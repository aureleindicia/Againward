"""Three synthetic value-map examples, reusing existing Goal A/B/C fixture architecture.
No model performance, real client declaration, human delivery approval or market claim.
"""
from pathlib import Path
import argparse
import json

from workspace.generate_goal_c_1_fixtures import generate
from operational_economics import record_goal_b_evidence,persist_economic_packet
from value_map import build_value_map,client_value_section
from client_delivery import validate_client_report_model,render_client_report_pdf
from pilot_learning import build_pilot_learning_review,render_pilot_learning_review


def main(root):
    root=Path(root)
    if root.exists():raise FileExistsError('Use a new output directory.')
    cases=generate(root);result={}
    for key,title in [('C-A','quantified_energy'),('C-E','false_lead_no_energy_saving'),('C-H','energy_and_client_time')]:
        case=cases[key];path=case/'investigation/economic_decision_state.json';state=json.loads(path.read_text())
        finding_ids=[r['finding_id'] for r in state['technical_finding_refs']]
        record_goal_b_evidence(case,{'evidence_id':'GBE-VALUE-EXAMPLE','evidence_type':'GOAL_B_CLIENT_RESPONSE',
            'content':{'synthetic_example':True,'response_text':'Déclaration fictive pour validation du contrat uniquement.',
                       'measurements':{'people':{'value':2,'unit':'person'},'hours_low':{'value':4,'unit':'h'},'hours_base':{'value':5,'unit':'h'},'hours_high':{'value':7.5,'unit':'h'}}}})
        record={'value_id':'VALUE-INVESTIGATION','category':'INVESTIGATION_VALUE','phase':'PRE_ACTION_ESTIMATE',
            'value_status':'OBSERVED_VALUE','source_status':'CLIENT_EXPLICIT','source_refs':['GBE-VALUE-EXAMPLE'],
            'finding_ids':finding_ids,'counterfactual_basis':'UNKNOWN','provenance':{'source_refs':['GBE-VALUE-EXAMPLE'],'finding_refs':finding_ids},
            'hypotheses_considered':['production','weather','operation','measurement','equipment','schedule'],
            'hypotheses_rejected':['production','weather','measurement','schedule'],'hypotheses_remaining':['operation','equipment'],
            'initial_search_scope':'Ensemble du site','final_search_scope':'Consommateurs pendant arrêt',
            'technical_confidence':'NOT_CALIBRATED','economic_confidence':'NOT_CALIBRATED',
            'counterfactual_confidence':'NOT_CALIBRATED','realization_confidence':'NOT_CALIBRATED',
            'limitations':['Fixture de contrat ; ne valide pas une investigation indépendante.']}
        if key=='C-E':
            record.update(hypotheses_considered=['drift','production'],hypotheses_rejected=['drift'],hypotheses_remaining=['production'],
                final_search_scope='Variation expliquée par la production dans cet exemple',false_leads_avoided=['Intervention sur une dérive non démontrée'])
        if key=='C-H':
            record.update(value_status='ESTIMATED_AVOIDED_VALUE',counterfactual_basis='DIRECT_CLIENT_STATEMENT')
            record['time']={'people_count':{s:{'evidence_ref':'GBE-VALUE-EXAMPLE','measurement_key':'people'} for s in ('LOW','BASE','HIGH')},
                'hours_per_person':{s:{'evidence_ref':'GBE-VALUE-EXAMPLE','measurement_key':'hours_'+s.lower()} for s in ('LOW','BASE','HIGH')},
                'role':'Technicien','source_status':'CLIENT_EXPLICIT','counterfactual_status':'CLIENT_ESTIMATED','confidence':'LOW'}
        decision={'value_id':'VALUE-DECISION','category':'DECISION_VALUE','phase':'PRE_ACTION_ESTIMATE',
            'value_status':'OBSERVED_VALUE','source_status':'CLIENT_EXPLICIT','source_refs':['GBE-VALUE-EXAMPLE'],
            'finding_ids':finding_ids,'counterfactual_basis':'UNKNOWN','provenance':{'source_refs':['GBE-VALUE-EXAMPLE'],'decision_refs':[state['decisions'][0]['decision_id']]},
            'decision_before':'Investigation générale envisagée','decision_after':'Aucune intervention justifiée' if key=='C-E' else 'Validation ciblée de l’action enregistrée',
            'decision_that_changed':state['decisions'][0]['decision_id']}
        state['value_assessment']={'records':[record,decision],'limitations':['Aucune somme énergie, argent, temps ou décision.']}
        state=persist_economic_packet(case,state);vm=build_value_map(case,state)
        model_path=case/'outputs/client_report/CLIENT_REPORT_MODEL.json';model=json.loads(model_path.read_text())
        model['investigation_value']=client_value_section(vm);validate_client_report_model(model,case)
        model_path.write_text(json.dumps(model,ensure_ascii=False,indent=2))
        rendered=render_client_report_pdf(model,model_path,model_path.parent/'VALUE_MAP_REPORT.pdf',case_directory=case)
        review=build_pilot_learning_review(case,{'investigation_value_ref':'VALUE-INVESTIGATION'})
        (case/'investigation/PILOT_LEARNING_REVIEW.json').write_text(json.dumps(review,ensure_ascii=False,indent=2))
        (case/'investigation/PILOT_LEARNING_REVIEW.md').write_text(render_pilot_learning_review(review))
        result[title]={'case':str(case),'pdf':rendered,'value_map':str(case/'investigation/value_map.json'),
            'time_hours':vm['investigation_value'][0]['time_calculation']['time_saved_hours'],'total_value':vm['total_value']}
    (root/'VALUE_MAP_EXAMPLES.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output');main(parser.parse_args().output)
