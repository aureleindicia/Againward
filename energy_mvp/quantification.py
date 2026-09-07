"""Explicit energy estimands and conditional multi-baseline sensitivity, never savings."""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Mapping, Sequence

from .models import Reading
from .toolbox import calculate_residuals


def energy_deviation(observed_kw: Sequence[float], expected_kw: Sequence[float],
                     interval_hours: Sequence[float]) -> dict[str, Any]:
    """Separate signed balance from positive/negative exposure on identical intervals."""
    if not len(observed_kw) == len(expected_kw) == len(interval_hours) or not observed_kw:
        raise ValueError("Trois séries non vides de même longueur sont requises.")
    if any(not math.isfinite(v) for series in (observed_kw,expected_kw,interval_hours) for v in series):
        raise ValueError("Les valeurs doivent être finies.")
    if any(v < 0 for series in (observed_kw,expected_kw) for v in series) or any(h <= 0 for h in interval_hours):
        raise ValueError("Puissances non négatives et durées strictement positives requises.")
    deltas=[(a-b)*h for a,b,h in zip(observed_kw,expected_kw,interval_hours)]
    return {"signed_net_kwh":math.fsum(deltas),
        "positive_exposure_kwh":math.fsum(max(v,0) for v in deltas),
        "negative_exposure_kwh":math.fsum(max(-v,0) for v in deltas),
        "observed_energy_kwh":math.fsum(a*h for a,h in zip(observed_kw,interval_hours)),
        "expected_energy_kwh":math.fsum(b*h for b,h in zip(expected_kw,interval_hours)),
        "covered_hours":math.fsum(interval_hours), "decision":None,
        "recoverable_saving_kwh":None,
        "limitations":["La partie positive inclut la variabilité normale et n'est pas un excès net.",
                       "Un bilan net dépend du contrefactuel; aucun de ces nombres ne prouve la récupérabilité."]}


def quantify_baseline_sensitivity(
    readings: Sequence[Reading], baselines: Mapping[str,dict[str,Any]],
    *, assessments: Mapping[str,dict[str,Any]], expected_duration_hours: float,
) -> dict[str,Any]:
    """Compare defensible models over exactly the same observed target intervals.

    Analyst assessments must declare comparable_regime, defensible and rationale.
    These declarations remain auditable judgments, not mathematical proof of causality.
    The returned range is model sensitivity, NOT a statistical confidence interval.
    """
    if not math.isfinite(expected_duration_hours) or expected_duration_hours <= 0:
        raise ValueError("Durée de la fenêtre cible explicitement requise et positive.")
    if not baselines or set(assessments)!=set(baselines):
        raise ValueError("Chaque baseline exige une évaluation explicite.")
    result: dict[str,Any]={"status":"ABSTAIN", "estimate_kwh":None,
        "estimand":"signed_net_energy_difference_on_observed_intervals",
        "range_kind":"baseline_sensitivity_not_confidence_interval", "baselines":{},
        "reasons":[],"recoverable_saving_kwh":None,"decision":None}
    ordered=sorted(readings,key=lambda r:r.timestamp)
    if not ordered:
        result['reasons'].append('empty_target');return result
    if any(r.interval_hours is None or not math.isfinite(r.interval_hours) or r.interval_hours<=0 for r in ordered):
        raise ValueError("Durées cibles inconnues ou invalides.")
    for a,b in zip(ordered,ordered[1:]):
        if a.timestamp+timedelta(hours=a.interval_hours)>b.timestamp:
            raise ValueError("Intervalles cibles en chevauchement ou dupliqués.")
    hours=math.fsum(r.interval_hours for r in ordered)
    if hours > expected_duration_hours+1e-7:
        raise ValueError("Durée couverte supérieure à la fenêtre déclarée.")
    result['coverage_ratio']=hours/expected_duration_hours
    result['observed_hours']=hours
    result['missing_hours']=max(0,expected_duration_hours-hours)
    if result['coverage_ratio']<.9:result['reasons'].append('insufficient_target_coverage')
    values=[]
    for name,model in baselines.items():
        assessment=assessments[name]
        reasons=[]
        if (assessment.get('defensible') is not True or assessment.get('comparable_regime') is not True
                or not str(assessment.get('rationale','')).strip()):
            reasons.append('baseline_not_defended_by_analyst')
        end=model.get('validation_end') or model.get('calibration_end')
        if not end or datetime.fromisoformat(end)>=ordered[0].timestamp:
            reasons.append('target_not_after_reference_validation')
        if model.get('validation_coverage_ratio',1)<.9:
            reasons.append('insufficient_validation_support')
        residuals=calculate_residuals(ordered,model)
        if len(residuals)!=len(ordered):reasons.append('unsupported_target_rows')
        detail={'assessment':dict(assessment),'reasons':reasons,'supported_rows':len(residuals),
            'reference_validation_metrics':model.get('validation_metrics'), 'deviation':None}
        if not reasons:
            try:
                detail['deviation']=energy_deviation([p['observed_kw'] for p in residuals],
                    [p['expected_kw'] for p in residuals],[p['interval_hours'] for p in residuals])
                values.append(detail['deviation']['signed_net_kwh'])
            except ValueError:
                reasons.append('invalid_physical_prediction')
        result['baselines'][name]=detail
        result['reasons'].extend(f'{name}:{reason}' for reason in reasons)
    if result['reasons']:return result
    lo,hi=min(values),max(values)
    result['signed_sensitivity_kwh']={'low':lo,'high':hi}
    tolerance=1e-8*max(1,hours)
    if lo < -tolerance and hi > tolerance:
        result['reasons'].append('plausible_baselines_disagree_on_effect_direction')
    elif hi <= tolerance:
        result['status']='NO_POSITIVE_NET_EFFECT'
    elif lo <= tolerance:
        result['reasons'].append('positive_effect_not_robust_to_baseline')
    else:
        result['status']='CONDITIONAL_ESTIMATE' if hi-lo<=tolerance else 'BASELINE_SENSITIVITY_RANGE'
        result['estimate_kwh']={'low':lo,'high':hi}
    return result
