import csv
import math
import random
from datetime import datetime,timedelta

import pytest

from energy_mvp.io import load_data
from energy_mvp.signals import detect_candidate_events


def run_case(tmp_path,kind,seed=103):
    rng=random.Random(seed)
    path=tmp_path/'input.csv'
    with path.open('w') as f:
        w=csv.writer(f)
        context=kind in ('production','weather')
        w.writerow(['timestamp','power_kw']+(['production','outside_temperature_c'] if context else []))
        for i in range(90*96):
            day,q=divmod(i,96);t=datetime(2025,1,6)+timedelta(minutes=i*15)
            power=10+rng.gauss(0,.12)
            prod=5+5*(day>=40);temp=15+8*math.sin(day/90*2*math.pi)
            if kind=='step':power+=10*(day>=40)
            if kind=='small_step':power+=2*(day>=40)
            if kind=='down':power+=10*(day<40)
            if kind=='ramp':power+=min(10,max(0,(day-35)/3))
            if kind=='temporary':power+=8*(40<=day<55)
            if kind=='production':power+=2*prod
            if kind=='weather':power+=2*temp
            if kind=='weekly':power+=8*(t.weekday()<5 and 24<=q<72)
            if kind=='cyclic':power+=8*math.sin(day/14*2*math.pi)
            w.writerow([t.isoformat(),power]+([prod,temp] if context else []))
    return detect_candidate_events(load_data(path))

@pytest.mark.parametrize('kind',['step','small_step','down'])
def test_meter_only_persistent_level_is_located_without_inventing_drift(tmp_path,kind):
    d=run_case(tmp_path,kind)
    levels=[e for e in d['events'] if e['type']=='permanent_baseline_shift']
    assert len(levels)==1
    assert abs((datetime.fromisoformat(levels[0]['start'])-datetime(2025,2,15)).days)<=2
    assert not any(e['type']=='progressive_drift' for e in d['events'])
    assert all(e['status']=='candidate_signal' for e in d['events'])
    assert 'forecast' in levels[0]['persistence']


def test_progressive_change_is_not_lost(tmp_path):
    d=run_case(tmp_path,'ramp')
    assert any(e['type']=='progressive_drift' for e in d['events'])


def test_temporary_change_does_not_become_permanent(tmp_path):
    d=run_case(tmp_path,'temporary')
    assert any(e['type']=='temporary_level_shift' for e in d['events'])
    assert not any(e['type'] in ('permanent_baseline_shift','progressive_drift') for e in d['events'])

@pytest.mark.parametrize('kind',['production','weather','weekly','noise','cyclic'])
def test_explained_or_repeated_variation_does_not_create_regime_change(tmp_path,kind):
    d=run_case(tmp_path,kind)
    assert d['events']==[]


def test_production_change_with_identifiable_reference_is_explained(tmp_path):
    path=tmp_path/'varied.csv';origin=datetime(2025,1,6)
    with path.open('w') as f:
        writer=csv.writer(f);writer.writerow(['timestamp','power_kw','production'])
        for i in range(90*96):
            day,q=divmod(i,96)
            production=5+(q%12)+(4 if day>=40 else 0)
            writer.writerow([(origin+timedelta(minutes=15*i)).isoformat(),10+2*production,production])
    result=detect_candidate_events(load_data(path))
    assert result['events']==[]
    assert result['prediction_coverage']['ratio']==1
