from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from againward.evidence.dataset import EvidenceDataset
from againward.evidence.protocol import EvidenceQuerySession, QueryBudget


def record_inputs():
    return dict(dataset_id="commercial-records", records=[
        {"source_row": 1, "item_id": "ITEM-001", "amount_minor": 85000, "currency": "EUR"},
        {"source_row": 2, "item_id": "ITEM-001", "amount_minor": 70000, "currency": "EUR"}],
        fields=[{"key": k, "data_type": t} for k, t in [
            ("source_row", "integer"), ("item_id", "string"),
            ("amount_minor", "integer"), ("currency", "string")]],
        provenance={"sources": [{"source_id": "invoice", "sha256": "a" * 64},
                                {"source_id": "agreement", "sha256": "b" * 64}],
                    "rows": {"1": [{"source_id": "invoice", "location": "sheet:Lines!A2:D2"}],
                             "2": [{"source_id": "agreement", "location": "page:1/item:1"}]}})


def test_generic_records_retain_types_sources_and_bounded_handles():
    inputs = record_inputs()
    data = EvidenceDataset.from_records(**inputs)
    inputs["records"][0]["amount_minor"] = 0
    assert data.rows[0]["amount_minor"] == 85000
    restored = EvidenceDataset.from_dict(json.loads(json.dumps(data.to_dict())))
    assert restored.to_dict() == data.to_dict()
    session = EvidenceQuerySession.create(restored, budget=QueryBudget(maximum_calls=1))
    request = dict(query_id="q1", dataset_id=data.dataset_id, operation="raw_slice",
                   purpose="Compare source amounts without deciding recoverability",
                   arguments={"fields": ["item_id", "amount_minor"], "limit": 1})
    response = session.execute(restored, request)
    assert response["decision"] is None
    assert response["result"]["returned"] == 1
    assert response["result"]["source_references"]["1"][0]["source_id"] == "invoice"
    assert response["result"]["sources"] == [{"source_id": "invoice", "sha256": "a" * 64}]
    assert response["retrieval_handles"]
    with pytest.raises(ValueError):
        session.execute(restored, {**request, "query_id": "q2"})


@pytest.mark.parametrize("mutation", ["type", "duplicate_row", "provenance", "nonfinite", "undeclared"])
def test_generic_records_refuse_ambiguous_or_untraceable_values(mutation):
    inputs = record_inputs()
    if mutation == "type": inputs["records"][0]["amount_minor"] = "85000"
    if mutation == "duplicate_row": inputs["records"][1]["source_row"] = 1
    if mutation == "provenance": inputs["provenance"]["rows"].pop("1")
    if mutation == "nonfinite": inputs["records"][0]["amount_minor"] = float("nan")
    if mutation == "undeclared": inputs["records"][0]["mystery"] = 3
    with pytest.raises(ValueError): EvidenceDataset.from_records(**inputs)


@pytest.mark.parametrize("key", ["dataset_id", "rows", "metadata", "provenance"])
def test_v2_hash_binds_identity_metadata_values_and_provenance(key):
    snapshot = deepcopy(EvidenceDataset.from_records(**record_inputs()).to_dict())
    if key == "dataset_id": snapshot[key] = "other"
    if key == "rows": snapshot[key][0]["amount_minor"] = 70000
    if key == "metadata": snapshot[key]["new"] = True
    if key == "provenance": snapshot[key]["rows"]["1"][0]["location"] = "page:2"
    with pytest.raises(ValueError): EvidenceDataset.from_dict(snapshot)


def test_v1_snapshot_is_readable_by_generic_queries_without_energy_imports():
    subprocess.run([sys.executable, "-c", """
import json, sys
from pathlib import Path
from againward.evidence.dataset import EvidenceDataset
from againward.evidence.protocol import EvidenceQuerySession
payload=json.loads(Path('tests/fixtures/domain_kernel/energy_snapshot_v1.json').read_text())
data=EvidenceDataset.from_dict(payload)
assert data.to_dict()==payload
session=EvidenceQuerySession.create(data)
reply=session.execute(data, dict(query_id='q',dataset_id=data.dataset_id,operation='describe_schema',
                                arguments={},purpose='Inspect legacy snapshot'))
assert reply['decision'] is None
assert not any(n.startswith(('energy_mvp','againward.domains')) for n in sys.modules)
"""], check=True)
