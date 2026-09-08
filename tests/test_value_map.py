import copy
import json
from pathlib import Path

import pytest

from tests import test_operational_economics as helpers
from tests.test_operational_economics import _input, _decision
from operational_economics import initialize_economic_state, persist_economic_packet, record_goal_b_evidence
from value_map import build_value_map, client_value_section, validate_append_only

S=('LOW','BASE','HIGH')

@pytest.fixture
def case_packet():
    helper=helpers.OperationalEconomicsB2Tests();case,directory=helper._case()
    initialize_economic_state(case)
    packet=helper._packet()
    record_goal_b_evidence(case,{'evidence_id':'GBE-V','evidence_type':'GOAL_B_CLIENT_RESPONSE',
        'content':{'response_text':'Estimation du contrôle qui aurait été envisagé.',
                   'measurements':{'people':{'value':2,'unit':'person'},'hours':{'value':4,'unit':'h'},'energy':{'value':100,'unit':'kWh'}}}})
    yield case,packet
    directory.cleanup()


def quantity(key):return {s:{'evidence_ref':'GBE-V','measurement_key':key} for s in S}


def record(**overrides):
    return {'value_id':'V1','category':'INVESTIGATION_VALUE','phase':'PRE_ACTION_ESTIMATE',
        'value_status':'OBSERVED_VALUE','source_status':'CLIENT_EXPLICIT','source_refs':['GBE-V'],
        'finding_ids':['FIND-01'],'counterfactual_basis':'UNKNOWN','counterfactual_confidence':'NOT_CALIBRATED',
        'provenance':{'source_refs':['GBE-V'],'finding_refs':['FIND-01']},
        'question_resolved':'La variation est-elle indépendante de la production ?',**overrides}


def time_record():
    return record(value_status='ESTIMATED_AVOIDED_VALUE',counterfactual_basis='DIRECT_CLIENT_STATEMENT',
        time={'people_count':quantity('people'),'hours_per_person':quantity('hours'),'role':'technicien',
              'counterfactual_status':'CLIENT_ESTIMATED','source_status':'CLIENT_EXPLICIT','confidence':'MEDIUM'})


def save(case,packet,r):
    packet['value_assessment']={'records':[r]}
    return persist_economic_packet(case,packet)['value_map']


def test_unknown_time_stays_unknown_not_zero(case_packet):
    case,p=case_packet;m=save(case,p,record())
    t=m['investigation_value'][0]['time_calculation']
    assert t['time_saved_hours'] is None and t['time_value_eur'] is None
    assert m['total_value'] is None


def test_client_documented_hours_do_not_invent_euros(case_packet):
    case,p=case_packet;m=save(case,p,time_record());t=m['investigation_value'][0]['time_calculation']
    assert t['time_saved_hours']==dict.fromkeys(S,8)
    assert t['time_value_eur'] is None and t['documented_estimate']
    assert t['source_refs']==['GBE-V']


def test_hourly_rate_requires_existing_source(case_packet):
    case,p=case_packet;r=time_record();r['time']['hourly_cost_refs']=dict.fromkeys(S,'RATE')
    with pytest.raises(ValueError):save(case,p,r)
    source=_input('RATE',50,'EUR/h','per_hour');source['source']={}
    p['economic_inputs'].append(source)
    with pytest.raises(ValueError):save(case,p,r)


def test_time_monetization_uses_supplied_hourly_source(case_packet):
    case,p=case_packet;source=_input('RATE',50,'EUR/h','per_hour')
    source['source']=p['economic_inputs'][0]['source'];p['economic_inputs'].append(source)
    r=time_record();r['time']['hourly_cost_refs']=dict.fromkeys(S,'RATE')
    m=save(case,p,r);t=m['investigation_value'][0]['time_calculation']
    assert t['time_value_eur']==dict.fromkeys(S,400)
    assert 'ce n’est pas une économie réalisée' in str(client_value_section(m))


def test_scenario_hours_cannot_claim_documented_estimate(case_packet):
    case,p=case_packet
    p['scenario_assumptions'].append({'assumption_id':'HOURS','quantity_type':'NON_MONETARY','description':'Hypothèse de charge',
        'value':8,'unit':'h','period':'one_off','provenance':'SCENARIO_ASSUMPTION','status':'SCENARIO','source':{'method':'Explicit sensitivity'}})
    r=time_record();r['time']['hours_per_person']={s:{'assumption_ref':'HOURS'} for s in S}
    with pytest.raises(ValueError,match='scénario'):save(case,p,r)
    r['time']['counterfactual_status']='SCENARIO_ONLY'
    m=save(case,p,r)
    assert not m['investigation_value'][0]['time_calculation']['documented_estimate']
    assert 'hypothétique' in str(client_value_section(m))


