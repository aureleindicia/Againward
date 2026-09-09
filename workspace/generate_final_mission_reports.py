"""Four explicitly authored synthetic editorial plans. Not a detector benchmark.

Uses the existing executable Goal A/B fixtures; financial assumptions are unchanged.
No real consent, client feedback or human approval is fabricated by this generator.
"""
from pathlib import Path
import argparse
import copy
import json
import shutil

from workspace.generate_goal_c_1_fixtures import generate
from operational_economics import record_goal_b_evidence, persist_economic_packet
from value_map import client_value_section
from report_design import SCHEMA, render_designed_report


def block(ref,kind='FINDING',x=45,y=80,w=500,h=150,size=11,emphasis='NORMAL'):
    return {'component':kind,'content_ref':ref,'box':[x,y,w,h],'font_size':size,'emphasis':emphasis}


def page(intent,*blocks):return {'intent':intent,'blocks':list(blocks)}


def main(output):
    root=Path(output)
    if root.exists():raise FileExistsError('Choose a new synthetic output directory.')
    cases=generate(root)
    fourth=root/'abstention_case';shutil.copytree(cases['C-E'],fourth)
    chosen={'clear_energy':cases['C-A'],'false_lead':cases['C-E'],
            'multiple_priorities':cases['C-MULTI'],'useful_abstention':fourth}
    results={}
    for key,case in chosen.items():
        path=case/'outputs/client_report/CLIENT_REPORT_MODEL.json';model=json.loads(path.read_text())
        model['metadata']['site_name']={'clear_energy':'Atelier des Rives — cas synthétique',
            'false_lead':'Manufacture du Parc — cas synthétique','multiple_priorities':'Production des Vallons — cas synthétique',
            'useful_abstention':'Atelier de la Plaine — cas synthétique'}[key]
        model['metadata']['report_title']='Performance énergétique et décisions opérationnelles'
        model['technical_appendix']['method']='Comparaison des régimes disponibles, examen des explications concurrentes et scénarios économiques conservés séparément.'
        model['technical_appendix']['limitations']=['La cause physique et la récupérabilité des écarts exigent une vérification opérationnelle.',
            'Les résultats de cet exemple synthétique illustrent le format de restitution, pas une validation terrain.']
        for chart in model['charts']:
            chart['finding_refs']=model['decision_cards'][0]['claim_refs']['finding_ids'] if model['decision_cards'] else []
        # Agent-authored wording tied to the unchanged finding/decision contracts.
        # Do not claim the illustrative chart alone proves recurrence.
        for card in model['decision_cards']:
            aid=card['action_ref']
            observation='Un écart récurrent subsiste dans les périodes comparables.'
            if aid.endswith('-CHECK'):
                observation+=' Le coût de l’investissement impose de vérifier la cause avant engagement.'
            elif aid.endswith('-MONITOR'):
                observation+=' La décision retenue est de suivre son évolution.'
            elif aid.endswith('-OPS'):
                observation+=' Une modification des horaires compromettrait la fraîcheur des produits.'
            else:
                observation+=' Le scénario économique soutient une correction ciblée, sous réserve du service à préserver.'
            uncertainty='Une charge évitable et un service utile non documenté restent des explications compatibles. La cause physique n’est pas identifiée.'
            for field,text in [('what_we_found',observation),('uncertainty',uncertainty)]:
                card[field]=text;card['claims'][field]['text']=text
        selected=list(dict.fromkeys(f for c in model['decision_cards'] for f in c['claim_refs']['finding_ids']))
        design={'schema_version':SCHEMA,'selected_findings':selected,'omitted_actions':{},'pages':[]}
        if key=='clear_energy':
            aid=model['decision_cards'][0]['action_ref']
            model['decision_cards'][0]['headline']='Un écart récurrent à traiter avec méthode'
            model['executive_summary']['message']='Un écart récurrent mérite une action ciblée. Le potentiel économique justifie la vérification opérationnelle ; il ne constitue pas encore une économie réalisée.'
            design['pages']=[
                page('EXECUTIVE_SUMMARY',block('cover','COVER',h=140,size=14,emphasis='PRIMARY'),
                    block('executive','EXECUTIVE_SUMMARY',y=255,h=150,size=13),
                    block(aid+':economics','ECONOMIC_RANGE',y=440,h=240,size=13),
                    block('notice','METHODOLOGY',y=710,h=65,size=9,emphasis='QUIET')),
                page('FINDING',block(aid+':what_we_found',y=75,h=125,size=12,emphasis='PRIMARY'),
                    block('chart:CHART-01','EVIDENCE_CHART',y=215,h=390,size=9),
                    block(aid+':uncertainty','LIMITATION',y=630,h=120)),
                page('DECISION',block(aid+':decision','DECISION',y=80,h=140,size=16,emphasis='PRIMARY'),
                    block(aid+':next_step','NEXT_STEP',y=250,h=210,size=12),
                    block('limitations','LIMITATION',y=495,h=130),block('method','METHODOLOGY',y=660,h=110,size=10))]
        elif key=='multiple_priorities':
            model['executive_summary']['message']='Agir sur la piste la plus concrète, vérifier avant un investissement important et préserver les contraintes de production. Les potentiels présentés ne doivent pas être additionnés.'
            design['pages']=[page('EXECUTIVE_SUMMARY',block('cover','COVER',h=140,size=14,emphasis='PRIMARY'),
                block('executive','EXECUTIVE_SUMMARY',y=270,h=160,size=14),
                block('limitations','LIMITATION',y=475,h=160),block('notice','METHODOLOGY',y=695,h=80,size=9))]
            for card in model['decision_cards'][:2]:
                aid=card['action_ref']
                design['pages'].append(page('FINDING',block(aid+':what_we_found',y=80,h=150,size=13,emphasis='PRIMARY'),
                    block(aid+':decision','DECISION',y=245,h=110,size=12),
                    block(aid+':economics','ECONOMIC_RANGE',y=385,h=180,size=11),
                    block(aid+':uncertainty','LIMITATION',y=610,h=145)))
            monitor,ops=[c['action_ref'] for c in model['decision_cards'][2:]]
            design['pages'].append(page('SECONDARY_FINDING',
                block(monitor+':what_we_found',y=75,h=110,size=12),block(monitor+':decision','DECISION',y=195,h=95),
                block(monitor+':uncertainty','LIMITATION',y=310,h=110,size=10),
                block(ops+':what_we_found',y=435,h=115,size=11),block(ops+':decision','DECISION',y=555,h=90,size=10),
                block(ops+':uncertainty','LIMITATION',y=655,h=100,size=10)))
            design['pages'].append(page('NEXT_STEP',block(ops+':constraints','LIMITATION',y=80,h=140,size=14,emphasis='PRIMARY'),
                block(model['decision_cards'][1]['action_ref']+':next_step','NEXT_STEP',y=255,h=215,size=12),
                block('method','METHODOLOGY',y=525,h=150,size=11)))
        else:
            model['charts']=[]
            if key=='false_lead':
                record_goal_b_evidence(case,{'evidence_id':'GBE-SYNTHETIC-REVIEW','evidence_type':'GOAL_B_DOCUMENT_RESPONSE',
                    'content':{'synthetic':True,'analysis_note':'La piste de dérive est rejetée dans ce scénario illustratif ; la production constitue une explication compatible.'}})
                state=json.loads((case/'investigation/economic_decision_state.json').read_text())
                state['value_assessment']={'records':[{'value_id':'V-REFUTATION','category':'INVESTIGATION_VALUE',
                    'phase':'PRE_ACTION_ESTIMATE','value_status':'OBSERVED_VALUE','source_status':'DOCUMENT_EXTRACTED',
                    'source_refs':['GBE-SYNTHETIC-REVIEW'],'finding_ids':[],
                    'hypotheses_considered':['drift','production'],'hypotheses_rejected':['drift'],'hypotheses_remaining':['production'],
                    'false_leads_avoided':['Intervention sur une dérive non démontrée'],
                    'initial_search_scope':'Causes énergétiques multiples','final_search_scope':'Effet de l’activité à conserver dans la comparaison',
                    'counterfactual_basis':'UNKNOWN'}]}
                vm=persist_economic_packet(case,state)['value_map'];model['investigation_value']=client_value_section(vm)
                model['executive_summary']['message']='La piste de dérive n’est pas suffisamment étayée. La valeur de l’analyse est ici d’écarter une intervention prématurée et de recentrer la comparaison sur l’activité.'
                model['no_action_items'][0]['title']='Ne pas engager une correction non justifiée'
                model['no_action_items'][0]['claim']['text']='Aucune dérive indépendante de l’activité n’est démontrée dans le scénario étudié.'
                model['no_action_items'][0]['explanation']=model['no_action_items'][0]['claim']['text']
                design['pages']=[page('EXECUTIVE_SUMMARY',block('cover','COVER',h=140,size=14,emphasis='PRIMARY'),
                    block('executive','EXECUTIVE_SUMMARY',y=260,h=185,size=14),block('no_action:0','DECISION',y=490,h=160,size=13),
                    block('notice','METHODOLOGY',y=700,h=75,size=9)),
                    page('INVESTIGATION_VALUE',block('value:V-REFUTATION','INVESTIGATION_VALUE',y=80,h=315,size=13,emphasis='PRIMARY'),
                        block('limitations','LIMITATION',y=440,h=150),block('method','METHODOLOGY',y=640,h=130,size=10))]
            else:
                model['executive_summary']['message']='Les données disponibles ne permettent pas de recommander une intervention. Conserver une référence et reprendre l’analyse si les conditions d’exploitation changent.'
                model['no_action_items'][0]['title']='Une abstention justifiée'
                model['no_action_items'][0]['claim']['text']='Aucune action corrective n’est suffisamment étayée par le périmètre disponible.'
                model['no_action_items'][0]['explanation']=model['no_action_items'][0]['claim']['text']
                model['technical_appendix']['limitations']=['L’absence de résultat suffisamment étayé ne prouve pas l’absence de toute anomalie.',
                    'Les conclusions restent limitées à la période et aux régimes effectivement disponibles.']
                design['pages']=[page('EXECUTIVE_SUMMARY',block('cover','COVER',h=140,size=14,emphasis='PRIMARY'),
                    block('executive','EXECUTIVE_SUMMARY',y=255,h=180,size=14),block('no_action:0','DECISION',y=495,h=145,size=13),
                    block('notice','METHODOLOGY',y=710,h=65,size=9)),
                    page('LIMITATION',block('limitations','LIMITATION',y=95,h=225,size=15,emphasis='PRIMARY'),
                        block('checked:0','METHODOLOGY',y=365,h=145,size=12),block('method','METHODOLOGY',y=560,h=180,size=12))]
        path.write_text(json.dumps(model,ensure_ascii=False,indent=2))
        receipt=render_designed_report(case,model,path,design)
        results[key]={'case':str(case),**receipt}
    (root/'FINAL_MISSION_REPORTS.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    print(json.dumps(results,ensure_ascii=False,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output');main(parser.parse_args().output)
