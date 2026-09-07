from dataclasses import replace
from datetime import datetime, timedelta
import math
import pytest
from energy_mvp.models import Reading
from energy_mvp.quantification import energy_deviation, quantify_baseline_sensitivity
from energy_mvp.toolbox import fit_linear_baseline, calculate_excess_energy, calculate_cost


def fixture():
    origin=datetime(2025,1,1)
    reference=[Reading(origin+timedelta(hours=i),10,power_kw=10,interval_hours=1) for i in range(100)]
    target=[replace(r,timestamp=r.timestamp+timedelta(days=30),power_kw=12,energy_kwh=12) for r in reference[:24]]
    return reference,target


def test_zero_signed_noise_is_not_positive_net_excess():
    d=energy_deviation([9,11]*48,[10]*96,[.25]*96)
    assert d['signed_net_kwh']==0
    assert d['positive_exposure_kwh']==d['negative_exposure_kwh']==12
    assert d['recoverable_saving_kwh'] is None

@pytest.mark.parametrize('value',[math.nan,math.inf,-math.inf])
def test_nonfinite_quantities_rejected(value):
    with pytest.raises(ValueError):energy_deviation([value],[10],[1])
    with pytest.raises(ValueError):calculate_excess_energy([10],[value],[1])
    with pytest.raises(ValueError):calculate_cost(value,.2)


def test_sensitivity_is_not_confidence_interval_or_saving():
    ref,target=fixture()
    first=fit_linear_baseline(ref,predictors=())
    second=fit_linear_baseline([replace(r,power_kw=11,energy_kwh=11) for r in ref],predictors=())
    models={'a':first,'b':second}
    assessments={n:{'defensible':True,'comparable_regime':True,'rationale':'Two separately justified reference periods'} for n in models}
    q=quantify_baseline_sensitivity(target,models,assessments=assessments,expected_duration_hours=24)
    assert q['status']=='BASELINE_SENSITIVITY_RANGE'
    assert q['estimate_kwh']['low']==pytest.approx(24)
    assert q['estimate_kwh']['high']==pytest.approx(48)
    assert q['range_kind']=='baseline_sensitivity_not_confidence_interval'
    assert q['recoverable_saving_kwh'] is None


def test_no_quantification_for_unsupported_or_in_sample_or_unjustified_baseline():
    ref,target=fixture();model=fit_linear_baseline(ref,predictors=())
    assess={'a':{'defensible':True,'comparable_regime':True,'rationale':'Comparable holdout'}}
    for target_data,assessment,duration in [(ref,assess,100),(target,{'a':{}},24),(target[:5],assess,24)]:
        q=quantify_baseline_sensitivity(target_data,{'a':model},assessments=assessment,expected_duration_hours=duration)
        assert q['status']=='ABSTAIN' and q['estimate_kwh'] is None


def test_disagreeing_baselines_force_abstention():
    ref,target=fixture()
    models={str(power):fit_linear_baseline([replace(r,power_kw=power) for r in ref],predictors=()) for power in [10,14]}
    assess={name:{'defensible':True,'comparable_regime':True,'rationale':'Physically plausible alternative reference'} for name in models}
    q=quantify_baseline_sensitivity(target,models,assessments=assess,expected_duration_hours=24)
    assert q['status']=='ABSTAIN' and q['estimate_kwh'] is None
    assert q['signed_sensitivity_kwh']['low']<0<q['signed_sensitivity_kwh']['high']