def test_hypotheses_reduced_without_percentage_or_monetization(case_packet):
    case,p=case_packet;m=save(case,p,record(hypotheses_considered=['a','b','c'],hypotheses_rejected=['a','b'],hypotheses_remaining=['c']))
    r=m['investigation_value'][0]
    assert r['hypothesis_counts']=={'initial':3,'rejected':2,'remaining':1}
    assert r['monetization_status']=='UNKNOWN'
    assert '%' not in str(client_value_section(m))


def test_unknown_counterfactual_cannot_claim_avoided_estimate(case_packet):
    case,p=case_packet
    with pytest.raises(ValueError,match='contrefactuel'):save(case,p,record(value_status='ESTIMATED_AVOIDED_VALUE'))
    assert save(case,p,record())['investigation_value'][0]['counterfactual_basis']=='UNKNOWN'


def test_false_lead_and_undocumented_intervention_have_no_money(case_packet):
    case,p=case_packet;r=record(false_leads_avoided=['Hypothèse de fuite réfutée'],avoided_actions=[{'description':'Visite générale','was_considered':False,'causal_link_supported':False}])
    m=save(case,p,r);a=m['investigation_value'][0]['avoided_action_calculations'][0]
    assert a['action_avoided']=='possible' and a['cost_avoided_eur'] is None


def test_intervention_cost_needs_consideration_and_causal_support(case_packet):
    case,p=case_packet;r=record(avoided_actions=[{'description':'Visite générale','cost_refs':dict.fromkeys(S,'CAP')}])
    with pytest.raises(ValueError,match='envisagée'):save(case,p,r)


def test_decision_value_does_not_need_money_and_do_nothing_is_valid(case_packet):
    case,p=case_packet;p['decision']=_decision('DO_NOTHING',selected=[],considered=['ACT-01'])
    r=record(category='DECISION_VALUE',decision_before='Inspection générale envisagée',decision_after='Intervention non justifiée',decision_that_changed='DEC-01')
    m=save(case,p,r)
    assert len(m['decision_value'])==1 and m['decision_value'][0]['time_calculation']['time_value_eur'] is None

@pytest.mark.parametrize('relation',['OVERLAPPING','UNKNOWN','DEPENDENT','ALTERNATIVE','SEQUENTIAL','INDEPENDENT'])
def test_relationships_never_generate_cross_category_total(case_packet,relation):
    case,p=case_packet;p['value_assessment']={'records':[record()], 'relationships':[{'component_a':'V1','component_b':'economic:ACT-01','type':relation,'rationale':'Évaluation explicite','source_refs':['GBE-V']}]}
    m=persist_economic_packet(case,p)['value_map']
    assert m['total_value'] is None
    assert any(r['type']=='DEPENDENT' and r['component_a']=='energy:ACT-01' for r in m['relationships'])


def test_free_total_value_is_rejected(case_packet):
    case,p=case_packet
    with pytest.raises(ValueError):save(case,p,record(total_value=17842))


def test_pre_action_estimate_is_immutable(case_packet):
    case,p=case_packet;save(case,p,time_record())
    changed=time_record();changed['time']['role']='Autre'
    with pytest.raises(ValueError,match='immuables'):save(case,p,changed)


def test_realized_requires_post_action_evidence(case_packet):
    case,p=case_packet;r=record(phase='POST_ACTION_OBSERVED_RESULT',value_status='REALIZED_VALUE')
    with pytest.raises(ValueError,match='post-action'):save(case,p,r)


def test_realized_appends_without_rewriting_estimate(case_packet):
    case,p=case_packet;before=time_record();save(case,p,before)
    post={'action_ref':'ACT-01','action_completed_at':'2026-01-03T10:00:00','observed_at':'2026-02-03T10:00:00','comparison_supported':True,'confounders_reviewed':True,'source_refs':['GBE-POST']}
    record_goal_b_evidence(case,{'evidence_id':'GBE-POST','evidence_type':'GOAL_B_DOCUMENT_RESPONSE','content':{'post_action_observation':post}})
    after=record(value_id='V2',phase='POST_ACTION_OBSERVED_RESULT',value_status='REALIZED_VALUE',post_action=post,pre_action_ref='V1',source_status='DOCUMENT_EXTRACTED',source_refs=['GBE-POST'],provenance={'source_refs':['GBE-POST']})
    p['value_assessment']={'records':[before,after]};m=persist_economic_packet(case,p)['value_map']
    assert m['realized_values']==['V2']
    assert m['investigation_value'][0]['time_calculation']['time_saved_hours']['BASE']==8


