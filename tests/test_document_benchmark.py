"""Evaluation-harness tests, explicitly not model quality or a blind holdout."""
import hashlib
import json
from pathlib import Path
import shutil

import pytest
from pypdf import PdfReader

from benchmarking.document_corpus import FAMILIES, generate_corpus
from benchmarking.document_runner import run_documents
from benchmarking.document_scoring import score_documents


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    if shutil.which("pdftoppm") is None:
        pytest.skip("Synthetic scan generation requires Poppler pdftoppm; no fake image substitute")
    root = tmp_path_factory.mktemp("document-corpus")
    generate_corpus(root, split="DEV", seed=812)
    return root


def test_real_documents_have_no_embedded_canonical_packets_and_scans_have_no_text(corpus):
    truth = json.loads((corpus / "private/truth.json").read_text())
    assert len(truth["cases"]) == len(FAMILIES) == 20
    assert not list((corpus / "public").rglob("*.json"))
    assert {p.suffix for p in (corpus / "public").rglob("*.*")} >= {".pdf", ".csv", ".xlsx", ".eml"}
    for cid, case in truth["cases"].items():
        if case["family"] in {"scan", "hybrid"}:
            reader = PdfReader(corpus / "public" / cid / "billing.pdf")
            text = reader.pages[0].extract_text()
            assert "Net" not in text and "net" not in text
            assert bool(text.strip()) == (case["family"] == "hybrid")
            assert len(reader.pages[0]["/Resources"]["/XObject"]) == 1
    with pytest.raises(ValueError, match="empty"):
        generate_corpus(corpus, split="DEV", seed=812)


def test_no_extractor_baseline_records_zero_recall_not_perfect_accuracy(corpus, tmp_path):
    run = tmp_path / "run"
    observed = run_documents(corpus / "public", run)
    assert all(r["status"] == "NO_SUBMISSION" for r in observed["cases"].values())
    assert any("MULTIMODAL_REQUIRED" in r["routes"] for r in observed["cases"].values())
    report = score_documents(corpus, run)
    metrics = report["metrics"]
    assert metrics["supported_discrepancy_precision"] is None
    assert metrics["supported_discrepancy_recall"] == 0
    assert metrics["false_positives"] == 0 and metrics["false_negatives"] > 0
    assert metrics["annotated_field_recall"] == 0
    assert metrics["entity_pair_precision"] is None
    assert metrics["canonical_fact_retrievable_support"] is None
    with pytest.raises(ValueError, match="already exists"):
        score_documents(corpus, run)
    with pytest.raises(ValueError, match="empty"):
        run_documents(corpus / "public", run)
    (run / "observations.json").write_text("{}")
    with pytest.raises(ValueError, match="observations changed"):
        score_documents(corpus, run)


def test_runner_does_not_import_generator_or_scorer():
    import ast
    path = Path(__file__).resolve().parents[1] / "benchmarking/document_runner.py"
    tree = ast.parse(path.read_text())
    imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not any(name and ("corpus" in name or "scoring" in name) for name in imports)


def test_seed_reproduces_source_hashes_including_spreadsheet_timestamps(corpus, tmp_path):
    generated = generate_corpus(tmp_path / "repeat", split="DEV", seed=812)
    original = json.loads((corpus / "manifest.json").read_text())
    assert generated["truth_sha256"] == original["truth_sha256"]


def test_scoring_rejects_changed_truth_before_any_metric(corpus, tmp_path):
    fake = tmp_path / "corpus"
    (fake / "private").mkdir(parents=True)
    shutil.copy(corpus / "manifest.json", fake / "manifest.json")
    (fake / "private/truth.json").write_text("{}")
    run = tmp_path / "run"
    run.mkdir()
    data = b'{}'
    (run / "observations.json").write_bytes(data)
    (run / "observations.sha256").write_text(hashlib.sha256(data).hexdigest())
    with pytest.raises(ValueError, match="truth changed"):
        score_documents(fake, run)


def test_runner_replays_supplied_source_bound_proposals_without_an_oracle(tmp_path):
    from tests.test_rental_document_adapter import packet

    _, package = packet(tmp_path / "fixture")
    public, submissions = tmp_path / "public", tmp_path / "submissions"
    public.mkdir()
    submissions.mkdir()
    shutil.copytree(tmp_path / "fixture/input", public / "case")
    (submissions / "case.json").write_text(json.dumps(package))
    result = run_documents(public, tmp_path / "run", submissions=submissions)
    case = result["cases"]["case"]
    assert case["status"] == "VALIDATED"
    assert case["supported_discrepancy"] == {"EUR": "150.00"}
    assert case["source_chain_validated"] and case["manual_decisions"] > 0
    assert len(case["relationships"]) == 1
    assert case["relationships"][0]["state"] == "CONFIRMED"
    (submissions / "case.json").write_text('{"repeated": 1, "repeated": 2}')
    invalid = run_documents(public, tmp_path / "invalid", submissions=submissions)
    assert invalid["cases"]["case"]["status"] == "ABSTAIN"
    assert invalid["cases"]["case"]["supported_discrepancy"] is None
