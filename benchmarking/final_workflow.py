"""Frozen evaluator of supplied final investigations, not an automatic analyst.

Candidates, retained observations, rejected hypotheses and abstentions are separate.
No model result is manufactured when a submission is absent. The semantic correctness
of evidence and counter-explanations still requires independent adjudication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from energy_mvp.validation import temporal_iou, validate_events

PROTOCOL = {"version":"final-workflow-v1", "minimum_iou":.25,
    "require_same_type":False, "energy_relative_tolerance":.25,
    "retained_level":"aggregate_observation", "omitted_cases":"reject_submission",
    "quantification_success":"both range endpoints within relative tolerance; never mere interval coverage",
    "abstention_success":"only explicitly required abstentions, not all normal cases"}


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _write_new(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.write('\n')


def _artifact(root: Path, relative: str) -> Path:
    path=(root/relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('Evidence artifact outside its case or missing.')
    return path


def prepare(public_root: Path, truth_sha256: str, target: Path) -> dict[str,Any]:
    """Commit public inputs and pre-existing truth hash without reading private labels."""
    if len(truth_sha256)!=64 or any(c not in '0123456789abcdef' for c in truth_sha256):
        raise ValueError('A precommitted private truth SHA-256 is required.')
    cases={}
    for case in sorted(public_root.iterdir()):
        if not case.is_dir() or not (case/'candidate_signals.json').exists():continue
        names=['input.csv','intake.json','candidate_signals.json','investigation_state.json']
        cases[case.name]={'root':str(case.resolve()),'files':{name:_hash(case/name) for name in names}}
    if not cases:raise ValueError('No prepared public case.')
    manifest={'protocol':PROTOCOL,'public_cases':cases,'truth_sha256':truth_sha256,
              'status':'PREPARED_NOT_RUN','final_metrics':None}
    _write_new(target,manifest)
    return manifest


def seal(manifest_path: Path, submission_path: Path, target: Path) -> dict[str,Any]:
    manifest=_read(manifest_path);submission=_read(submission_path)
    if manifest['protocol']!=PROTOCOL:raise ValueError('Protocol changed after preparation.')
    cases=submission.get('cases',[])
    identifiers=[case.get('case_id') for case in cases]
    if len(set(identifiers))!=len(identifiers) or set(identifiers)!=set(manifest['public_cases']):
        raise ValueError('All cases required exactly once; missing cases cannot disappear from recall.')
    if submission.get('execution_kind') not in {'independent_agent','nonblind_operator','engineering_fixture'}:
        raise ValueError('Execution origin must be declared honestly.')
    if not submission.get('operator_or_model'):raise ValueError('Operator/model provenance required.')
    evidence={}
    for case in cases:
        name=case['case_id'];record=manifest['public_cases'][name];root=Path(record['root'])
        for filename,expected in record['files'].items():
            if _hash(root/filename)!=expected:raise ValueError('Public inputs changed after preparation.')
        if case.get('disposition') not in {'FINDINGS','NO_FINDING','ABSTAIN'}:
            raise ValueError('Explicit case disposition required.')
        findings=case.get('findings')
        if not isinstance(findings,list):raise ValueError('findings must be a list.')
        if bool(findings)!=(case['disposition']=='FINDINGS'):
            raise ValueError('Disposition and retained findings disagree.')
        if case['disposition']=='ABSTAIN' and not case.get('evidence_gap'):
            raise ValueError('Abstention requires the missing evidence.')
        if not isinstance(case.get('rejected_hypotheses'),list):raise ValueError('Rejected hypotheses must be explicit.')
        if not case.get('falsification_summary'):raise ValueError('Falsification trace required.')
        ids=set()
        for finding in findings:
            if not finding.get('event_id') or finding['event_id'] in ids:raise ValueError('Unique finding IDs required.')
            ids.add(finding['event_id']);temporal_iou(finding,finding)
            if finding.get('level')!=PROTOCOL['retained_level']:
                raise ValueError('This protocol measures aggregate findings, not attribution or causal claims.')
            if finding.get('recoverable_saving') is not None:raise ValueError('No recoverability credit in this protocol.')
            if not finding.get('alternative_explanations_tested'):raise ValueError('Retained observation requires falsification.')
            estimate=finding.get('estimated_energy_kwh')
            if estimate is not None:
                if set(estimate)!={'low','high'} or not all(isinstance(v,(float,int)) and math.isfinite(v) for v in estimate.values()) or not 0<=estimate['low']<=estimate['high']:
                    raise ValueError('Finite ordered energy range required.')
                if not finding.get('quantitative_source'):raise ValueError('A quantitative artifact is required.')
            elif not finding.get('quantification_abstention_reason'):
                raise ValueError('Unquantified observation requires an explicit reason.')
        refs=case.get('evidence_artifacts')
        if not isinstance(refs,list) or not refs:raise ValueError('Actual evidence artifacts required.')
        quantitative_refs={f['quantitative_source'] for f in findings if f.get('estimated_energy_kwh') is not None}
        if not quantitative_refs<=set(refs):raise ValueError('Quantification artifact not committed.')
        evidence[name]={ref:_hash(_artifact(root,ref)) for ref in refs}
        for metric in ('active_seconds','input_tokens','output_tokens','cost'):
            value=case.get(metric)
            if value is not None and (not isinstance(value,(float,int)) or not math.isfinite(value) or value<0):
                raise ValueError('Measured resource quantities must be finite and nonnegative, or null.')
    payload={'manifest_sha256':_hash(manifest_path),'submission_sha256':_hash(submission_path),
             'submission_path':str(submission_path.resolve()),
             'protocol':PROTOCOL,'submission':submission,'evidence_hashes':evidence,'status':'SEALED_BEFORE_SCORING'}
    _write_new(target,payload)
    return payload


def score(manifest_path: Path, sealed_path: Path, truth_path: Path) -> dict[str,Any]:
    manifest=_read(manifest_path);sealed=_read(sealed_path)
    if sealed['manifest_sha256']!=_hash(manifest_path) or manifest['protocol']!=PROTOCOL or sealed['protocol']!=PROTOCOL:
        raise ValueError('Protocol or manifest commitment changed.')
    if _hash(truth_path)!=manifest['truth_sha256']:raise ValueError('Private labels changed after preparation.')
    submission=sealed['submission']
    original=Path(sealed['submission_path'])
    if _hash(original)!=sealed['submission_sha256'] or _read(original)!=submission:
        raise ValueError('Sealed submission changed.')
    identifiers=[case['case_id'] for case in submission['cases']]
    if len(set(identifiers))!=len(identifiers) or set(identifiers)!=set(manifest['public_cases']):
        raise ValueError('Sealed cohort changed.')
    # Re-verify committed artifacts before opening the private truth.
    for name,hashes in sealed['evidence_hashes'].items():
        root=Path(manifest['public_cases'][name]['root'])
        for filename,expected in {**manifest['public_cases'][name]['files'],**hashes}.items():
            if _hash(_artifact(root,filename))!=expected:raise ValueError('Committed evidence changed.')
    truth=_read(truth_path)
    if set(truth['cases'])!=set(manifest['public_cases']):raise ValueError('Truth/public cohort mismatch.')
    totals={key:0 for key in ['raw_candidates','true_final_findings','false_final_findings',
        'missed_useful_events','correct_abstentions','required_abstentions','correct_no_findings',
        'quantifications_within_tolerance','quantification_opportunities','correct_quantification_abstentions',
        'quantification_abstentions_required','rejected_hypotheses']}
    outputs={}
    for case in submission['cases']:
        name=case['case_id'];expected=truth['cases'][name]
        findings=case['findings'];events=expected['events']
        metrics=validate_events(events,findings,minimum_iou=PROTOCOL['minimum_iou'],require_same_type=False)
        raw=_read(Path(manifest['public_cases'][name]['root'])/'candidate_signals.json')['events']
        totals['raw_candidates']+=len(raw)
        for key,source in [('true_final_findings','true_positives'),('false_final_findings','false_positives'),('missed_useful_events','false_negatives')]:totals[key]+=metrics[source]
        totals['required_abstentions']+=bool(expected.get('abstention_required'))
        totals['correct_abstentions']+=bool(expected.get('abstention_required') and case['disposition']=='ABSTAIN')
        totals['correct_no_findings']+=bool(not events and not expected.get('abstention_required') and case['disposition']=='NO_FINDING')
        totals['rejected_hypotheses']+=len(case['rejected_hypotheses'])
        for event in events:
            totals['quantification_opportunities']+=bool(event.get('quantification_identifiable'))
            totals['quantification_abstentions_required']+=not bool(event.get('quantification_identifiable'))
        by_truth={e['anomaly_id']:e for e in events};by_finding={f['event_id']:f for f in findings}
        for match in metrics['matches']:
            event=by_truth[match['injected_id']];finding=by_finding[match['detected_id']]
            estimate=finding.get('estimated_energy_kwh')
            if event.get('quantification_identifiable') and estimate is not None:
                target=event['expected_energy_impact'];tol=PROTOCOL['energy_relative_tolerance']
                totals['quantifications_within_tolerance']+=bool(target>0 and all(abs(v-target)<=tol*target for v in estimate.values()))
            elif not event.get('quantification_identifiable') and estimate is None:
                totals['correct_quantification_abstentions']+=1
        outputs[name]={'final_metrics':metrics,'disposition':case['disposition'],'raw_candidates':len(raw)}
    resources={name:(sum(c[name] for c in submission['cases']) if all(c.get(name) is not None for c in submission['cases']) else None)
               for name in ('active_seconds','input_tokens','output_tokens','cost')}
    return {'protocol':PROTOCOL,'execution_kind':submission['execution_kind'],'totals':totals,
        'cases':outputs,'resources':resources,
        'semantic_defensibility':'REQUIRES_INDEPENDENT_ADJUDICATION',
        'limitations':['Numeric tolerance and provenance do not prove counterfactual defensibility.',
                       'Engineering fixtures/nonblind operators are not independent agent performance.',
                       'No external validity or financial recoverability measured.']}


def main() -> None:
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare');p.add_argument('public_root',type=Path);p.add_argument('truth_sha256');p.add_argument('output',type=Path)
    p=sub.add_parser('seal');p.add_argument('manifest',type=Path);p.add_argument('submission',type=Path);p.add_argument('output',type=Path)
    p=sub.add_parser('score');p.add_argument('manifest',type=Path);p.add_argument('sealed',type=Path);p.add_argument('truth',type=Path);p.add_argument('output',type=Path)
    args=parser.parse_args()
    if args.command=='prepare':prepare(args.public_root,args.truth_sha256,args.output)
    elif args.command=='seal':seal(args.manifest,args.submission,args.output)
    else:_write_new(args.output,score(args.manifest,args.sealed,args.truth))

if __name__=='__main__':main()
