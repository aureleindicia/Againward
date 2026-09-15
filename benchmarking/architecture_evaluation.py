"""Reproducible policy ablations and storage measurements, synthetic only.

These deterministic episodes measure protocol behavior, not LLM task success.
The old policies are explicit local baselines; no private datasets are loaded.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import random
import sqlite3
import statistics
import tempfile
import time
from collections import Counter
from pathlib import Path

from .architecture_probe import request
from energy_mvp.artifact_store import atomic_write_json, transaction, write_json
from energy_mvp.client_requests import select_minimum_requests
from energy_mvp.evidence_plane import EvidenceDataset
from energy_mvp.evidence_protocol import EvidenceQuerySession
from energy_mvp.io import load_data


def joint_information(selected, hypotheses):
    counts=Counter(tuple(q["answer_by_hypothesis"][h] for q in selected) for h in hypotheses)
    return -sum(n/len(hypotheses)*math.log2(n/len(hypotheses)) for n in counts.values())


def greedy_information(candidates, hypotheses):
    selected=[]
    remaining=list(candidates)
    for _ in range(3):
        best=max(remaining,key=lambda q:joint_information([*selected,q],hypotheses))
        selected.append(best); remaining.remove(best)
    return joint_information(selected,hypotheses)


def question_ablations():
    rows=[]
    for seed in range(30):
        rng=random.Random(seed)
        hypotheses=[str(i) for i in range(8)]
        candidates=[]
        # Three independent questions, two redundant alternatives, and two random partitions.
        for index in range(7):
            partition={h:str((int(h) >> (index % 3)) & 1) for h in hypotheses}
            if index >= 5: partition={h:str(rng.randrange(2)) for h in hypotheses}
            candidates.append({**request(f"Q{index}"),"hypotheses_distinguished":hypotheses,
                               "answer_by_hypothesis":partition})
        rng.shuffle(candidates)
        old=[candidates[0]]  # Previous subject-only key discarded every other question.
        ranked=sorted(candidates,key=lambda q:-joint_information([q],hypotheses))[:3]
        selected=select_minimum_requests(candidates)["selected"]
        optimum=max(joint_information(list(group),hypotheses) for group in itertools.combinations(candidates,3))
        rows.append({"seed":seed,"old_subject_dedup_bits":joint_information(old,hypotheses),
                     "independent_top3_bits":joint_information(ranked,hypotheses),
                     "conditional_selection_bits":joint_information(selected,hypotheses),
                     "exhaustive_optimum_bits":optimum,"selected_count":len(selected)})
    adversarial=[]
    for seed in range(50):
        rng=random.Random(1000+seed)
        hypotheses=[str(i) for i in range(12)]
        candidates=[{**request(f"R{i}"),"hypotheses_distinguished":hypotheses,
                     "answer_by_hypothesis":{h:str(rng.randrange(2)) for h in hypotheses}} for i in range(7)]
        selected=select_minimum_requests(candidates)["selected"]
        greedy=greedy_information(candidates,hypotheses)
        production=joint_information(selected,hypotheses)
        optimum=max(joint_information(list(group),hypotheses) for group in itertools.combinations(candidates,3))
        adversarial.append({"seed":1000+seed,"greedy_bits":greedy,"production_bits":production,
                            "optimal_bits":optimum,"gap_bits":max(0,optimum-greedy),
                            "production_gap_bits":max(0,optimum-production)})
    return {"episodes":rows,"random_partition_challenges":adversarial,
            "random_partition_suboptimal_episodes":sum(row["gap_bits"]>1e-9 for row in adversarial),
            "production_suboptimal_episodes":sum(row["production_gap_bits"]>1e-9 for row in adversarial),
            "means":{key:statistics.mean(row[key] for row in rows) for key in
            ("old_subject_dedup_bits","independent_top3_bits","conditional_selection_bits","exhaustive_optimum_bits")},
            "greedy_suboptimal_episodes":sum(row["conditional_selection_bits"] < row["exhaustive_optimum_bits"]-1e-9 for row in rows),
            "limitations":"Uniform hypotheses and noiseless partitions; not calibrated client value or correctness."}


def budget_episodes(root):
    source=root/"series.csv"
    from datetime import datetime,timedelta
    start=datetime(2026,1,1)
    source.write_text("timestamp,power_kw\n"+"\n".join(f"{(start+timedelta(minutes=15*i)).isoformat()},100" for i in range(128)))
    dataset=EvidenceDataset.from_loaded_data(load_data(source),source_sha256="synthetic")
    rows=[]
    for required in (4,12,20,40):
        session=EvidenceQuerySession.create(dataset)
        for i in range(required):
            if session.status=="budget_exhausted":
                used={q for c in session.continuations for q in c["progress_query_ids"]}
                session.continue_investigation(budget={"maximum_calls":session.budget.maximum_calls+4},
                    progress_query_ids=sorted(session.successful_query_ids-used),
                    unresolved_hypotheses=["remaining_comparison"],next_tests=[f"compare window {i}"],
                    decision_impact="Synthetic episode has one unexamined decision-relevant window.")
            session.execute(dataset,{"query_id":f"q{i}","dataset_id":dataset.dataset_id,"operation":"raw_slice",
                            "arguments":{"fields":["power_kw"],"start":i,"limit":1},"purpose":"inspect the next episode window"})
        rows.append({"required_useful_queries":required,"fixed16_completed":min(required,16),
                     "continued_completed":len(session.successful_query_ids),"continuations":len(session.continuations),
                     "returned_rows":session.returned_rows_used,"context_bytes":session.context_bytes_used})
    return {"episodes":rows,"limitations":"Oracle episode length supplied by the harness; does not prove an agent recognizes useful progress."}


def storage_probe(root):
    payload={"synthetic":True,"history":[{"id":i,"status":"observed"} for i in range(100)]}
    results={}
    for strategy in ("per_file_atomic","journaled_json","sqlite_transaction"):
        directory=root/strategy
        directory.mkdir()
        connection=None
        if strategy=="sqlite_transaction":
            connection=sqlite3.connect(directory/"case.db")
            connection.execute("CREATE TABLE artifacts (name TEXT PRIMARY KEY, value TEXT NOT NULL)")
        times=[]
        for repeat in range(20):
            started=time.perf_counter()
            if strategy=="sqlite_transaction":
                with connection:
                    for name in ("state","questions","trace"):
                        connection.execute("INSERT OR REPLACE INTO artifacts VALUES (?,?)",(name,json.dumps(payload)))
            elif strategy=="journaled_json":
                with transaction(directory):
                    for name in ("state","questions","trace"):write_json(directory/f"{name}.json",payload)
            else:
                for name in ("state","questions","trace"):atomic_write_json(directory/f"{name}.json",payload)
            times.append((time.perf_counter()-started)*1000)
        if connection:connection.close()
        results[strategy]={"median_ms":statistics.median(times),"max_ms":max(times),"updates":20}
    return {"results":results,"limitations":"Small local metadata transactions, warm filesystem; SQLite has no JSON materialization in this prototype."}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="againward-architecture-eval-") as tmp:
        root=Path(tmp)
        result={"synthetic_only":True,"question_selection":question_ablations(),
                "budget_policy":budget_episodes(root),"storage":storage_probe(root)}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"question_means":result["question_selection"]["means"],
                      "greedy_suboptimal_episodes":result["question_selection"]["greedy_suboptimal_episodes"],
                      "budget_episodes":result["budget_policy"]["episodes"],"storage":result["storage"]},indent=2))


if __name__=="__main__":main()
