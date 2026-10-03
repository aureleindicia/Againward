import json

import pytest

from againward.documents.contracts import DocumentError
from againward.documents.sources import inventory_sources
from againward.domains.energy_billing.protocol import BillingFailure
from againward.domains.energy_billing.provider import ModelBoundary
from againward.domains.energy_billing.reader import read_source, replay_reading
from benchmarking.document_renderers import pdf


def source(tmp_path, *, native_pdf=True):
    incoming = tmp_path / "input"
    incoming.mkdir()
    if native_pdf:
        pdf(incoming / "invoice.pdf", ["Invoice: INV-01", "Quantity: 1200 kWh"])
    else:
        (incoming / "invoice.txt").write_text("Invoice: INV-01\nQuantity: 1200 kWh")
    output = tmp_path / "snapshot"
    batch = inventory_sources(incoming, output)
    return batch, output


def test_real_pdf_parser_to_atomic_receipt_preserves_valid_siblings(tmp_path):
    batch, root = source(tmp_path)
    rows = [
        {"field": "invoice_id", "group": "invoice", "value": "INV-01", "location": "page:1", "quote": "Invoice: INV-01"},
        {"field": "quantity", "group": "invoice", "value": "1200", "location": "page:1", "quote": "Quantity: 1200 kWh"},
        {"field": "note", "group": "decorative", "value": "invalid", "location": "page:9", "quote": "not there"},
    ]
    boundary = ModelBoundary(lambda *_: json.dumps({"observations": rows, "limitations": []}).encode())
    receipt = read_source(batch, batch.documents[0].source_id, root, model="SCRIPTED", boundary=boundary, role="PRIMARY")
    reading = replay_reading(batch, root, receipt)
    assert len(reading.observations) == 2
    assert len(reading.quarantine) == 1
    assert reading.quarantine[0]["potentially_material"] is False
    assert all(atom.location == "page:1" and atom.start < atom.end for atom in reading.observations)


def test_source_mutation_after_read_is_not_business_unsupported(tmp_path):
    batch, root = source(tmp_path, native_pdf=False)
    boundary = ModelBoundary(lambda *_: b'{"observations":[],"limitations":[]}')
    digest = read_source(batch, batch.documents[0].source_id, root, model="SCRIPTED", boundary=boundary, role="PRIMARY")
    (root / batch.documents[0].blob_path).write_text("Changed bytes")
    with pytest.raises(DocumentError) as failure:
        replay_reading(batch, root, digest)
    assert failure.value.code == "SOURCE_CHANGED"


def test_protocol_failure_writes_no_receipt(tmp_path):
    batch, root = source(tmp_path, native_pdf=False)
    boundary = ModelBoundary(lambda *_: b'{"case":"replacement"}')
    with pytest.raises(BillingFailure) as failure:
        read_source(batch, batch.documents[0].source_id, root, model="SCRIPTED", boundary=boundary, role="PRIMARY")
    assert failure.value.code == "MODEL_PROTOCOL_FAILURE"
    assert boundary.calls == 2
    assert not (root / "energy_billing").exists()


def test_independent_read_only_receives_original_not_primary_proposals(tmp_path):
    batch, root = source(tmp_path, native_pdf=False)
    prompts = []

    def transport(prompt, schema):
        prompts.append(prompt)
        return b'{"observations":[],"limitations":[]}'

    boundary = ModelBoundary(transport)
    first = read_source(batch, batch.documents[0].source_id, root, model="SCRIPTED", boundary=boundary, role="PRIMARY")
    second = read_source(batch, batch.documents[0].source_id, root, model="SCRIPTED", boundary=boundary, role="INDEPENDENT")
    assert first != second
    assert prompts[0] == prompts[1]
    assert "INV-01" in prompts[0]


def test_replay_refuses_missing_or_forged_receipt(tmp_path):
    batch, root = source(tmp_path, native_pdf=False)
    with pytest.raises(BillingFailure):
        replay_reading(batch, root, "../../unknown")
    with pytest.raises(BillingFailure):
        replay_reading(batch, root, "f" * 64)


def test_unrelated_source_mutation_preserves_independent_valid_reading(tmp_path):
    incoming = tmp_path / "input"
    incoming.mkdir()
    (incoming / "first.txt").write_text("Invoice: FIRST")
    (incoming / "second.txt").write_text("Invoice: SECOND")
    root = tmp_path / "snapshot"
    batch = inventory_sources(incoming, root)
    first = next(d for d in batch.documents if "first.txt" in d.original_names)
    second = next(d for d in batch.documents if "second.txt" in d.original_names)
    row = {"field": "invoice_id", "group": "first", "value": "FIRST", "location": "line:1", "quote": "Invoice: FIRST"}
    boundary = ModelBoundary(lambda *_: json.dumps({"observations": [row], "limitations": []}).encode())
    receipt = read_source(batch, first.source_id, root, model="SCRIPTED", boundary=boundary, role="PRIMARY")
    (root / second.blob_path).write_text("CORRUPTED")
    assert len(replay_reading(batch, root, receipt).observations) == 1
    with pytest.raises(DocumentError) as failure:
        read_source(batch, second.source_id, root, model="SCRIPTED", boundary=boundary, role="PRIMARY")
    assert failure.value.code == "SOURCE_CHANGED"