def test_inconsistent_hypotheses_and_ranges_rejected(case_packet):
    case,p=case_packet
    with pytest.raises(ValueError):save(case,p,record(hypotheses_considered=['a'],hypotheses_rejected=['b']))
    record_goal_b_evidence(case,{'evidence_id':'GBE-BAD','evidence_type':'GOAL_B_CLIENT_RESPONSE','content':{'measurements':{'hours':{'value':10,'unit':'h'}}}})
    r=time_record();r['time']['hours_per_person']['LOW']={'evidence_ref':'GBE-BAD','measurement_key':'hours'}
    with pytest.raises(ValueError,match='LOW'):save(case,p,r)


def test_historical_energy_has_no_automatic_saving(case_packet):
    case,p=case_packet;r=record(category='DIRECT_ENERGY_VALUE',energy_observation={'basis':'COUNTERFACTUAL_ESTIMATE','baseline':'Comparaison passée','period':'2026-01','unit':'kWh','quantity_refs':quantity('energy')})
    m=save(case,p,r)
    assert m['direct_energy_value'][-1]['energy_observation']['quantity']['values']['BASE']==100
    assert 'ne prouve pas' in str(client_value_section(m))


def test_source_rewrite_cannot_change_old_time_estimate(case_packet):
    case,p=case_packet;source=_input('RATE',50,'EUR/h','per_hour');source['source']=p['economic_inputs'][0]['source'];p['economic_inputs'].append(source)
    r=time_record();r['time']['hourly_cost_refs']=dict.fromkeys(S,'RATE');save(case,p,r)
    p['economic_inputs'][-1]['value']=500
    with pytest.raises(ValueError,match='réécrit'):save(case,p,r)


def test_packet_cannot_inject_fake_native_evidence(case_packet):
    case,p=case_packet;r=time_record()
    for s in S:r['time']['people_count'][s]['evidence_ref']='FAKE'
    p['goal_b_evidence']=[{'evidence_id':'FAKE','evidence_type':'GOAL_B_CLIENT_RESPONSE','content':{'measurements':{'people':{'value':20,'unit':'person'}}}}]
    with pytest.raises(ValueError,match='absente'):save(case,p,r)


def test_material_numbers_cannot_enter_by_qualitative_text(case_packet):
    case,p=case_packet
    with pytest.raises(ValueError,match='Chiffre libre'):save(case,p,record(final_search_scope='5000 EUR économisés'))


def test_no_economic_data_yields_map_without_money(case_packet):
    case,p=case_packet
    p.update(economic_inputs=[],scenario_assumptions=[],scenario_calculations={})
    p['decision']=_decision('INSUFFICIENT_FOR_ECONOMIC_DECISION',selected=[],considered=['ACT-01'])
    m=save(case,p,record())
    assert m['direct_economic_value']==[] and m['total_value'] is None


def test_waiting_gate_still_blocks_value_promotion(case_packet):
    from energy_mvp.client_lifecycle import publish_client_requests
    from tests.test_client_workflow_unification import candidate
    case,p=case_packet
    publish_client_requests(case,[candidate('REQ-VALUE')])
    with pytest.raises(ValueError,match='STOP'):save(case,p,time_record())


