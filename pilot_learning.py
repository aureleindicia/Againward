"""Explicit, authorized pilot-learning projections of Value Map, not market evidence."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from statistics import median

from operational_economics import _read
from value_map import build_value_map, _context, _refs, resolve_quantity

BOOL_METRICS = {'useful_finding','new_to_client','useful_negative_conclusion','concrete_decision',
                'appropriate_abstention','main_value_is_investigation','client_would_find_alone'}
NUMERIC_METRICS = {'hypotheses_eliminated','againward_human_hours','client_hours_potentially_avoided',
                   'energy_value_kwh_per_year','economic_value_eur_per_year',
                   'findings_total','findings_field_verified'}
QUESTIONS = {
    'useful_finding':'Un finding utile est-il documenté ?',
    'new_to_client':'Le résultat était-il nouveau pour le client ?',
    'useful_negative_conclusion':'Une conclusion négative a-t-elle été utile ?',
    'concrete_decision':'Une décision concrète a-t-elle changé ?',
    'appropriate_abstention':'Une abstention a-t-elle évité une conclusion non fondée ?',
    'main_value_is_investigation':'La valeur principale venait-elle de l’investigation plutôt que de l’énergie ?',
    'client_would_find_alone':'Le client aurait-il probablement trouvé seul ?',
}


def build_pilot_learning_review(case, assessment):
    """Resolve judgments against local evidence; missing answers remain unknown.

    No inference of 'useful', 'new', 'verified' or 'main value' from detector outputs.
    All such judgments must be supplied explicitly with evidence.
    """
    from energy_mvp.client_lifecycle import assert_workflow_action_allowed
    assert_workflow_action_allowed(case, 'pilot_learning')
    case=Path(case);state=_read(case/'investigation/economic_decision_state.json')
    ctx=_context(case,state);vm=build_value_map(case,state)
    allowed=BOOL_METRICS|{'investigation_value_ref','energy_value_ref','economic_value_ref',
        'againward_hours_refs','field_verified_finding_ids','field_verification_source_refs',
        'primary_contribution','uncaptured_value'}
    if not isinstance(assessment,dict) or set(assessment)-allowed:raise ValueError('Pilot learning : champs inconnus.')
    metrics={key:None for key in BOOL_METRICS|NUMERIC_METRICS};provenance={}
    for key in BOOL_METRICS:
        answer=assessment.get(key)
        if answer is None:continue
        if not isinstance(answer,dict) or set(answer)!={'value','source_refs'} or not isinstance(answer['value'],bool):raise ValueError('Jugement de pilote booléen et sourcé requis.')
        _refs(answer['source_refs'],ctx['source_refs'],key,True)
        metrics[key]=answer['value'];provenance[key]=answer['source_refs']
    metrics['findings_total']=len(ctx['findings'])
    verified=assessment.get('field_verified_finding_ids')
    if verified is not None:
        _refs(verified,ctx['finding_refs'],'Findings vérifiés')
        _refs(assessment.get('field_verification_source_refs'),ctx['source_refs'],'Vérification terrain',True)
        if len(set(verified))!=len(verified):raise ValueError('Finding terrain dupliqué.')
        metrics['findings_field_verified']=len(verified)
        provenance['findings_field_verified']=assessment['field_verification_source_refs']
    if assessment.get('investigation_value_ref'):
        selected=[r for r in vm['investigation_value'] if r['value_id']==assessment['investigation_value_ref']]
        if len(selected)!=1:raise ValueError('Valeur d’investigation absente.')
        record=selected[0]
        if record['source_status'] not in {'UNKNOWN','SCENARIO_ASSUMPTION'}:
            metrics['hypotheses_eliminated']=record['hypothesis_counts']['rejected']
            t=record['time_calculation']
            if t.get('documented_estimate') and t['time_saved_hours'] is not None:
                metrics['client_hours_potentially_avoided']=t['time_saved_hours']['BASE']
        provenance['investigation_value_ref']=record['value_id']
    hours=resolve_quantity(assessment.get('againward_hours_refs'),ctx,'h')
    if hours and not hours['scenario_only']:
        metrics['againward_human_hours']=hours['values']['BASE'];provenance['againward_human_hours']=hours['source_refs']
    # A designated component, never the sum of overlapping map components.
    if assessment.get('energy_value_ref'):
        selected=[r for r in vm['direct_energy_value'] if r['value_id']==assessment['energy_value_ref']]
        if len(selected)!=1 or 'effect' not in selected[0]:raise ValueError('Effet annuel explicite requis pour cette métrique.')
        effect=selected[0]['effect'];metrics['energy_value_kwh_per_year']=effect['scenarios']['BASE']*(1000 if effect['unit']=='MWh/year' else 1)
        provenance['energy_basis']=effect['basis'];provenance['energy_value_ref']=selected[0]['value_id']
    if assessment.get('economic_value_ref'):
        selected=[r for r in vm['direct_economic_value'] if r['value_id']==assessment['economic_value_ref']]
        if len(selected)!=1 or 'calculation' not in selected[0]:raise ValueError('Calcul économique explicite requis.')
        calc=selected[0]['calculation']
        if calc['currency']!='EUR':raise ValueError('Pas de conversion implicite de devise.')
        metrics['economic_value_eur_per_year']=calc['scenarios']['BASE']['net_annual_benefit']
        provenance['economic_basis']=calc['reproducibility']['energy_effect']['basis']
        provenance['economic_value_ref']=selected[0]['value_id']
    contribution=assessment.get('primary_contribution')
    if contribution is not None:
        if not isinstance(contribution,dict) or contribution.get('value') not in {'DETECTED','QUANTIFIED','REFUTED','PRIORITIZED','UNKNOWN'}:raise ValueError('Contribution inconnue.')
        _refs(contribution.get('source_refs'),ctx['source_refs'],'Contribution',True)
    uncaptured=assessment.get('uncaptured_value')
    if uncaptured is not None:
        if not isinstance(uncaptured,dict) or not isinstance(uncaptured.get('text'),str):raise ValueError('Valeur non capturée : réflexion sourcée requise.')
        _refs(uncaptured.get('source_refs'),ctx['source_refs'],'Valeur non capturée',True)
    return {'schema_version':'againward-pilot-learning-v1','metrics':metrics,'provenance':provenance,
        'primary_contribution':contribution,'uncaptured_value':uncaptured,
        'judgments_are_not_automatic_facts':True,'technical_confidence_is_not_economic_confidence':True,
        'value_map_ref':'investigation/value_map.json','energy_and_economic_values_are_potential_not_realized':True}


def render_pilot_learning_review(review):
    lines=['# PILOT_LEARNING_REVIEW','', 'Les réponses ci-dessous sont documentées ou inconnues ; elles ne prouvent pas la valeur commerciale générale.','']
    for key,question in QUESTIONS.items():
        value=review['metrics'][key]
        lines.extend([f'- {question} '+('UNKNOWN' if value is None else ('Oui, selon la source citée' if value else 'Non, selon la source citée')),
                      '  Source : '+', '.join(review['provenance'].get(key,[]) or ['UNKNOWN'])])
    for key in sorted(NUMERIC_METRICS):
        lines.append(f'- {key} : '+('UNKNOWN' if review['metrics'][key] is None else str(review['metrics'][key])))
    lines+=['','Les montants désignent un composant sélectionné, sans somme transversale. Les heures client restent contrefactuelles.',
            'Contribution principale : '+json.dumps(review.get('primary_contribution'),ensure_ascii=False),
            'Valeur encore mal capturée : '+json.dumps(review.get('uncaptured_value'),ensure_ascii=False)]
    return '\n'.join(lines)+'\n'


def export_authorized_pilot_metrics(review, *, authorization, pilot_id):
    """Return a closed, content-free metric record only after explicit deidentification review.

    Caller must store the authorization locally. No client paths, sources or prose exported.
    This validates declarations, not whether a human actually consented.
    """
    if (authorization.get('authorized') is not True or authorization.get('deidentification_reviewed') is not True
            or not authorization.get('authorization_ref') or not authorization.get('reviewer')):
        raise ValueError('Agrégation exige autorisation et revue de désidentification explicites.')
    if not isinstance(pilot_id,str) or not re.fullmatch(r'PILOT-[0-9a-f]{16,32}',pilot_id):raise ValueError('Identifiant opaque requis.')
    metrics=review['metrics']
    if set(metrics)!=BOOL_METRICS|NUMERIC_METRICS:raise ValueError('Schéma de métriques fermé requis.')
    for key,value in metrics.items():
        if value is None:continue
        if key in BOOL_METRICS and not isinstance(value,bool):raise ValueError('Métrique booléenne invalide.')
        if key in NUMERIC_METRICS and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value)):
            raise ValueError('Métrique numérique invalide.')
    _validate_export_metrics(metrics)
    token=hashlib.sha256(json.dumps(authorization,sort_keys=True).encode()).hexdigest()
    return {'schema_version':'againward-authorized-pilot-metrics-v1','pilot_id':pilot_id,
        'authorized':True,'deidentified':True,'authorization_sha256':token,'metrics':dict(metrics),
        'energy_basis':review['provenance'].get('energy_basis','UNKNOWN'),
        'economic_basis':review['provenance'].get('economic_basis','UNKNOWN')}


def aggregate_pilot_metrics(records):
    ids=[r.get('pilot_id') for r in records]
    if len(set(ids))!=len(ids):raise ValueError('Un pilote ne peut être compté deux fois.')
    for r in records:
        _validate_export_metrics(r.get('metrics',{}))
        if r.get('schema_version')!='againward-authorized-pilot-metrics-v1' or r.get('authorized') is not True or r.get('deidentified') is not True or not r.get('authorization_sha256'):
            raise ValueError('Export pilote non autorisé.')
    metrics={}
    for key in BOOL_METRICS|NUMERIC_METRICS:
        values=[r['metrics'][key] for r in records if r['metrics'][key] is not None]
        detail={'known':len(values),'unknown':len(records)-len(values)}
        if key in BOOL_METRICS:detail['percent']=None if not values else 100*sum(values)/len(values)
        elif key not in {'energy_value_kwh_per_year','economic_value_eur_per_year'}:detail['median']=median(values) if values else None
        else:
            basis='energy_basis' if key.startswith('energy_') else 'economic_basis'
            groups={}
            for r in records:
                if r['metrics'][key] is not None:groups.setdefault(r[basis],[]).append(r['metrics'][key])
            detail['medians_by_basis']={k:{'n':len(v),'median':median(v)} for k,v in groups.items()}
        metrics[key]=detail
    verified=[r for r in records if r['metrics']['findings_field_verified'] is not None]
    denominator=sum(r['metrics']['findings_total'] for r in verified)
    return {'pilots':len(records),'metrics':metrics,
        'field_verified_findings_percent':None if not denominator else 100*sum(r['metrics']['findings_field_verified'] for r in verified)/denominator,
        'commercial_conclusion':None,'limitations':['Descriptif seulement ; petit échantillon, sélection et valeurs manquantes interdisent une généralisation automatique.',
            'Médianes énergie/argent stratifiées par base, potentiels et non économies réalisées.']}


def _validate_export_metrics(metrics):
    if not isinstance(metrics,dict) or set(metrics)!=BOOL_METRICS|NUMERIC_METRICS:
        raise ValueError('Schéma fermé de métriques requis.')
    for key,value in metrics.items():
        if value is None:continue
        if key in BOOL_METRICS:
            if not isinstance(value,bool):raise ValueError('Métrique booléenne invalide.')
        elif isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value):
            raise ValueError('Métrique numérique invalide.')
        elif key!='economic_value_eur_per_year' and value<0:
            raise ValueError('Compte, temps ou énergie négative invalide.')
    total=metrics['findings_total'];verified=metrics['findings_field_verified']
    if total is None or not isinstance(total,int) or (verified is not None and (not isinstance(verified,int) or verified>total)):
        raise ValueError('Nombre de findings vérifiés incohérent.')
