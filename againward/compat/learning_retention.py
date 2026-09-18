"""Closed v1 learning-retention schema; compatibility, not analytical policy."""
from pathlib import Path

BOOL_METRICS = {'useful_finding','new_to_client','useful_negative_conclusion','concrete_decision',
                'appropriate_abstention','main_value_is_investigation','client_would_find_alone'}
NUMERIC_METRICS = {'hypotheses_eliminated','againward_human_hours','client_hours_potentially_avoided',
                   'energy_value_kwh_per_year','economic_value_eur_per_year',
                   'findings_total','findings_field_verified'}
VALUE_BASES = {'UNKNOWN','DIRECTLY_MEASURED_HISTORICAL_EXCESS','COUNTERFACTUAL_ESTIMATE',
               'MODELED_REDUCTION','ENGINEERING_ASSUMPTION','SCENARIO_ESTIMATE'}
RETENTION_SCHEMA = 'againward-learning-whitelist-v1'
RETENTION_FIELDS = tuple(sorted(BOOL_METRICS|NUMERIC_METRICS))+('energy_basis','economic_basis','purpose','schema_version')
RETENTION_BINS = {'UNKNOWN','NEGATIVE','ZERO','LT_10','10_TO_100','100_TO_1000','1000_TO_10000','GE_10000'}


def validate_retained_learning_projection(path):
    import csv
    path=Path(path)
    if path.suffix!='.csv':raise ValueError('Rétention learning : CSV whitelisté uniquement ; Markdown libre interdit.')
    with path.open(encoding='utf-8',newline='') as handle:
        reader=csv.DictReader(handle)
        if reader.fieldnames!=list(RETENTION_FIELDS):raise ValueError('Colonnes hors whitelist de rétention.')
        rows=list(reader)
    if len(rows)!=1:raise ValueError('Dérivé learning : une projection bornée par dossier.')
    row=rows[0]
    if (row['schema_version']!=RETENTION_SCHEMA or row['purpose'] not in {'INTERNAL_RND','BENCHMARKING'}
            or any(row[k] not in {'YES','NO','UNKNOWN'} for k in BOOL_METRICS)
            or any(row[k] not in RETENTION_BINS for k in NUMERIC_METRICS)
            or any(row[k] not in VALUE_BASES for k in ('energy_basis','economic_basis'))):
        raise ValueError('Valeur précise, texte libre ou finalité hors whitelist.')
    return row
