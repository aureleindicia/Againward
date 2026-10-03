"""Scripted protocol checks; these are not an actual operator rehearsal."""
import json

import pytest

from againward.core.privacy import validate_codex_privacy_review
from againward.core.visual_review import attest_visual_packet, prepare_visual_packet
from againward.domains.rental.privacy_policy import RENTAL_PRESERVATION
from benchmarking.document_renderers import pdf
from tests.test_privacy_gate import _file_spec, _review
from tests.test_rental_privacy_documents import rental_case


def _prepared(tmp_path):
    case = rental_case(tmp_path)
    source = case / "incoming/return.pdf"
    pdf(source, ["Signed return agreement AG-12 asset LIFT-5 on 2026-09-05."], scan=True)
    review = _review(case, [_file_spec("incoming/return.pdf")], status="PASS")
    packet = prepare_visual_packet(case, review)
    return case, source, review, packet


def test_interactive_visual_packet_binds_actor_preview_source_and_gate(tmp_path):
    case, source, review, packet = _prepared(tmp_path)
    component = packet["components"][0]
    assert component["location"] == "page:1"
    assert component["source_sha256"] != component["preview_sha256"]
    answers = iter(["INSPECTED " + component["source_sha256"][:12], "PASS",
                    "PROFESSIONAL_SIGNATURE", "YES"])
    result = attest_visual_packet(case, review, actor_id="owner_01",
                                  ask=lambda _prompt: next(answers), interactive=True)
    assert result["reviewed_components"] == 1
    reviewed = json.loads(review.read_text())["files"][0]["visual_reviews"][0]
    assert reviewed["reviewer_id"] == "owner_01"
    manifest = validate_codex_privacy_review(case, review, preservation_policy=RENTAL_PRESERVATION)
    visual = manifest["files"][0]["privacy_assessment"]["human_visual_reviews"][0]
    assert visual["reviewer_id"] == "owner_01"
    assert visual["packet_sha256"] == packet["packet_sha256"]
    assert manifest["files"][0]["original_sha256"] == component["source_sha256"]
    assert (case / "sanitized/return.pdf").is_file()
    assert not source.exists()


def test_visual_operator_cannot_be_simulated_by_noninteractive_cli(tmp_path):
    case, _, review, _ = _prepared(tmp_path)
    with pytest.raises(ValueError, match="HUMAN_REVIEW_REQUIRED"):
        attest_visual_packet(case, review, actor_id="model", ask=lambda _: "PASS", interactive=False)


def test_visual_preview_tampering_blocks_attestation(tmp_path):
    case, _, review, packet = _prepared(tmp_path)
    preview = case / packet["components"][0]["preview"]
    preview.write_bytes(preview.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="SOURCE_CHANGED"):
        attest_visual_packet(case, review, actor_id="owner_01", ask=lambda _: "PASS", interactive=True)


def test_visual_packet_requires_codex_first_review(tmp_path):
    case = rental_case(tmp_path)
    pdf(case / "incoming/return.pdf", ["Signed return."], scan=True)
    review = _review(case, [_file_spec("incoming/return.pdf")], status="PASS")
    body = json.loads(review.read_text())
    body["codex_semantic_review"]["completed"] = False
    review.write_text(json.dumps(body))
    with pytest.raises(ValueError, match="Codex-first"):
        prepare_visual_packet(case, review)


def test_visual_packet_rejects_path_escape_even_with_recomputed_digest(tmp_path):
    from againward.core.visual_review import _digest
    case, _, review, packet = _prepared(tmp_path)
    packet["components"][0]["preview"] = "../outside.png"
    packet["packet_sha256"] = _digest({key: value for key, value in packet.items()
                                      if key != "packet_sha256"})
    (case / "privacy/candidate/visual_packet.json").write_text(json.dumps(packet))
    with pytest.raises(ValueError, match="path escapes"):
        attest_visual_packet(case, review, actor_id="owner_01", ask=lambda _: "PASS", interactive=True)
