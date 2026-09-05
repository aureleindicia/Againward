#!/usr/bin/env python3
import json,platform,statistics,sys,time,tracemalloc
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from energy_mvp.client_requests import select_minimum_requests
def request(i):
    b=i%37
    return {"request_id":f"Q{i:05d}","request_type":"MICRO_QUESTION","client_question":f"Le régime {b} était-il actif pendant cette période ?","internal_reason":"Départager activité utile et charge inexpliquée.","target_role":"responsable site","related_hypothesis_ids":[f"H{b}"],"hypotheses_distinguished":["activité utile","charge inexpliquée"],"answer_by_hypothesis":{"activité utile":"oui","charge inexpliquée":"non"},"plausible_answers":[{"answer_id":"YES","label":"Oui","decision_effects":["Conserver activité"]},{"answer_id":"NO","label":"Non","decision_effects":["Écarter activité"]}],"decision_impact_dimensions":["false_conclusion_risk"],"expected_effort":"réponse brève","effort":1+i%4,"availability":.8,"reliability":.7,"source_cost":0,"expected_source_type":"CLIENT_DECLARATION","importance":"BLOCKING"}
def main():
    measurements=[]
    for size in (10,100,1000):
        values=[request(i) for i in range(size)]; durations=[]; peaks=[]
        for _ in range(5):
            tracemalloc.start(); start=time.perf_counter(); result=select_minimum_requests(values); durations.append((time.perf_counter()-start)*1000); peaks.append(tracemalloc.get_traced_memory()[1]); tracemalloc.stop()
        measurements.append({"candidate_count":size,"unique_semantic_branches":min(size,37),"selected_count":len(result["selected"]),"rejected_count":len(result["rejected"]),"median_elapsed_ms":round(statistics.median(durations),3),"max_peak_traced_bytes":max(peaks)})
    payload={"schema_version":"indicia-client-workflow-benchmark-v1","synthetic_only":True,"python":platform.python_version(),"runs_per_size":5,"measurements":measurements,"assertions":{"bounded_selection":all(x["selected_count"]<=3 for x in measurements),"semantic_deduplication_exercised":measurements[-1]["rejected_count"]>=963}}
    Path(__file__).with_name("RESULTS.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n"); print(json.dumps(payload,ensure_ascii=False,indent=2)); return 0 if all(payload["assertions"].values()) else 1
if __name__=="__main__": raise SystemExit(main())
