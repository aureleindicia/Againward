"""Expose source-bound facts and link decisions through the shared Evidence Plane."""
from __future__ import annotations

import json

from againward.evidence.hashing import stable_hash


def append_document_evidence(case, lineage, rows, row_refs):
    if lineage.get("canonical_case_sha256") != stable_hash(case.to_dict()):
        raise ValueError("Document lineage does not support this canonical Rental case.")
    facts = {f["fact_id"]: f for f in lineage["facts"]}

    def reference(fact):
        c = fact["candidate"]
        span = c["source_span"]
        suffix = f"/chars:{span[0]}:{span[1]}" if span else "/visual"
        return {"source_id": c["source_id"], "location": c["location"] + suffix,
                "field": c["semantic_type"]}

    def append(record, refs):
        ordinal = len(rows) + 1
        rows.append({"source_row": ordinal, **record})
        row_refs[str(ordinal)] = refs

    for fact in lineage["facts"]:
        c = fact["candidate"]
        append({"record_type": "document_fact", "record_id": fact["fact_id"],
                "source_id": c["source_id"], "location": reference(fact)["location"],
                "semantic_type": c["semantic_type"], "raw_quote": c["raw_observed_value"],
                "normalized_value": json.dumps(c["value"], ensure_ascii=False),
                "extraction_sha256": fact["extraction_sha256"], "review_sha256": fact["review_sha256"]},
               [reference(fact)])
    for claim in lineage.get("package_classifications", []):
        append({"record_type": "package_classification", "record_id": "claim-" + stable_hash(claim),
                "entity_id": claim["entity_id"], "semantic_type": claim["field"],
                "normalized_value": json.dumps(claim["value"]), "state": claim["status"],
                "review_sha256": stable_hash(claim["reviews"]), "authority": "MODEL_REVIEWED_MEANING_ONLY"},
               [reference(facts[fid]) for fid in claim["supporting_fact_ids"]])
    entity_facts = {e["entity_id"]: [facts[f["fact_id"]] for f in e["facts"]]
                    for e in lineage["entities"]}
    for resolution in (lineage["rental_resolution"], lineage["credit_resolution"]):
        for link in resolution["relationships"]:
            append({"record_type": "document_relationship", "record_id": link["relationship_id"],
                    "relationship_type": link["relationship_type"], "state": link["state"],
                    "left_entity": link["left"], "right_entity": link["right"],
                    "authority": link["authority"], "contradictions": json.dumps(link["contradictions"]),
                    "resolution_sha256": resolution["resolution_sha256"]},
                   [reference(f) for eid in (link["left"], link["right"]) for f in entity_facts[eid]])
