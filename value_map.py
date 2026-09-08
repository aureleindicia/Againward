"""Value Map extension of Operational Economics. Representation, never recommendation.

Canonical inputs live in economic_decision_state.json. No global monetary total exists.
Structured evidence is necessary but its counterfactual meaning remains an agent judgment.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from itertools import combinations
import math
from typing import Any

from operational_economics import (
    CONFIDENCE_LEVELS, RELATIONSHIP_TYPES, SCENARIOS, _value_source_index,
    _validate_calculation_provenance, _validate_economic_input_sources,
    _case_provenance_ids, _case_provenance_metadata, _goal_b_evidence_index,
    _goal_a_findings, _read, _write,
)

CATEGORIES = {'DIRECT_ENERGY_VALUE','DIRECT_ECONOMIC_VALUE','INVESTIGATION_VALUE',
              'DECISION_VALUE','UNVERIFIED_POTENTIAL_VALUE'}
VALUE_STATUSES = {'OBSERVED_VALUE','ESTIMATED_AVOIDED_VALUE','POTENTIAL_VALUE','REALIZED_VALUE'}
COUNTERFACTUAL_BASES = {'DIRECT_CLIENT_STATEMENT','DOCUMENTED_STANDARD_PROCESS',
    'HISTORICAL_CLIENT_BEHAVIOR','EXTERNAL_QUOTE','SCENARIO_ASSUMPTION','UNKNOWN'}
SOURCE_STATUSES = {'CLIENT_EXPLICIT','DOCUMENT_EXTRACTED','OBSERVED_INTERNAL_PROCESS',
    'EXTERNAL_QUOTE','SCENARIO_ASSUMPTION','UNKNOWN'}
TIME_STATUSES = {'MEASURED','CLIENT_ESTIMATED','DOCUMENTED_PROCESS_ESTIMATE','SCENARIO_ONLY','UNKNOWN'}
PROVENANCE_KEYS = {'finding_refs','source_refs','calculation_refs','client_statement_refs',
                   'scenario_assumption_refs','action_refs','decision_refs'}
CONFIDENCES = ('technical_confidence','economic_confidence','counterfactual_confidence','realization_confidence')
INVESTIGATION_FIELDS = {'question_resolved','initial_search_scope','final_search_scope',
    'hypotheses_considered','hypotheses_rejected','hypotheses_remaining','false_leads_avoided',
    'investigation_steps_avoided','field_checks_avoided','external_interventions_avoided',
    'instrumentation_avoided','internal_hours_potentially_avoided','external_cost_potentially_avoided',
    'time','avoided_actions'}
DECISION_FIELDS = {'decision_before','uncertainty_before','decision_after','uncertainty_after',
    'action_enabled','action_prevented','action_deferred','evidence_needed_before','evidence_needed_after',
    'decision_delay_before','decision_delay_after','decision_acceleration','decision_that_changed'}
COMMON = {'question_resolved','value_id','category','phase','value_status','source_status','source_refs','finding_ids',
    'confidence','counterfactual_basis','counterfactual_confidence','monetization_status',
    'provenance','limitations','post_action','pre_action_ref','energy_observation',*CONFIDENCES}


def _text(value: Any, name: str) -> str:
    if not isinstance(value,str) or not value.strip(): raise ValueError(f'{name}: texte requis.')
    return value


def _number(value: Any) -> float:
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:
        raise ValueError('Valeur finie non négative requise.')
    return float(value)


def _range(values: Any) -> dict[str,float]:
    if not isinstance(values,dict) or set(values)!=set(SCENARIOS): raise ValueError('LOW/BASE/HIGH requis.')
    result={s:_number(values[s]) for s in SCENARIOS}
    if not result['LOW']<=result['BASE']<=result['HIGH']: raise ValueError('LOW ≤ BASE ≤ HIGH requis.')
    return result


def _refs(refs: Any, known: set[str], name: str, required: bool=False) -> list[str]:
    if not isinstance(refs,list) or any(not isinstance(r,str) or r not in known for r in refs):
        raise ValueError(f'{name}: références inconnues ou invalides.')
    if required and not refs: raise ValueError(f'{name}: provenance requise.')
    return refs


def _context(case, state):
    findings=_goal_a_findings(case); evidence=_goal_b_evidence_index(state)
    sources=_case_provenance_ids(case)|set(evidence)
    inputs=state.get('economic_inputs',[]); assumptions=state.get('scenario_assumptions',[])
    values=_value_source_index(inputs,assumptions)
    _validate_economic_input_sources(inputs,_case_provenance_ids(case),evidence,_case_provenance_metadata(case))
    return {'finding_refs':set(findings),'source_refs':sources,
        'client_statement_refs':{k for k,v in evidence.items() if v['evidence_type']=='GOAL_B_CLIENT_RESPONSE'},
        'scenario_assumption_refs':{a['assumption_id'] for a in assumptions},
        'calculation_refs':set(state.get('scenario_calculations',{})),
        'action_refs':{a['action_id'] for a in state.get('candidate_actions',[])},
        'decision_refs':{d['decision_id'] for d in state.get('decisions',[])},
        'evidence':evidence,'values':values,'findings':findings}


def _provenance(record, ctx):
    p=record.get('provenance',{})
    if not isinstance(p,dict) or set(p)-PROVENANCE_KEYS: raise ValueError('Provenance typée requise.')
    for key in PROVENANCE_KEYS: _refs(p.get(key,[]),ctx[key],key)
    _refs(record.get('source_refs',[]),ctx['source_refs'],'source_refs')
    _refs(record.get('finding_ids',[]),ctx['finding_refs'],'finding_ids')
    if record['source_status']!='UNKNOWN' and not (p.get('source_refs') or record.get('source_refs') or p.get('scenario_assumption_refs')):
        raise ValueError('Valeur matérielle sans source ou hypothèse structurée.')
    return p


def resolve_quantity(spec, ctx, unit):
    """Resolve LOW/BASE/HIGH from persisted Goal B measurements or scenario assumptions.

    spec supplies references only, never the economic number it wishes to display.
    Evidence content.measurements[key] = {value, unit}; client extraction remains explicit.
    """
    if spec is None: return None
    if not isinstance(spec,dict) or set(spec)!=set(SCENARIOS): raise ValueError('Références de quantité LOW/BASE/HIGH requises.')
    values={}; refs=[]; hypothetical=False
    for s,ref in spec.items():
        if not isinstance(ref,dict): raise ValueError('Référence numérique structurée requise.')
        if set(ref)=={'assumption_ref'}:
            source=ctx['values'].get(ref['assumption_ref'])
            if source is None or source.get('provenance')!='SCENARIO_ASSUMPTION': raise ValueError('Hypothèse absente.')
            hypothetical=True;refs.append(ref['assumption_ref'])
        elif set(ref)=={'evidence_ref','measurement_key'}:
            evidence=ctx['evidence'].get(ref['evidence_ref'])
            if evidence is None: raise ValueError('Preuve numérique Goal B absente.')
            source=evidence.get('content',{}).get('measurements',{}).get(ref['measurement_key'])
            if not isinstance(source,dict): raise ValueError('Mesure structurée absente de la preuve.')
            refs.append(ref['evidence_ref'])
        else: raise ValueError('Nombre libre interdit : citer une mesure persistée ou hypothèse.')
        if source.get('unit')!=unit: raise ValueError('Unité de quantité incompatible.')
        values[s]=_number(source.get('value'))
    return {'values':_range(values),'unit':unit,'source_refs':sorted(set(refs)),
            'scenario_only':hypothetical}


def _rate(spec, ctx):
    if spec is None:return None
    _refs(list(spec.values()) if isinstance(spec,dict) else None,set(ctx['values']),'Coût horaire',True)
    if set(spec)!=set(SCENARIOS):raise ValueError('Coût horaire LOW/BASE/HIGH requis.')
    result={};scenario=False
    for s,ref in spec.items():
        source=ctx['values'][ref]
        if source.get('status')=='UNKNOWN' or source.get('unit')!='EUR/h' or source.get('period')!='per_hour' or source.get('currency')!='EUR':
            raise ValueError('Coût horaire EUR/h sourcé requis.')
        # An external generic assumption cannot masquerade as documented client cost.
        if source.get('provenance') in {'EXTERNAL_ASSUMPTION','SCENARIO_ASSUMPTION'} or source.get('status')=='SCENARIO':scenario=True
        result[s]=source['value']
    return {'values':_range(result),'unit':'EUR/h','source_refs':list(spec.values()),'scenario_only':scenario}


def _time(record, ctx):
    time=record.get('time')
    if time is None:return {'time_saved_hours':None,'time_value_eur':None,'monetization_status':'UNKNOWN'}
    allowed={'people_count','hours_per_person','role','source_status','source_refs','confidence',
             'counterfactual_status','hourly_cost_refs','counterfactual_basis'}
    if not isinstance(time,dict) or set(time)-allowed:raise ValueError('Contrat de temps invalide.')
    status=time.get('counterfactual_status','UNKNOWN')
    if status not in TIME_STATUSES:raise ValueError('Statut du temps inconnu.')
    source_refs=_refs(time.get('source_refs',record.get('source_refs',[])),ctx['source_refs'],'Sources du temps')
    if status=='CLIENT_ESTIMATED' and not set(source_refs)&ctx['client_statement_refs']:
        raise ValueError('Temps estimé par client exige une déclaration client persistée.')
    if status=='MEASURED' and time.get('source_status')!='OBSERVED_INTERNAL_PROCESS':
        raise ValueError('Temps mesuré exige un processus observé ; pas une simple estimation client.')
    if time.get('confidence','NOT_CALIBRATED') not in CONFIDENCE_LEVELS:raise ValueError('Confiance temps invalide.')
    people=resolve_quantity(time.get('people_count'),ctx,'person')
    hours=resolve_quantity(time.get('hours_per_person'),ctx,'h')
    rate=_rate(time.get('hourly_cost_refs'),ctx)
    if status=='UNKNOWN':
        if people or hours or rate:raise ValueError('Temps UNKNOWN ne peut porter de chiffres.')
        return {'time_saved_hours':None,'time_value_eur':None,'monetization_status':'UNKNOWN'}
    if people is None or hours is None:raise ValueError('Temps estimé exige personnes et heures sourcées.')
    source_status=time.get('source_status')
    if source_status not in SOURCE_STATUSES-{'UNKNOWN'}:raise ValueError('Source du temps requise.')
    scenario=people['scenario_only'] or hours['scenario_only'] or source_status=='SCENARIO_ASSUMPTION' or record['counterfactual_basis']=='SCENARIO_ASSUMPTION'
    if scenario and status!='SCENARIO_ONLY':raise ValueError('Temps de scénario ne devient pas documenté.')
    if status=='SCENARIO_ONLY':scenario=True
    if record['counterfactual_basis']=='UNKNOWN':raise ValueError('Temps évité exige un contrefactuel explicite.')
    values={s:people['values'][s]*hours['values'][s] for s in SCENARIOS}
    euros=None if rate is None else {s:values[s]*rate['values'][s] for s in SCENARIOS}
    if euros is not None:_range(euros)
    return {'time_saved_hours':_range(values),'time_value_eur':euros,
        'counterfactual_status':status,'documented_estimate':status in TIME_STATUSES-{'UNKNOWN','SCENARIO_ONLY'},
        'source_refs':sorted(set(people['source_refs']+hours['source_refs']+(rate['source_refs'] if rate else []))),
        'monetization_status':'NOT_MONETIZED' if rate is None else ('SCENARIO_ONLY' if scenario or rate['scenario_only'] else 'DOCUMENTED_ESTIMATE'),
        'scenario_only':scenario,'not_realized_saving':True}


def _avoided(items,ctx):
    if items is None:return None
    if not isinstance(items,list):raise ValueError('Actions évitées : liste requise.')
    result=[]
    for item in items:
        if set(item)-{'description','action_ref','source_refs','was_considered','causal_link_supported','cost_refs'}:raise ValueError('Action évitée invalide.')
        _text(item.get('description'),'Action évitée')
        _refs(item.get('source_refs',[]),ctx['source_refs'],'Action évitée')
        if item.get('action_ref') is not None:_refs([item['action_ref']],ctx['action_refs'],'action_ref')
        cost=_rate_cost(item.get('cost_refs'),ctx)
        documented=item.get('was_considered') is True and item.get('causal_link_supported') is True and bool(item.get('source_refs'))
        if cost is not None and not documented:raise ValueError('Coût évité exige action envisagée et lien causal documentés.')
        result.append({**deepcopy(item),'action_avoided':'documented' if documented else 'possible',
                       'cost_avoided_eur':None if cost is None else cost['values'],
                       'scenario_only':False if cost is None else cost['scenario_only']})
    return result


def _rate_cost(spec,ctx):
    if spec is None:return None
    if not isinstance(spec,dict) or set(spec)!=set(SCENARIOS):raise ValueError('Coût LOW/BASE/HIGH requis.')
    values={};scenario=False
    for s,ref in spec.items():
        source=ctx['values'].get(ref)
        if not source or source.get('status')=='UNKNOWN' or source.get('unit')!='EUR' or source.get('period')!='one_off':raise ValueError('Coût ponctuel sourcé requis.')
        values[s]=source['value'];scenario|=source.get('provenance') in {'SCENARIO_ASSUMPTION','EXTERNAL_ASSUMPTION'} or source.get('status')=='SCENARIO'
    return {'values':_range(values),'scenario_only':scenario}


def _post_action(record, ctx):
    post=record.get('post_action')
    if not isinstance(post,dict):raise ValueError('REALIZED_VALUE exige une preuve post-action.')
    _refs([post.get('action_ref')],ctx['action_refs'],'Action réalisée',True)
    refs=_refs(post.get('source_refs'),set(ctx['evidence']),'Preuves post-action',True)
    action_at=datetime.fromisoformat(_text(post.get('action_completed_at'),'Date action'))
    observed_at=datetime.fromisoformat(_text(post.get('observed_at'),'Date observation'))
    if (action_at.tzinfo is None) != (observed_at.tzinfo is None):
        raise ValueError('Dates post-action : conventions de fuseau incompatibles.')
    if observed_at<=action_at:raise ValueError('Observation doit être postérieure à action.')
    if post.get('comparison_supported') is not True or post.get('confounders_reviewed') is not True:
        raise ValueError('Avant/après comparable et confondants examinés requis.')
    for ref in refs:
        proof=ctx['evidence'][ref].get('content',{}).get('post_action_observation')
        if not isinstance(proof,dict) or proof.get('action_ref')!=post['action_ref'] or proof.get('observed_at')!=post['observed_at'] or proof.get('action_completed_at')!=post['action_completed_at']:
            raise ValueError('Preuve post-action ne correspond pas à la réalisation déclarée.')
    allowed={'action_ref','action_completed_at','observed_at','comparison_supported','confounders_reviewed','source_refs',
             'energy_reduction_kwh','actual_intervention_cost_eur','actual_time_spent_hours','observed_saving_eur'}
    if set(post)-allowed:raise ValueError('Champ post-action inconnu.')
    results={}
    for field,unit in [('energy_reduction_kwh','kWh'),('actual_intervention_cost_eur','EUR'),('actual_time_spent_hours','h'),('observed_saving_eur','EUR')]:
        q=resolve_quantity(post.get(field),ctx,unit)
        if q is not None and (q['scenario_only'] or set(q['source_refs'])-set(refs)):
            raise ValueError('Résultat réalisé exige une mesure des preuves post-action, pas une hypothèse.')
        results[field]=q
    return {**deepcopy(post),'measurements':results}


def _record(record,ctx):
    if not isinstance(record,dict) or set(record)-(COMMON|INVESTIGATION_FIELDS|DECISION_FIELDS):raise ValueError('Champs Value Map inconnus (totaux/nombres libres interdits).')
    _text(record.get('value_id'),'value_id')
    if record.get('category') not in CATEGORIES:raise ValueError('Catégorie de valeur inconnue.')
    permitted = {'INVESTIGATION_VALUE':INVESTIGATION_FIELDS, 'DECISION_VALUE':DECISION_FIELDS,
                 'DIRECT_ENERGY_VALUE':set(), 'DIRECT_ECONOMIC_VALUE':set(),
                 'UNVERIFIED_POTENTIAL_VALUE':INVESTIGATION_FIELDS|DECISION_FIELDS}[record['category']]
    if set(record)-(COMMON|permitted):raise ValueError('Dimensions incompatibles avec la catégorie de valeur.')
    if record.get('phase') not in {'PRE_ACTION_ESTIMATE','POST_ACTION_OBSERVED_RESULT'}:raise ValueError('Phase explicite requise.')
    if record.get('value_status') not in VALUE_STATUSES:raise ValueError('Statut de valeur requis.')
    if record.get('source_status') not in SOURCE_STATUSES:raise ValueError('Statut de source requis.')
    if record.get('counterfactual_basis','UNKNOWN') not in COUNTERFACTUAL_BASES:raise ValueError('Base contrefactuelle inconnue.')
    record=deepcopy(record);record.setdefault('counterfactual_basis','UNKNOWN')
    for field in CONFIDENCES:
        record.setdefault(field,'NOT_CALIBRATED')
        if record[field] not in CONFIDENCE_LEVELS:raise ValueError('Confiances distinctes invalides.')
    if record.get('confidence','NOT_CALIBRATED') not in CONFIDENCE_LEVELS:raise ValueError('Confiance invalide.')
    p=_provenance(record,ctx)
    textual = {'question_resolved','initial_search_scope','final_search_scope','false_leads_avoided',
        'investigation_steps_avoided','field_checks_avoided','external_interventions_avoided','instrumentation_avoided',
        'decision_before','uncertainty_before','decision_after','uncertainty_after','action_enabled','action_prevented',
        'action_deferred','evidence_needed_before','evidence_needed_after'}
    for field in textual:
        value = record.get(field)
        if value is not None:
            texts = value if isinstance(value,list) else [value]
            if not texts or any(not isinstance(v,str) or not v.strip() for v in texts):
                raise ValueError('Description qualitative requise ; aucun nombre matériel libre.')
            # Numeric claims belong in referenced quantities, not the prose route to PDF.
            if any(any(c.isdigit() for c in v) or '€' in v or 'EUR' in v for v in texts):
                raise ValueError('Chiffre libre interdit dans une description de valeur.')
    if record['source_status']=='UNKNOWN' and any(record.get(k) is not None for k in ('time','energy_observation','post_action','avoided_actions','decision_delay_before','decision_delay_after')):

        raise ValueError('Source UNKNOWN ne supporte pas une quantité matérielle.')
    if record['source_status']=='SCENARIO_ASSUMPTION' and record['value_status']!='POTENTIAL_VALUE':
        raise ValueError('Une hypothèse de scénario reste POTENTIAL_VALUE, jamais observée ou réalisée.')
    if record['counterfactual_basis']=='UNKNOWN' and record['counterfactual_confidence']!='NOT_CALIBRATED':
        raise ValueError('Contrefactuel UNKNOWN : confiance NOT_CALIBRATED requise.')
    if record['phase']=='POST_ACTION_OBSERVED_RESULT' and (record.get('time') is not None or record.get('avoided_actions') is not None or record.get('energy_observation') is not None):
        raise ValueError('Un temps/intervention potentiellement évité reste contrefactuel ; les résultats post-action utilisent des mesures distinctes.')
    if record['value_status']=='REALIZED_VALUE':
        if record['phase']!='POST_ACTION_OBSERVED_RESULT':raise ValueError('Valeur réalisée exige POST_ACTION_OBSERVED_RESULT.')
        record['post_action_result']=_post_action(record,ctx)
        if record['source_status'] in {'UNKNOWN','SCENARIO_ASSUMPTION'}:raise ValueError('Une hypothèse ne devient pas réalisée.')
    elif record['phase']=='POST_ACTION_OBSERVED_RESULT':record['post_action_result']=_post_action(record,ctx)
    if record['value_status']=='ESTIMATED_AVOIDED_VALUE' and record['counterfactual_basis']=='UNKNOWN':raise ValueError('Estimation évitée sans contrefactuel.')
    if record['source_status']=='SCENARIO_ASSUMPTION' and not p.get('scenario_assumption_refs'):raise ValueError('Scénario exige une hypothèse persistée.')
    for field in ('internal_hours_potentially_avoided','external_cost_potentially_avoided','decision_acceleration'):
        if record.get(field) is not None:raise ValueError(f'{field}: utiliser les calculs/quantités référencées, pas un nombre libre.')
    before_delay=resolve_quantity(record.get('decision_delay_before'),ctx,'day')
    after_delay=resolve_quantity(record.get('decision_delay_after'),ctx,'day')
    record['decision_delay_calculation']={'before':before_delay,'after':after_delay,'acceleration_days':None}
    if before_delay is not None and after_delay is not None and record['counterfactual_basis']!='UNKNOWN':
        record['decision_delay_calculation']['acceleration_days']={
            'LOW':before_delay['values']['LOW']-after_delay['values']['HIGH'],
            'BASE':before_delay['values']['BASE']-after_delay['values']['BASE'],
            'HIGH':before_delay['values']['HIGH']-after_delay['values']['LOW']}
    if record.get('energy_observation') is not None:
        observation=record['energy_observation']
        if record['category']!='DIRECT_ENERGY_VALUE':raise ValueError('Énergie dans catégorie incorrecte.')
        if observation.get('basis') not in {'DIRECTLY_MEASURED_HISTORICAL_EXCESS','COUNTERFACTUAL_ESTIMATE','MODELED_REDUCTION','ENGINEERING_ASSUMPTION','SCENARIO_ESTIMATE'}:raise ValueError('Base énergie inconnue.')
        if not record.get('finding_ids'):raise ValueError('Observation énergie exige finding.')
        if observation.get('unit') not in {'kWh','MWh'}:raise ValueError('Observation historique kWh/MWh requise.')
        _text(observation.get('baseline'),'Baseline');_text(observation.get('period'),'Période observée')
        record['energy_observation']['quantity']=resolve_quantity(observation.get('quantity_refs'),ctx,observation['unit'])
        if record['energy_observation']['quantity'] is None:raise ValueError('Quantité énergie absente.')
    for field in ('hypotheses_considered','hypotheses_rejected','hypotheses_remaining'):
        value=record.get(field)
        if value is not None and (not isinstance(value,list) or any(not isinstance(x,str) or not x for x in value) or len(set(value))!=len(value)):raise ValueError('Hypothèses : identifiants uniques requis.')
    considered=record.get('hypotheses_considered');rejected=record.get('hypotheses_rejected');remaining=record.get('hypotheses_remaining')
    if considered is not None:
        if set(rejected or [])-set(considered) or set(remaining or [])-set(considered):raise ValueError('Hypothèse absente du périmètre initial.')
    if set(rejected or []) & set(remaining or []):raise ValueError('Hypothèse simultanément rejetée et restante.')
    if considered is not None and rejected is not None and remaining is not None and set(considered)!=set(rejected)|set(remaining):raise ValueError('Partition des hypothèses incomplète.')
    record['hypothesis_counts']={key:None if value is None else len(value) for key,value in [('initial',considered),('rejected',rejected),('remaining',remaining)]}
    record['time_calculation']=_time(record,ctx)
    record['avoided_action_calculations']=_avoided(record.get('avoided_actions'),ctx)
    if record['counterfactual_basis']=='SCENARIO_ASSUMPTION' or record['source_status']=='SCENARIO_ASSUMPTION':
        for avoided in record['avoided_action_calculations'] or []:
            avoided['scenario_only']=True
            avoided['action_avoided']='possible'
    if any(a['cost_avoided_eur'] is not None for a in record['avoided_action_calculations'] or []) and record['counterfactual_basis']=='UNKNOWN':
        raise ValueError('Coût évité exige un contrefactuel explicite.')
    record['internal_hours_potentially_avoided']=record['time_calculation']['time_saved_hours']
    avoided=record['avoided_action_calculations'] or []
    # One component may be exposed directly; several interventions are never silently summed.
    record['external_cost_potentially_avoided']=avoided[0]['cost_avoided_eur'] if len(avoided)==1 else None
    record['decision_acceleration']=record['decision_delay_calculation']['acceleration_days']
    record['monetization_status']=record['time_calculation']['monetization_status']
    if record['external_cost_potentially_avoided'] is not None and record['time_calculation']['time_value_eur'] is None:
        record['monetization_status']='SCENARIO_ONLY' if avoided[0]['scenario_only'] else 'DOCUMENTED_ESTIMATE'
    if record.get('decision_that_changed') is not None:
        _refs([record['decision_that_changed']],ctx['decision_refs'],'Décision changée')
    return record


def build_value_map(case, state):
    """Project the current economic state; all judgments must already be supplied."""
    from energy_mvp.client_lifecycle import assert_workflow_action_allowed
    assert_workflow_action_allowed(case, "value_map_review")
    ctx=_context(case,state)
    extension=state.get('value_assessment',{})
    if not isinstance(extension,dict) or set(extension)-{'records','relationships','limitations'}:raise ValueError('Extension Value Map invalide.')
    for decision in state.get('decisions',[]):
        acquisition=decision.get('evidence_acquisition') or {}
        cost=acquisition.get('acquisition_cost')
        if cost is not None:
            if not isinstance(cost,dict) or set(cost)!={'economic_input_ref'}:
                raise ValueError('Acquisition : référence économique requise.')
            source=ctx['values'].get(cost['economic_input_ref'])
            if not source or source.get('status')=='UNKNOWN' or source.get('unit')!='EUR' or source.get('period')!='one_off':
                raise ValueError('Coût d’acquisition sans input ponctuel valide.')
    records=[_record(r,ctx) for r in extension.get('records',[])]
    ids=[r['value_id'] for r in records]
    if len(set(ids))!=len(ids):raise ValueError('value_id dupliqué.')
    by_id={r['value_id']:r for r in records}
    for r in records:
        if r.get('pre_action_ref'):
            before=by_id.get(r['pre_action_ref'])
            if not before or before['phase']!='PRE_ACTION_ESTIMATE' or r['phase']!='POST_ACTION_OBSERVED_RESULT':raise ValueError('Lien avant/après invalide.')
    energy=[];economic=[];derived_relations=[]
    for action,calculation in state.get('scenario_calculations',{}).items():
        _validate_calculation_provenance(calculation,value_sources=ctx['values'],allowed_energy_refs=ctx['finding_refs']|ctx['source_refs'])
        effect=calculation['reproducibility']['energy_effect']
        energy.append({'value_id':f'energy:{action}','category':'DIRECT_ENERGY_VALUE','effect':deepcopy(effect),
            'value_status':'POTENTIAL_VALUE','recoverable_saving':None,'calculation_ref':action,
            'limitations':['Effet annualisé hérité de Goal B ; la base ne prouve pas la récupérabilité.']})
        economic.append({'value_id':f'economic:{action}','category':'DIRECT_ECONOMIC_VALUE','calculation':deepcopy(calculation),
            'value_status':'POTENTIAL_VALUE','not_realized':True,'calculation_ref':action})
        derived_relations.append({'component_a':f'energy:{action}','component_b':f'economic:{action}','type':'DEPENDENT','rationale':'Même effet exprimé en énergie et en argent ; non additif.'})
    all_ids=set(ids)|{r['value_id'] for r in energy+economic}
    if len(all_ids)!=len(ids)+len(energy)+len(economic):raise ValueError('Identifiants de valeur réservés ou dupliqués.')
    relations=list(derived_relations);pairs={frozenset((r['component_a'],r['component_b'])) for r in relations}
    for relation in extension.get('relationships',[]):
        if set(relation)-{'component_a','component_b','type','rationale','source_refs'}:raise ValueError('Relation de valeur invalide.')
        pair=frozenset((relation.get('component_a'),relation.get('component_b')))
        if len(pair)!=2 or pair-all_ids or pair in pairs or relation.get('type') not in RELATIONSHIP_TYPES:raise ValueError('Relation de valeur inconnue/dupliquée.')
        _text(relation.get('rationale'),'Relation');_refs(relation.get('source_refs',[]),ctx['source_refs'],'Relation',True)
        relations.append(deepcopy(relation));pairs.add(pair)
    for a,b in combinations(sorted(all_ids),2):
        if frozenset((a,b)) not in pairs:relations.append({'component_a':a,'component_b':b,'type':'UNKNOWN','rationale':'Relation non instruite ; aucune somme autorisée.'})
    return {'schema_version':'againward-value-map-v1','technical_findings':deepcopy(state.get('technical_finding_refs',[])),
        'direct_energy_value':energy+[r for r in records if r['category']=='DIRECT_ENERGY_VALUE'],
        'direct_economic_value':economic+[r for r in records if r['category']=='DIRECT_ECONOMIC_VALUE'],
        'investigation_value':[r for r in records if r['category']=='INVESTIGATION_VALUE'],
        'decision_value':[r for r in records if r['category']=='DECISION_VALUE'],
        'unverified_potential_value':[r for r in records if r['category']=='UNVERIFIED_POTENTIAL_VALUE'],
        'counterfactual_values':[r['value_id'] for r in energy+economic+records if r['value_status'] in {'POTENTIAL_VALUE','ESTIMATED_AVOIDED_VALUE'}],
        'realized_values':[r['value_id'] for r in records if r['value_status']=='REALIZED_VALUE'],
        'capture_costs_and_constraints':{'candidate_actions':deepcopy(state.get('candidate_actions',[])),
            'operational_constraints':deepcopy(state.get('operational_constraints',[]))},
        'information_value':[{'decision_id':d['decision_id'],**deepcopy(d['evidence_acquisition'])} for d in state.get('decisions',[]) if d.get('decision')=='INVESTIGATE_FIRST'],
        'relationships':relations,'action_relationships':deepcopy(state.get('relationships',[])),
        'limitations':list(extension.get('limitations',[]))+['Aucun total transversal ; les catégories et contrefactuels ne sont pas interchangeables.', 'Provenance vérifiée ne signifie pas causalité démontrée.'],
        'provenance':{'canonical_state':'investigation/economic_decision_state.json','numeric_source_policy':'persisted_goal_b_measurements_or_economic_inputs_or_scenario_assumptions'},
        'aggregation_policy':'NO_CROSS_CATEGORY_TOTAL','total_value':None,'agent_decision':None}


def validate_append_only(old, new):
    """Keep every earlier estimate; post-action results append, never rewrite history."""
    previous={r['value_id']:r for r in old.get('records',[])}
    current={r['value_id']:r for r in new.get('records',[])}
    if any(current.get(k)!=v for k,v in previous.items()):raise ValueError('Estimations Value Map immuables : conserver l’entrée initiale et ajouter une nouvelle entrée.')


def load_value_map(case):
    from pathlib import Path
    case=Path(case)
    state=_read(case/'investigation/economic_decision_state.json')
    return build_value_map(case,state)


def client_value_section(value_map):
    """Client projection: labels attach to numbers; no computed global ROI or saving."""
    def display(values,unit):
        return f"{values['LOW']:g}–{values['HIGH']:g} {unit} (base : {values['BASE']:g})"
    items=[]
    for energy in value_map['direct_energy_value']:
        if 'effect' in energy:
            effect=energy['effect']
            lines=['Effet énergétique potentiel : '+display(effect['scenarios'],effect['unit']),
                   'Économie récupérable : à confirmer.']
        elif energy.get('energy_observation'):
            q=energy['energy_observation']['quantity']
            label='Hypothèse de scénario' if q['scenario_only'] or energy['energy_observation']['basis'] in {'ENGINEERING_ASSUMPTION','SCENARIO_ESTIMATE'} else 'Écart énergétique documenté'
            lines=[label+' : '+display(q['values'],q['unit']), 'Cet écart ne prouve pas une économie récupérable.']
        else:
            continue
        items.append({'value_ref':energy['value_id'],'lines':lines})
    for record in value_map['investigation_value']+value_map['decision_value']+value_map['unverified_potential_value']:
        if record['source_status']=='UNKNOWN':continue
        lines=[]
        counts=record['hypothesis_counts']
        if counts['rejected'] is not None:lines.append(f"Hypothèses éliminées : {counts['rejected']}.")
        for field,label in [('initial_search_scope','Périmètre initial'),('final_search_scope','Périmètre après investigation'),
                            ('decision_before','Décision avant'),('decision_after','Décision après')]:
            if record.get(field):lines.append(label+' : '+('; '.join(record[field]) if isinstance(record[field],list) else record[field]))
        time=record['time_calculation']
        if time['time_saved_hours'] is not None:
            label='Scénario hypothétique' if time.get('scenario_only') else 'Estimation documentée du contrefactuel'
            lines.append('Temps potentiellement évité : '+display(time['time_saved_hours'],'h')+' — '+label+'.')
            if time['time_value_eur'] is not None:
                label='hypothétique' if time['monetization_status']=='SCENARIO_ONLY' else 'documentée'
                lines.append('Valorisation du temps '+label+' : '+display(time['time_value_eur'],'EUR')+' ; ce n’est pas une économie réalisée.')
        for action in record.get('avoided_action_calculations') or []:
            lines.append('Intervention évitée : '+('documentée' if action['action_avoided']=='documented' else 'non démontrée')+'.')
            if action['cost_avoided_eur'] is not None:
                lines.append('Coût potentiellement évité'+(' (hypothèse)' if action['scenario_only'] else ' (estimation)')+' : '+display(action['cost_avoided_eur'],'EUR')+'.')
        leads=record.get('false_leads_avoided') or []
        for lead in ([leads] if isinstance(leads,str) else leads):
            lines.append('Fausse piste écartée : '+lead)
        if record['source_status']=='SCENARIO_ASSUMPTION'  or record['category']=='UNVERIFIED_POTENTIAL_VALUE':lines.insert(0,'Valeur hypothétique, non démontrée.')
        if lines:items.append({'value_ref':record['value_id'],'lines':lines})
    for record in (value_map['direct_energy_value']+value_map['direct_economic_value']+
                   value_map['investigation_value']+value_map['decision_value']):
        result=record.get('post_action_result')
        if not result:continue
        lines=['Résultat observé après action ; distinct de l’estimation initiale.']
        for key,label in [('energy_reduction_kwh','Baisse énergétique observée'),('actual_intervention_cost_eur','Coût réel de l’intervention'),
                          ('actual_time_spent_hours','Temps réellement passé'),('observed_saving_eur','Économie observée après action, selon la comparaison documentée')]:
            q=result['measurements'][key]
            if q is not None:lines.append(label+' : '+display(q['values'],q['unit']))
        items.append({'value_ref':record['value_id'],'lines':lines})
    return {'title':'Valeur de l’investigation' ,'items':items,'total_value':None,
            'notice':'Les composantes sont présentées séparément et ne sont pas additionnées.'}


def value_map_digest(value_map):
    import hashlib
    import json
    return hashlib.sha256(json.dumps(value_map,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def validate_value_map_human_review(case, human_review):
    """Bind existing human approval to this exact map, including estimates and results."""
    from pathlib import Path
    case=Path(case);state=_read(case/'investigation/economic_decision_state.json')
    if not state.get('value_assessment'):return
    expected=build_value_map(case,state)
    artifact=case/'investigation/value_map.json'
    if not artifact.exists() or _read(artifact)!=expected:
        raise ValueError('value_map.json absent ou différent de sa projection canonique.')
    if human_review.get('value_map_sha256')!=value_map_digest(expected):
        raise ValueError('Revue humaine Value Map absente ou périmée : value_map_sha256 requis.')
