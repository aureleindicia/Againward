import json
from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from energy_mvp.models import Reading
from energy_mvp.signals import _fit_robust_reference
from energy_mvp.toolbox import calculate_residuals, fit_linear_baseline


def readings(labels=('A','B','C')):
    result=[]
    for i in range(360):
        category=i%len(labels); production=float(i%13)
        power=8+category*3+(1+category*.4)*production
        result.append(Reading(datetime(2025,1,1)+timedelta(hours=i),power,
            power_kw=power,production=production,product_type=labels[category],interval_hours=1))
    return result


PREDICTORS=('production','product_type','production_by_product')

@pytest.mark.parametrize('labels', [('A','B'),('B','A'),('recette_1','recette_2'),('éclair','P/41'),('z','a','middle'),('🔥','null','B','fourth')])
def test_predictions_invariant_to_arbitrary_bijective_renaming(labels):
    data=readings(labels)
    reference=readings(tuple(str(i) for i in range(len(labels))))
    a=fit_linear_baseline(data,predictors=PREDICTORS)
    b=fit_linear_baseline(reference,predictors=PREDICTORS)
    assert a['validation_metrics']['rmse'] < 1e-6
    assert a['coefficients']==b['coefficients']
    assert [p['expected_kw'] for p in calculate_residuals(data,a)] == [p['expected_kw'] for p in calculate_residuals(reference,b)]
    restored=json.loads(json.dumps(a))
    assert calculate_residuals(data,restored)==calculate_residuals(data,a)


def test_new_missing_and_rare_categories_never_become_reference_category():
    data=readings()
    model=fit_linear_baseline(data,predictors=PREDICTORS)
    future=[replace(data[-1],timestamp=data[-1].timestamp+timedelta(hours=i+1),product_type=label)
            for i,label in enumerate(['new',None,'A'])]
    assert len(calculate_residuals(future,model))==1
    assert calculate_residuals(future,model)[0]['timestamp']==future[-1].timestamp.isoformat()
    data[0]=replace(data[0],product_type='singleton')
    model=fit_linear_baseline(data,predictors=PREDICTORS)
    assert model['category_support']['product_type']['unsupported_levels']==['singleton']
    assert model['calibration_unsupported_rows']==1


def test_validation_cannot_teach_vocabulary_and_exclusions_are_reported():
    data=readings()
    for i in range(300,330):data[i]=replace(data[i],product_type='future_only')
    model=fit_linear_baseline(data,predictors=PREDICTORS)
    assert 'future_only' not in model['category_levels']['product_type']
    assert model['validation_unsupported_rows']==30
    assert model['validation_coverage_ratio']<1


def test_whole_validation_unknown_is_explicitly_unavailable():
    data=readings()
    for i in range(252,360):data[i]=replace(data[i],product_type='future_only')
    with pytest.raises(ValueError,match='Support insuffisant'):
        fit_linear_baseline(data,predictors=PREDICTORS)


def test_high_cardinality_is_explicitly_refused():
    with pytest.raises(ValueError,match='32 modalités'):
        fit_linear_baseline(readings(tuple(f'product-{i}' for i in range(40))),predictors=PREDICTORS)


def test_robust_refit_never_trims_validation_or_moves_split():
    data=readings(('one',))
    # Training-only outlier should be removed. Held-out extreme must remain measured.
    data[40]=replace(data[40],power_kw=data[40].power_kw+100)
    data[300]=replace(data[300],power_kw=data[300].power_kw+100)
    initial=fit_linear_baseline(data,predictors=('production',))
    robust=_fit_robust_reference(data,('production',))
    assert robust['robust_refit']
    assert robust['calibration_end']==initial['calibration_end']
    assert robust['validation_rows']==initial['validation_rows']
    assert robust['validation_metrics']['rmse']>9


def test_constant_predictor_cannot_support_new_operating_range():
    data=readings(('one',))
    data=[replace(r,production=5.,power_kw=20.) for r in data]
    model=fit_linear_baseline(data,predictors=('production',))
    future=replace(data[-1],timestamp=data[-1].timestamp+timedelta(hours=1),production=10.,power_kw=30.)
    assert model['constant_predictors']['production']==5.
    assert calculate_residuals([future],model)==[]


def test_supported_production_change_is_normalized_not_discarded():
    data=readings(('one',))
    model=fit_linear_baseline(data,predictors=('production',))
    future=[replace(r,timestamp=r.timestamp+timedelta(days=100),production=r.production*1.5,
                    power_kw=8+r.production*1.5) for r in data]
    residuals=calculate_residuals(future,model)
    assert len(residuals)==len(future)
    assert max(abs(r['residual_kw']) for r in residuals)<1e-6