def test_pdf_uses_revalidated_value_map_and_rejects_forged_total(tmp_path):
    from workspace.generate_goal_c_1_fixtures import generate
    from client_delivery import validate_client_report_model,render_client_report_pdf
    from value_map import load_value_map
    cases=generate(tmp_path);case=cases['C-A']
    state=json.loads((case/'investigation/economic_decision_state.json').read_text())
    finding=state['technical_finding_refs'][0]['finding_id']
    record_goal_b_evidence(case,{'evidence_id':'GBE-V','evidence_type':'GOAL_B_CLIENT_RESPONSE','content':{'measurements':{'people':{'value':2,'unit':'person'},'hours':{'value':4,'unit':'h'}}}})
    r=time_record();r['finding_ids']=[finding];r['provenance']['finding_refs']=[finding]
    state['value_assessment']={'records':[r]};state.pop('decision',None)
    persist_economic_packet(case,state)
    model_path=case/'outputs/client_report/CLIENT_REPORT_MODEL.json';model=json.loads(model_path.read_text())
    model['investigation_value']=client_value_section(load_value_map(case))
    validate_client_report_model(model,case)
    pdf=tmp_path/'value_report.pdf';render_client_report_pdf(model,model_path,pdf,case_directory=case)
    assert b'Valeur de l' in pdf.read_bytes() and b'Temps potentiellement' in pdf.read_bytes()
    forged=copy.deepcopy(model);forged['executive_summary']['economic_total']={'display':'17842 EUR'}
    with pytest.raises(ValueError,match='Total économique'):validate_client_report_model(forged,case)
    forged=copy.deepcopy(model);forged['investigation_value']['items'][0]['lines']=['Économie réalisée : 17842 EUR']
    with pytest.raises(ValueError,match='Value Map'):render_client_report_pdf(forged,model_path,tmp_path/'forged.pdf',case_directory=case)


def test_portfolio_rejects_mixed_currency_and_multiple_overlaps():
    from operational_economics import aggregate_declared_portfolio
    from tests.test_operational_economics import _calculation
    a=_calculation();b=copy.deepcopy(a)
    b['currency']='USD'
    # A valid deterministic USD table, rather than a forged arithmetic payload.
    from operational_economics import calculate_economic_scenarios
    b=calculate_economic_scenarios(a['reproducibility']['energy_effect'],tariff_per_kwh=dict.fromkeys(S,.2),input_references=a['reproducibility']['input_references'],currency='USD')
    with pytest.raises(ValueError,match='devise'):aggregate_declared_portfolio(['a','b'],{'a':a,'b':b},[{'action_a':'a','action_b':'b','type':'INDEPENDENT'}])


def test_overlapping_pair_corrections_cannot_double_subtract():
    from operational_economics import aggregate_declared_portfolio
    from tests.test_operational_economics import _calculation
    calc=_calculation()
    relations=[{'action_a':'a','action_b':'b','type':'OVERLAPPING','combined_effect_ref':'combined'},
               {'action_a':'a','action_b':'c','type':'OVERLAPPING','combined_effect_ref':'combined'},
               {'action_a':'b','action_b':'c','type':'INDEPENDENT'}]
    combined={'combined':{'effect_type':'ENERGY','energy_effect':calc['reproducibility']['energy_effect'],'economic_calculation':calc}}
    with pytest.raises(ValueError,match='Recouvrements multiples'):
        aggregate_declared_portfolio(['a','b','c'],dict.fromkeys(['a','b','c'],calc),relations,combined_effects=combined,economic_value_sources=[_input('TAR',.2,'EUR/kWh','per_kwh')])


def test_decision_delay_is_sourced_not_automatic_money(case_packet):
    case,p=case_packet
    record_goal_b_evidence(case,{'evidence_id':'GBE-D','evidence_type':'GOAL_B_CLIENT_RESPONSE','content':{'measurements':{'before':{'value':10,'unit':'day'},'after':{'value':2,'unit':'day'}}}})
    r=record(category='DECISION_VALUE',counterfactual_basis='DIRECT_CLIENT_STATEMENT',
             decision_delay_before={s:{'evidence_ref':'GBE-D','measurement_key':'before'} for s in S},
             decision_delay_after={s:{'evidence_ref':'GBE-D','measurement_key':'after'} for s in S})
    m=save(case,p,r);assert m['decision_value'][0]['decision_delay_calculation']['acceleration_days']['BASE']==8
    assert m['decision_value'][0]['time_calculation']['time_value_eur'] is None


def test_investigate_first_voi_reuses_cost_input(case_packet):
    case,p=case_packet;p['decision']=_decision('INVESTIGATE_FIRST')
    p['decision']['evidence_acquisition'].update(information_to_acquire='Contrôle ciblé',acquisition_cost={'economic_input_ref':'CAP'},acquisition_burden='Créneau de maintenance',possible_decision_value='Écarter un remplacement inutile')
    m=save(case,p,record());assert m['information_value'][0]['acquisition_cost']['economic_input_ref']=='CAP'
    p['decision']['evidence_acquisition']['acquisition_cost']={'economic_input_ref':'UNKNOWN'}
    with pytest.raises(ValueError,match='acquisition'):save(case,p,record())


