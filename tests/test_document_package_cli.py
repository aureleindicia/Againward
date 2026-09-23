"""Assembly convenience consumes real reviewed artifacts; it grants no authority."""
import json

from againward.documents.cli import main
from tests.test_rental_document_adapter import packet


def test_package_cli_assembles_existing_reviewed_sources_without_manual_json(tmp_path, capsys):
    source, payload = packet(tmp_path)
    root = source.parent
    batch_path = root / "batch.json"
    review_path = root / "fact_review.json"
    batch_path.write_text(json.dumps(payload["batch"]))
    review_path.write_text(json.dumps(payload["fact_review"]))
    paths = []
    for index, extraction in enumerate(payload["extractions"]):
        path = root / f"extraction-{index}.json"
        path.write_text(json.dumps(extraction))
        paths.append(str(path))
    assert main(["package-rental", str(root), str(batch_path), str(review_path), *paths]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["invoice_lines"] == 1
    assert receipt["reviewed_facts"] > 0
    assert receipt["approved_for_delivery"] is False
    assembled = json.loads((root / "packages" / receipt["package"].split("/")[-1]).read_text())
    assert assembled["schema_version"] == payload["schema_version"]
    assert assembled["fact_review"] == payload["fact_review"]
    assert main(["link-review-template", str(root), str(batch_path), str(review_path), *paths]) == 0
    link_receipt = json.loads(capsys.readouterr().out)
    assert link_receipt["human_approved_links"] == 0
    assert {row["relationship_type"] for row in link_receipt["relationships"]} == {"SAME_RENTAL", "CREDIT_FOR"}
    for row in link_receipt["relationships"]:
        assert json.loads((root / "review_templates" / row["review_template"].split("/")[-1]).read_text())[
            "reviewer_role"] is None
