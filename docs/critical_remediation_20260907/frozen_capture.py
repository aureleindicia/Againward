import csv, hashlib, json, math, os, random, runpy, sys, tempfile
from pathlib import Path
from datetime import datetime,timedelta
from energy_mvp.io import load_data
from energy_mvp.signals import detect_candidate_events
from energy_mvp.validation import validate_events
from energy_mvp.blind_suite import CASE_NAMES, generate_blind_case
from energy_mvp.demo import SCENARIOS, generate_demo

ROOT=Path(__file__).resolve().parents[2]
CASE_NAMES_NEW=('step_large','step_small','step_down','ramp','transient','production_explained','noise','weekly','weather_explained','cyclic','missing_block')
def create_case(name,path,seed):
 rng=random.Random(seed); noise=0.; rows=[]
 context=name in ('production_explained','weather_explained')
 for i in range(90*96):
  day,q=divmod(i,96); t=datetime(2025,1,6)+timedelta(minutes=15*i)
  noise=.7*noise+rng.gauss(0,.12)
  prod=5+int(day>=40)*5; temp=15+8*math.sin(day/90*2*math.pi)
  power=10+noise
  if name=='step_large':power+=10*(day>=40)
  if name=='step_small':power+=2*(day>=40)
  if name=='step_down':power+=10*(day<40)
  if name=='ramp':power+=min(10,max(0,(day-35)/3))
  if name=='transient':power+=8*(40<=day<55)
  if name=='production_explained':power+=2*prod
  if name=='weekly':power+=8*(t.weekday()<5 and 24<=q<72)
  if name=='weather_explained':power+=2*temp
  if name=='cyclic':power+=8*math.sin(day/14*2*math.pi)
  if name=='missing_block' and 40<=day<48:continue
  row=[t.isoformat(),power]
  if context:row += [prod,temp]
  rows.append(row)
 with path.open('w') as f:
  w=csv.writer(f);w.writerow(['timestamp','power_kw']+(['production','outside_temperature_c'] if context else []));w.writerows(rows)
 return hashlib.sha256(path.read_bytes()).hexdigest()

def main(destination):
 out=Path(destination).resolve();out.mkdir(parents=True,exist_ok=True)
 if (out/'results.json').exists():raise FileExistsError(out)
 results={'new_cases':{},'historical_blind':{},'demo_scenarios':{}}
 with tempfile.TemporaryDirectory() as temp:
  root=Path(temp)
  for name in CASE_NAMES_NEW:
   for seed in (103,211,307):
    p=root/'input.csv'; sha=create_case(name,p,seed)
    d=detect_candidate_events(load_data(p,interval_minutes=15))
    results['new_cases'][f'{name}-{seed}']={'source_sha256':sha,'events':d['events'],'threshold':d['structured_threshold_kw'],'baseline_rmse':d['baseline']['validation_metrics']['rmse']}
  for index,name in enumerate(CASE_NAMES):
   p=root/'input.csv';truth=root/'truth.json'
   generate_blind_case(name,p,root/'intake.json',truth,seed=700+index)
   d=detect_candidate_events(load_data(p,interval_minutes=60,site_timezone='Europe/Paris'))
   tr=json.loads(truth.read_text())
   results['historical_blind'][name]={'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'events':d['events'],'strict_metrics':validate_events(tr['anomalies'],d['events'],minimum_iou=.25),'temporal_metrics':validate_events(tr['anomalies'],d['events'],minimum_iou=.25,require_same_type=False)}
  for name in sorted(SCENARIOS):
   for seed,enabled in [(1,True),(7,True),(42,True),(101,False)]:
    p=root/'input.csv';truth=root/'truth.json'
    tr=generate_demo(p,truth,days=120,seed=seed,scenario_name=name,include_data_issues=True,include_anomalies=enabled)
    d=detect_candidate_events(load_data(p))
    results['demo_scenarios'][f'{name}-{seed}']={'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'events':d['events'],'strict_metrics':validate_events(tr['anomalies'],d['events'],minimum_iou=.3)}
 results['protocol']={'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'old_criteria_unchanged':True,'new_cases':'engineering counterexamples, not unseen field validation','new_case_acceptance':'step types distinguish level/ramp/transient; no change on explained/noise/weekly; cyclic must not become final finding; candidate counts and localization published without posthoc scoring threshold changes'}
 (out/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
 # Run original audit probe without modifying either the original code or its results.
 probe=ROOT/'scratch/againward_adversarial_20260907/probes.py'
 env={'__file__':str(out/'probes.py'),'__name__':'capture_probe'}
 exec(compile(probe.read_text(),str(probe),'exec'),env)
 env['run']()
 print('Captured',out)
if __name__=='__main__':main(sys.argv[1])
