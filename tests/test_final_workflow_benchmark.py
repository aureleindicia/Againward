"""Engineering fixtures test scoring/integrity, never claim agent performance."""
import hashlib
import json
from pathlib import Path

import pytest

from benchmarking.final_workflow import prepare, seal, score


def write(path, value):
    path.write_text(json.dumps(value))


def packet(tmp_path):
    public=tmp_path/'public';public.mkdir()
    event={'anomaly_id':'T1','type':'shift','start':'2025-02-01','end':'2025-03-01',
           'expected_energy_impact':100,'quantification_identifiable':True}
    truth={'cases':{'positive':{'events':[event]},'unknown':{'events':[],'abstention_required':True},
                    'normal':{'events':[]}}}
    truth_path=tmp_path/'truth.json';write(truth_path,truth)
    cases=[]
    for name in truth['cases']:
        root=public/name;root.mkdir()
        for filename in ('input.csv','intake.json','investigation_state.json'):(root/filename).write_text('{}')
        write(root/'candidate_signals.json',{'events':[dict(event,event_id='C1')]})
        write(root/'calculation.json',{'signed_net_kwh':100})
        cases.append({'case_id':name,'disposition':{'positive':'FINDINGS','unknown':'ABSTAIN','normal':'NO_FINDING'}[name],
          'findings':[],'evidence_gap':'No operating context' if name=='unknown' else None,
          'rejected_hypotheses':['C1'] if name!='positive' else [],
          'falsification_summary':'Engineering fixture only: supplied counter-explanation result.',
          'evidence_artifacts':['calculation.json']})
    cases[0]['findings']=[{'event_id':'F1','type':'observation','start':event['start'],'end':event['end'],
          'level':'aggregate_observation','alternative_explanations_tested':['production'],
          'estimated_energy_kwh':{'low':90,'high':110},'quantitative_source':'calculation.json'}]
    manifest=tmp_path/'manifest.json';prepare(public,hashlib.sha256(truth_path.read_bytes()).hexdigest(),manifest)
    submission=tmp_path/'submission.json';write(submission,{'execution_kind':'engineering_fixture','operator_or_model':'pytest','cases':cases})
    return manifest,submission,truth_path


def test_final_metrics_do_not_count_candidates_as_findings(tmp_path):
    manifest,submission,truth=packet(tmp_path);sealed=tmp_path/'sealed.json'
    seal(manifest,submission,sealed);result=score(manifest,sealed,truth)
    t=result['totals']
    assert t['raw_candidates']==3 and t['true_final_findings']==1
    assert t['false_final_findings']==t['missed_useful_events']==0
    assert t['correct_abstentions']==t['required_abstentions']==1
    assert t['correct_no_findings']==1 and t['quantifications_within_tolerance']==1
    assert result['resources']['cost'] is None
    assert result['execution_kind']=='engineering_fixture'

@pytest.mark.parametrize('mutation',['omit','duplicate','no_falsification','unlinked_number'])
def test_seal_rejects_incomplete_investigations(tmp_path,mutation):
    manifest,submission,truth=packet(tmp_path);value=json.loads(submission.read_text())
    if mutation=='omit':value['cases'].pop()
    if mutation=='duplicate':value['cases'].append(value['cases'][0])
    if mutation=='no_falsification':value['cases'][0]['falsification_summary']=''
    if mutation=='unlinked_number':value['cases'][0]['findings'][0]['quantitative_source']='missing.json'
    write(submission,value)
    with pytest.raises(ValueError):seal(manifest,submission,tmp_path/'sealed.json')

@pytest.mark.parametrize('mutation',['truth','input','evidence','submission','sealed'])
def test_score_refuses_changed_commitments(tmp_path,mutation):
    manifest,submission,truth=packet(tmp_path);sealed=tmp_path/'sealed.json';seal(manifest,submission,sealed)
    paths={'truth':truth,'input':tmp_path/'public/positive/input.csv',
           'evidence':tmp_path/'public/positive/calculation.json','submission':submission}
    if mutation=='sealed':
        value=json.loads(sealed.read_text());value['submission']['cases'][0]['findings']=[];write(sealed,value)
    else:paths[mutation].write_text(paths[mutation].read_text()+' ')
    with pytest.raises(ValueError):score(manifest,sealed,truth)


def test_wide_range_does_not_get_quantification_credit(tmp_path):
    manifest,submission,truth=packet(tmp_path);value=json.loads(submission.read_text())
    value['cases'][0]['findings'][0]['estimated_energy_kwh']={'low':0,'high':10000}
    write(submission,value);sealed=tmp_path/'sealed.json';seal(manifest,submission,sealed)
    assert score(manifest,sealed,truth)['totals']['quantifications_within_tolerance']==0
