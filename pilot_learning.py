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
VALUE_BASES = {'UNKNOWN','DIRECTLY_MEASURED_HISTORICAL_EXCESS','COUNTERFACTUAL_ESTIMATE',
               'MODELED_REDUCTION','ENGINEERING_ASSUMPTION','SCENARIO_ESTIMATE'}
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
        'primary_contribution','uncaptured_value','post_mortem'}
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
    scientific=None if assessment.get('post_mortem') is None else _scientific_review(case,assessment['post_mortem'],ctx,metrics)
    return {'schema_version':'againward-pilot-learning-v1','metrics':metrics,'provenance':provenance,
        'classification':'TEMPORARY_CONFIDENTIAL','case_ref':str(case.resolve()),'scientific_post_mortem':scientific,
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
    scientific=review.get('scientific_post_mortem')
    lines[2:2]=['Classification : TEMPORARY_CONFIDENTIAL — purge avec le dossier sauf dérivé explicitement autorisé.', '']
    if scientific:
        def add_statement(item):
            lines.append('- ['+item['statement_type']+'] '+item['text'])
            lines.append('  Sources : '+', '.join(item.get('source_refs',[])+item.get('finding_refs',[])+list(item.get('artifact_sha256',{}))))
            if item.get('resolved_metric'):lines.append('  Résultat référencé : '+json.dumps(item['resolved_metric'],ensure_ascii=False))
        for key in POST_MORTEM_SECTIONS:
            lines.extend(['','## '+key,''])
            for item in scientific['sections'][key]:add_statement(item)
        for key,question in MANDATORY_QUESTIONS.items():
            lines.extend(['','## '+question,'']);add_statement(scientific['mandatory_answers'][key])
        simplicity=scientific.get('simplicity_counterfactual')
        if simplicity:
            labels={
                'raw_plus_python':'Raw data + Python + bon prompt',
                'tool_value':'Valeur des outils Againward',
                'workflow_friction':'Étapes du workflow qui ont contraint ou ralenti',
                'deterministic_python':'Calculs à confier au Python déterministe simple',
                'architecture_rationalization':'Briques à supprimer, fusionner ou rendre optionnelles',
                'unique_againward_capability':'Ce qu’Againward a permis de ne pas rater',
                'architecture_workarounds':'Contournements ou compensations de l’agent',
                'minimal_design':'Design minimal recommandé pour un dossier similaire',
            }
            lines.extend(['','## Comparaison contrefactuelle de simplicité',''])
            for key,label in labels.items():
                assessment=simplicity[key]
                lines.extend(['### '+label+' : '+assessment['outcome'],''])
                for item in assessment['evidence']:add_statement(item)
            lines.extend(['','### Dimensions comparées',''])
            for key,assessment in simplicity['dimensions'].items():
                lines.extend(['#### '+key+' : '+assessment['outcome'],''])
                for item in assessment['evidence']:add_statement(item)
            lines.extend(['','### Verdict : '+simplicity['verdict']['classification'],''])
            for item in simplicity['verdict']['rationale']:add_statement(item)
        lines.extend(['','## Verdict : '+scientific['verdict']['classification'],''])
        for key in ('arguments_for','arguments_against','new_elements','known_elements','generalization_limits'):
            lines.extend(['','### '+key,''])
            for item in scientific['verdict'][key]:add_statement(item)
    return '\n'.join(lines)+'\n'


def export_authorized_pilot_metrics(review, *, authorization, pilot_id):
    """Return a closed, content-free metric record only after explicit deidentification review.

    Caller must store the authorization locally. No client paths, sources or prose exported.
    This validates declarations, not whether a human actually consented.
    """
    from energy_mvp.contract_policy import assert_contract_permission
    if not review.get('case_ref'):
        raise ValueError('Export learning exige son dossier canonique ; aucune autorisation détachée.')
    assert_contract_permission(review['case_ref'], operation='retention', purpose='INTERNAL_RND')
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
    if any(review['provenance'].get(key,'UNKNOWN') not in VALUE_BASES for key in ('energy_basis','economic_basis')):
        raise ValueError('Base de valeur hors vocabulaire fermé ; aucun texte client exportable.')
    token=hashlib.sha256(json.dumps(authorization,sort_keys=True).encode()).hexdigest()
    return {'schema_version':'againward-authorized-pilot-metrics-v1','pilot_id':pilot_id,
        'authorized':True,'deidentified':True,'authorization_sha256':token,'metrics':dict(metrics),
        'energy_basis':review['provenance'].get('energy_basis','UNKNOWN'),
        'economic_basis':review['provenance'].get('economic_basis','UNKNOWN')}


def aggregate_pilot_metrics(records):
    ids=[r.get('pilot_id') for r in records]
    if len(set(ids))!=len(ids):raise ValueError('Un pilote ne peut être compté deux fois.')
    for r in records:
        if (set(r)!={'schema_version','pilot_id','authorized','deidentified','authorization_sha256','metrics','energy_basis','economic_basis'}
                or not isinstance(r.get('pilot_id'),str) or not re.fullmatch(r'PILOT-[0-9a-f]{16,32}',r['pilot_id'])
                or any(r.get(k) not in VALUE_BASES for k in ('energy_basis','economic_basis'))):
            raise ValueError('Export pilote : schéma fermé et identifiant opaque requis.')
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


POST_MORTEM_SECTIONS = (
    'experimental_context', 'data_quality', 'findings', 'rejected_hypotheses',
    'abstentions', 'investigation_performance', 'value_produced',
    'evidence_plane_introspection', 'agent_introspection', 'detection_introspection',
    'quantification_introspection', 'economic_plane_introspection',
    'contribution_relevance', 'generalization', 'main_limitations_source',
    'project_verdict', 'falsification', 'proposed_changes', 'do_not_change',
    'next_pilot_questions',
)
STATEMENT_TYPES = {'FAIT_OBSERVE','RESULTAT_CALCULE','RETOUR_CLIENT','INFERENCE',
                   'HYPOTHESE','INTERPRETATION_POST_MORTEM','INCONNU'}
PILOT_VERDICTS = {'RENFORCE_FORTEMENT','RENFORCE','NEUTRE','AFFAIBLIT','AFFAIBLIT_FORTEMENT'}
MANDATORY_QUESTIONS = {
    'without_againward': 'Si AGAINWARD n’existait pas, quelle partie exacte de cette conclusion aurait réellement été difficile à obtenir ?',
    'general_capacity': 'Ce pilote démontre-t-il une capacité générale d’AGAINWARD ou seulement une réussite spécifique à ce dataset ?',
    'limits_origin': 'Les limites observées viennent-elles principalement du moteur, de l’agent, de l’architecture, d’une information physiquement absente, de données de mauvaise qualité, du choix du client, ou de la formulation de la question ?',
}
CONTRIBUTION_DIMENSIONS = {'OBVIOUS_OBSERVATION','REPETITIVE_CALCULATION','DIFFICULT_COMPARISON',
    'CONFOUNDER_ELIMINATION','FALSIFICATION','HYPOTHESIS_SPACE_REDUCTION','QUANTIFICATION','DECISION','UNKNOWN'}
SIMPLICITY_VERDICTS = {'AGAINWARD_CLEARLY_BETTER','AGAINWARD_BETTER_ON_RELIABILITY',
    'ROUGHLY_EQUIVALENT','RAW_PLUS_PYTHON_LIKELY_BETTER','INCONCLUSIVE'}
SIMPLICITY_DIMENSIONS = ('discovery_and_investigation','calculation_reliability',
    'false_positives_and_abstentions','traceability_and_reproducibility',
    'time_and_complexity','final_client_value')
SIMPLICITY_DIMENSION_OUTCOMES = {'AGAINWARD_ADVANTAGE','RAW_PLUS_PYTHON_ADVANTAGE',
    'ROUGHLY_EQUIVALENT','INCONCLUSIVE'}


def _scientific_review(case, payload, ctx, metrics):
    """Validate an agent-authored post-mortem; do not choose a verdict or conclusion."""
    if not isinstance(payload,dict) or set(payload)!={'sections','mandatory_answers','contribution_dimensions','verdict','simplicity_counterfactual'}:
        raise ValueError('Post-mortem : sections, questions, comparaison de simplicité et verdict requis.')

    def statement(item):
        fields={'statement_type','text','source_refs','finding_refs','artifact_refs','metric_ref'}
        if not isinstance(item,dict) or set(item)-fields or item.get('statement_type') not in STATEMENT_TYPES:
            raise ValueError('Typologie explicite des énoncés requise.')
        text=item.get('text')
        if not isinstance(text,str) or not text.strip() or re.search(r'\d|€',text):
            raise ValueError('Énoncé qualitatif requis ; citer les métriques pour les nombres.')
        source_refs=_refs(item.get('source_refs',[]),ctx['source_refs'],'Source du post-mortem')
        finding_refs=_refs(item.get('finding_refs',[]),ctx['finding_refs'],'Finding du post-mortem')
        artifacts={}
        for relative in item.get('artifact_refs',[]):
            path=case/relative
            if (not isinstance(relative,str) or Path(relative).is_absolute() or '..' in Path(relative).parts
                    or path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(case.resolve())
                    or relative.startswith(('incoming/','raw/','contracts/'))):
                raise ValueError('Artefact de post-mortem absent ou non analytique.')
            artifacts[relative]=hashlib.sha256(path.read_bytes()).hexdigest()
        metric=item.get('metric_ref')
        if metric is not None and (metric not in metrics or metrics[metric] is None):
            raise ValueError('Métrique du post-mortem inconnue ; ne pas inventer de nombre.')
        kind=item['statement_type']
        if kind!='INCONNU' and not (source_refs or finding_refs or artifacts or metric):
            raise ValueError('Énoncé de post-mortem sans provenance.')
        if kind=='RESULTAT_CALCULE' and metric not in NUMERIC_METRICS:
            raise ValueError('Résultat calculé exige une métrique numérique canonique.')
        if kind=='RETOUR_CLIENT' and not set(source_refs)&ctx['client_statement_refs']:
            raise ValueError('Retour client exige une déclaration client persistée.')
        if kind=='INCONNU' and metric is not None:
            raise ValueError('INCONNU ne porte pas un chiffre connu.')
        return {**item,'artifact_sha256':artifacts,
                'resolved_metric':None if metric is None else {'name':metric,'value':metrics[metric]}}

    def simplicity_counterfactual(value):
        required = {
            'raw_plus_python', 'tool_value', 'workflow_friction', 'deterministic_python',
            'architecture_rationalization', 'unique_againward_capability',
            'architecture_workarounds', 'minimal_design', 'dimensions', 'verdict',
        }
        if not isinstance(value, dict) or set(value) != required:
            raise ValueError('Comparaison contrefactuelle de simplicité complète requise.')

        def assessed_axis(item):
            if (not isinstance(item, dict) or set(item) != {'outcome', 'evidence'}
                    or item['outcome'] not in SIMPLICITY_DIMENSION_OUTCOMES):
                raise ValueError('Chaque axe de simplicité exige un résultat fermé et des preuves.')
            evidence = item['evidence']
            if not isinstance(evidence, list) or not evidence:
                raise ValueError('Chaque axe de simplicité exige une conclusion sourcée.')
            resolved_evidence = [statement(entry) for entry in evidence]
            if not any(entry['statement_type'] != 'INCONNU' for entry in resolved_evidence):
                raise ValueError('Une conclusion de simplicité ne peut pas être seulement INCONNU.')
            return {'outcome': item['outcome'], 'evidence': resolved_evidence}

        resolved = {
            key: assessed_axis(value[key])
            for key in (
                'raw_plus_python', 'tool_value', 'workflow_friction',
                'deterministic_python', 'architecture_rationalization',
                'unique_againward_capability', 'architecture_workarounds', 'minimal_design',
            )
        }
        dimensions = value['dimensions']
        if not isinstance(dimensions, dict) or set(dimensions) != set(SIMPLICITY_DIMENSIONS):
            raise ValueError('Les six dimensions de comparaison sont requises.')
        resolved_dimensions = {key: assessed_axis(item) for key, item in dimensions.items()}
        verdict = value['verdict']
        if (not isinstance(verdict, dict) or set(verdict) != {'classification', 'rationale'}
                or verdict['classification'] not in SIMPLICITY_VERDICTS):
            raise ValueError('Verdict fermé de simplicité requis.')
        rationale = verdict['rationale']
        if not isinstance(rationale, list) or not rationale:
            raise ValueError('Le verdict de simplicité exige une justification sourcée.')
        resolved_rationale = [statement(item) for item in rationale]
        if not any(item['statement_type'] != 'INCONNU' for item in resolved_rationale):
            raise ValueError('Le verdict de simplicité ne peut pas être seulement INCONNU.')
        return {
            **resolved,
            'dimensions': resolved_dimensions,
            'verdict': {
                'classification': verdict['classification'],
                'rationale': resolved_rationale,
            },
        }

    sections=payload['sections']
    if not isinstance(sections,dict) or set(sections)!=set(POST_MORTEM_SECTIONS):
        raise ValueError('Les vingt dimensions du post-mortem sont requises ; INCONNU si nécessaire.')
    resolved={}
    for key,items in sections.items():
        if not isinstance(items,list) or not items:raise ValueError('Section vide : expliciter la limite.')
        resolved[key]=[statement(item) for item in items]
    answers=payload['mandatory_answers']
    if not isinstance(answers,dict) or set(answers)!=set(MANDATORY_QUESTIONS):
        raise ValueError('Les trois questions obligatoires doivent être traitées.')
    answers={key:statement(value) for key,value in answers.items()}
    simplicity=simplicity_counterfactual(payload['simplicity_counterfactual'])
    dimensions=payload['contribution_dimensions']
    if not isinstance(dimensions,list) or not dimensions or set(dimensions)-CONTRIBUTION_DIMENSIONS:
        raise ValueError('Nature de la contribution inconnue.')
    verdict=payload['verdict']
    if not isinstance(verdict,dict) or set(verdict)!={'classification','arguments_for','arguments_against','new_elements','known_elements','generalization_limits'} or verdict['classification'] not in PILOT_VERDICTS:
        raise ValueError('Verdict agent explicite et contradictoire requis.')
    validated={'classification':verdict['classification']}
    for key in set(verdict)-{'classification'}:
        if not isinstance(verdict[key],list) or not verdict[key]:raise ValueError('Arguments ou inconnus explicites requis.')
        validated[key]=[statement(item) for item in verdict[key]]
    return {'sections':resolved,'mandatory_answers':answers,'simplicity_counterfactual':simplicity,
            'contribution_dimensions':dimensions,'verdict':validated,
            'classification':'TEMPORARY_CONFIDENTIAL','general_validation_demonstrated':False}


def persist_pilot_learning_review(case_directory, assessment):
    """Store the existing review plus its scientific extension inside the client workspace."""
    from energy_mvp.workflow_paths import resolve_analysis_directory
    from operational_economics import _write
    case=Path(case_directory)
    review=build_pilot_learning_review(case,assessment)
    if review.get('scientific_post_mortem') is None:
        raise ValueError('Un post-mortem final doit traiter les vingt sections, les trois questions et la comparaison de simplicité.')
    target=resolve_analysis_directory(case)
    _write(target/'PILOT_LEARNING_REVIEW.json',review)
    (target/'PILOT_LEARNING_REVIEW.md').write_text(render_pilot_learning_review(review),encoding='utf-8')
    return review


RETENTION_SCHEMA = 'againward-learning-whitelist-v1'
RETENTION_FIELDS = tuple(sorted(BOOL_METRICS|NUMERIC_METRICS))+('energy_basis','economic_basis','purpose','schema_version')
RETENTION_BINS = {'UNKNOWN','NEGATIVE','ZERO','LT_10','10_TO_100','100_TO_1000','1000_TO_10000','GE_10000'}


def _generalized_metric(value):
    if value is None:return 'UNKNOWN'
    if value<0:return 'NEGATIVE'
    if value==0:return 'ZERO'
    for bound,label in ((10,'LT_10'),(100,'10_TO_100'),(1000,'100_TO_1000'),(10000,'1000_TO_10000')):
        if value<bound:return label
    return 'GE_10000'


def create_retention_candidate(case_directory, review, *, purpose='INTERNAL_RND'):
    """Project a closed, generalized CSV; never retain the free-form post-mortem."""
    import csv
    from energy_mvp.contract_policy import assert_contract_permission, contract_policy_digest
    from energy_mvp.workflow_paths import resolve_case_layout
    from operational_economics import _write
    root=resolve_case_layout(case_directory)['case_root']
    if not review.get('case_ref') or Path(review['case_ref']).resolve()!=root.resolve():
        raise ValueError('Dérivé et revue doivent appartenir au même dossier.')
    if purpose not in {'INTERNAL_RND','BENCHMARKING'}:
        raise ValueError('Projection learning limitée aux finalités R&D ou benchmark autorisées.')
    policy=assert_contract_permission(root,operation='retention',purpose=purpose)
    if policy is None:
        # Synthetic reports can exercise the projection, but cannot grant real reuse rights.
        policy_digest=None
    else:policy_digest=contract_policy_digest(policy)
    metrics=review['metrics'];_validate_export_metrics(metrics)
    row={key:('UNKNOWN' if metrics[key] is None else 'YES' if metrics[key] else 'NO') for key in BOOL_METRICS}
    row.update({key:_generalized_metric(metrics[key]) for key in NUMERIC_METRICS})
    for key in ('energy_basis','economic_basis'):
        row[key]=review['provenance'].get(key,'UNKNOWN')
        if row[key] not in VALUE_BASES:raise ValueError('Base de valeur hors whitelist.')
    row.update(purpose=purpose,schema_version=RETENTION_SCHEMA)
    target=root/'retained_derived/pilot_learning.csv'
    if target.exists():raise FileExistsError('Dérivé existant : aucune réécriture silencieuse.')
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('w',encoding='utf-8',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=RETENTION_FIELDS);writer.writeheader();writer.writerow(row)
    receipt={'status':'RETENTION_CANDIDATE','path':'retained_derived/pilot_learning.csv',
        'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'purpose':purpose,
        'whitelist_schema':RETENTION_SCHEMA,'contract_policy_sha256':policy_digest,
        'transformations':['DROP_ALL_FREE_TEXT','DROP_ALL_IDENTIFIERS','DROP_ALL_TIMESTAMPS','BIN_NUMERIC_METRICS'],
        'approved_for_long_term_retention':False}
    _write(root/'privacy/learning_retention_candidate.json',receipt)
    return receipt


from againward.compat.learning_retention import validate_retained_learning_projection


def approve_retention_candidate(case_directory, human_review):
    """Persist only an actual supplied review, bound to the projected bytes and contract."""
    from energy_mvp.contract_policy import assert_contract_permission, contract_policy_digest
    from energy_mvp.workflow_paths import resolve_case_layout
    from operational_economics import _write
    root=resolve_case_layout(case_directory)['case_root']
    candidate=_read(root/'privacy/learning_retention_candidate.json')
    if candidate.get('path')!='retained_derived/pilot_learning.csv':
        raise ValueError('Chemin de projection non canonique.')
    path=root/candidate['path']
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Projection hors dossier.')
    row=validate_retained_learning_projection(path)
    policy=assert_contract_permission(root,operation='retention',purpose=row['purpose'])
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if digest!=candidate['sha256'] or candidate['contract_policy_sha256']!=(None if policy is None else contract_policy_digest(policy)):
        raise ValueError('Candidat ou contrat modifié : nouvelle projection/revue requise.')
    required=('approved_for_long_term_retention','site_identity_removed','unique_asset_combinations_generalized',
              'volumes_generalized','timestamps_generalized','no_personal_data_remaining','no_forbidden_industrial_dimensions')
    if (not isinstance(human_review,dict) or any(human_review.get(k) is not True for k in required)
            or human_review.get('reidentification_risk')!='LOW' or not human_review.get('reviewer_role')
            or not human_review.get('reviewed_at_utc') or human_review.get('artifact_sha256')!={candidate['path']:digest}):
        raise ValueError('RETENTION_APPROVED exige une revue humaine complète, risque LOW et empreinte exacte.')
    result={**human_review,'status':'RETENTION_APPROVED','purpose':row['purpose'],
            'contract_policy_sha256':candidate['contract_policy_sha256'],'whitelist_schema':RETENTION_SCHEMA}
    _write(root/'privacy/derived_retention_review.json',result)
    return result