def test_realization_cannot_promote_estimated_time(case_packet):
    case,p=case_packet;r=time_record();r.update(phase='POST_ACTION_OBSERVED_RESULT',value_status='REALIZED_VALUE')
    with pytest.raises(ValueError,match='contrefactuel'):save(case,p,r)


def test_realized_quantities_must_come_from_post_action_measurements(case_packet):
    case,p=case_packet
    post={'action_ref':'ACT-01','action_completed_at':'2026-01-03T10:00:00','observed_at':'2026-02-03T10:00:00',
          'comparison_supported':True,'confounders_reviewed':True,'source_refs':['GBE-POST'],
          'energy_reduction_kwh':{s:{'evidence_ref':'GBE-POST','measurement_key':'reduction'} for s in S}}
    record_goal_b_evidence(case,{'evidence_id':'GBE-POST','evidence_type':'GOAL_B_DOCUMENT_RESPONSE',
        'content':{'post_action_observation':post,'measurements':{'reduction':{'value':120,'unit':'kWh'}}}})
    r=record(category='DIRECT_ENERGY_VALUE',phase='POST_ACTION_OBSERVED_RESULT',value_status='REALIZED_VALUE',post_action=post,source_status='DOCUMENT_EXTRACTED',source_refs=['GBE-POST'],provenance={'source_refs':['GBE-POST']})
    m=save(case,p,r)
    assert m['direct_energy_value'][-1]['post_action_result']['measurements']['energy_reduction_kwh']['values']['BASE']==120
    assert 'Baisse énergétique observée' in str(client_value_section(m))
    p['value_assessment']['records'].append({**r,'value_id':'V2','post_action':{**post,'energy_reduction_kwh':quantity('energy')}})
    with pytest.raises(ValueError,match='post-action'):persist_economic_packet(case,p)


def test_value_map_human_review_is_bound_to_exact_projection(case_packet):
    from value_map import validate_value_map_human_review,value_map_digest
    from energy_mvp.case_lifecycle import evaluate_delivery_gate
    case,p=case_packet;m=save(case,p,time_record())
    with pytest.raises(ValueError,match='humaine'):validate_value_map_human_review(case,{})
    validate_value_map_human_review(case,{'value_map_sha256':value_map_digest(m)})
    (case/'investigation/trace.json').write_text(json.dumps({'entries':[]}))
    result=evaluate_delivery_gate(case)
    assert not result['ready_for_delivery']
    assert any('Value Map' in reason for reason in result['blocking_reasons'])
    path=case/'investigation/value_map.json';tampered=json.loads(path.read_text());tampered['total_value']=17842;path.write_text(json.dumps(tampered))
    with pytest.raises(ValueError,match='canonique'):validate_value_map_human_review(case,{'value_map_sha256':value_map_digest(m)})


def test_scenario_counterfactual_cannot_be_documented_time(case_packet):
    case,p=case_packet;r=time_record();r['counterfactual_basis']='SCENARIO_ASSUMPTION'
    with pytest.raises(ValueError,match='scénario'):save(case,p,r)
    r['time']['counterfactual_status']='SCENARIO_ONLY'
    m=save(case,p,r)
    assert not m['investigation_value'][0]['time_calculation']['documented_estimate']
    assert 'hypothétique' in str(client_value_section(m))


@pytest.mark.parametrize('value',[float('nan'),float('inf'),float('-inf')])
def test_nonfinite_economic_value_rejected(value):
    from operational_economics import validate_economic_input
    with pytest.raises(ValueError):validate_economic_input(_input('INVALID',value,'EUR','one_off'))


def test_client_section_keeps_scenario_energy_hypothetical():
    q={'scenario_only':False,'values':dict.fromkeys(S,100),'unit':'kWh'}
    m={'direct_energy_value':[{'value_id':'V','source_status':'SCENARIO_ASSUMPTION',
        'energy_observation':{'quantity':q,'basis':'COUNTERFACTUAL_ESTIMATE'}}],
       'direct_economic_value':[],'investigation_value':[],'decision_value':[],'unverified_potential_value':[]}
    assert 'Hypothèse de scénario' in str(client_value_section(m))
    assert 'Écart énergétique documenté' not in str(client_value_section(m))
