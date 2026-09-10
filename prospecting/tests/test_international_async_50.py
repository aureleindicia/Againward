"""Intégrité du lot public ; ces tests ne certifient pas les faits des entreprises."""
from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
from pathlib import Path

from prospecting.prepare import prepare
from prospecting.score import score


DATA = Path(__file__).resolve().parents[1] / "data"
BATCH = DATA / "international_async_50_20260910"
SPEC = importlib.util.spec_from_file_location("batch_builder", BATCH / "build_artifacts.py")
assert SPEC and SPEC.loader
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def load(name):
    return json.loads((BATCH / name).read_text(encoding="utf-8"))


def test_public_batch_has_fifty_distinct_entities_without_french_targets():
    raw = load("prospects_raw.json")["prospects"]
    assert len(raw) == len({p["entity_key"] for p in raw}) == 50
    assert all("France" not in p["country"] for p in raw)
    assert len({p["prospect_id"] for p in raw}) == 50


def test_existing_preparation_and_scoring_reproduce_frozen_batch():
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp)
        prepare(BATCH / "prospects_raw.json", DATA / "opposition.json", folder)
        assert json.loads((folder / "rejected_prequalification.json").read_text())["prospects"] == []
        computed = score(BATCH / "prospects_raw.json", BATCH / "scoring_assessments.json", folder / "scores.json")
        assert computed == load("scoring_results.json")


def test_business_uncertainty_or_sharing_hold_cannot_be_bought_with_async():
    for prospect in load("research_judgments.json")["prospects"]:
        if prospect["utility_status"] != "STRONG_CANDIDATE" or prospect.get("commercial_hold"):
            altered = copy.deepcopy(prospect)
            altered["ratings"][7] = 5
            assert builder.band(altered) == 3


def test_unknown_async_stays_out_of_first_commercial_bands():
    candidate = copy.deepcopy(load("research_judgments.json")["prospects"][1])
    candidate["utility_status"] = "STRONG_CANDIDATE"
    candidate.pop("commercial_hold", None)
    candidate["ratings"][7] = 0
    assert builder.band(candidate) == 3


def test_all_personalization_hooks_resolve_to_source_in_same_company():
    sources = {p["prospect_id"]:{s["source_id"]:s for s in p["sources"]} for p in load("prospects_raw.json")["prospects"]}
    emails = load("email_personalization.json")["prospects"]
    assert len(emails) == 50
    for item in emails:
        own = sources[item["prospect_id"]]
        assert item["hook_source_refs"]
        assert all(ref in own for ref in item["hook_source_refs"])
        assert item["source_urls"] == [own[ref]["url"] for ref in item["hook_source_refs"]]
        assert item["qualification_question_fr"] and item["target_function"]
        assert item["send_status"] == "NOT_SENT"


def test_no_public_score_becomes_client_qualification_or_utility_probability():
    batch = load("commercial_prioritization.json")
    assert batch["contacting_performed"] is False
    for item in batch["prospects"]:
        assert item["paid_pilot_qualification"] == "NOT_QUALIFIED"
        assert item["energy_data_availability"] == "UNKNOWN"
        assert item["utility_probability"] is None
        assert item["async_transfer_confidence"] in {"low", "medium"}


def test_commercial_rank_is_distinct_from_legacy_score_and_bands_are_honest():
    rows = load("commercial_prioritization.json")["prospects"]
    assert [p["commercial_rank"] for p in rows] == list(range(1,51))
    for p in rows:
        assert p["commercial_band"] == builder.band(p)
    # Le score industriel élevé d'un entrepôt à portail seul ne doit pas évincer
    # les premières cibles ayant des preuves écrites au sein des opérations.
    by_name = {p["name"]:p for p in rows}
    assert by_name["Modist Brewing"]["commercial_rank"] < by_name["Des Moines Cold Storage"]["commercial_rank"]
    assert by_name["Modist Brewing"]["score_display"] < by_name["Des Moines Cold Storage"]["score_display"]


def test_failed_source_access_is_not_reported_as_full_read():
    sources = {s["url"]:s for s in load("source_inventory.json")["sources"]}
    assert sources["https://almanacbeer.com/pages/taproom-keyholder"]["access_status"] == "SEARCH_EXTRACT_OPEN_FAILED"
    assert sources["https://www.oceanz.eu/en/blogs/youroceanz-hassle-free-order-management/"]["access_status"] == "SEARCH_EXTRACT_CHALLENGE"
    assert all(s["retrieved_at"] == "2026-09-10" for s in sources.values())
