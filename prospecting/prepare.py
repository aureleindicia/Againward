"""Prépare la veille publique avant le scoring qualitatif.

Ce script ne note, ne classe et ne contacte jamais les entreprises. Il transforme des fiches
manuelles sourcées en un paquet compact et vérifiable pour une phase de jugement ultérieure.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
RAW_PATH = DATA / "prospects_raw.json"
OPPOSITION_PATH = DATA / "opposition.json"

ALLOWED_STATUSES = {"CANDIDATE", "UNCERTAIN", "REJECTED"}
FORBIDDEN_SCORING_KEYS = {
    "score", "score_final", "priority", "rank", "ranking", "contact_angle",
    "email_draft", "contact_recommended", "recommended_contact_order",
}


def _normalise(value: str) -> str:
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _assert_no_scoring_fields(value: Any, location: str = "root") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key.lower() in FORBIDDEN_SCORING_KEYS:
                raise ValueError(f"Champ interdit avant scoring: {location}.{key}")
            _assert_no_scoring_fields(nested, f"{location}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _assert_no_scoring_fields(nested, f"{location}[{index}]")


def _require_text(record: dict[str, Any], key: str, location: str) -> None:
    if not isinstance(record.get(key), str) or not record[key].strip():
        raise ValueError(f"{location}.{key} est requis.")


def _validate_source(source: dict[str, Any], location: str) -> None:
    for key in ("source_id", "title", "url", "retrieved_at", "source_type", "confidence"):
        _require_text(source, key, location)
    if source["confidence"] not in {"high", "medium", "low"}:
        raise ValueError(f"{location}.confidence est invalide.")
    if not source["url"].startswith(("https://", "http://")):
        raise ValueError(f"{location}.url doit être une URL HTTP(S).")


def _validate_prospect(prospect: dict[str, Any]) -> None:
    location = f"prospect[{prospect.get('prospect_id', '?')}]"
    for key in (
        "prospect_id", "entity_key", "name", "sector", "discovered_at",
        "prequalification_status", "facts", "inferences", "sources",
        "missing_information", "negative_signals", "related_entities",
    ):
        if key not in prospect:
            raise ValueError(f"{location}.{key} est requis.")
    if prospect["prequalification_status"] not in ALLOWED_STATUSES:
        raise ValueError(f"{location}.prequalification_status est invalide.")
    if _normalise(prospect["entity_key"]) != prospect["entity_key"]:
        raise ValueError(f"{location}.entity_key doit être normalisé.")
    source_ids: set[str] = set()
    for source in prospect["sources"]:
        _validate_source(source, location)
        if source["source_id"] in source_ids:
            raise ValueError(f"{location}: source_id dupliqué {source['source_id']}.")
        source_ids.add(source["source_id"])
    for fact in prospect["facts"]:
        for key in ("field", "value", "source_id", "observed_at", "confidence"):
            _require_text(fact, key, location)
        if fact["source_id"] not in source_ids:
            raise ValueError(f"{location}: fait sans source connue {fact['source_id']}.")
        if fact["confidence"] not in {"high", "medium", "low"}:
            raise ValueError(f"{location}: confiance de fait invalide.")
    for inference in prospect["inferences"]:
        for key in ("statement", "basis_source_ids", "confidence"):
            if key not in inference:
                raise ValueError(f"{location}: inférence incomplète.")
        if not isinstance(inference["basis_source_ids"], list) or not inference["basis_source_ids"]:
            raise ValueError(f"{location}: une inférence doit citer ses sources.")
        if not set(inference["basis_source_ids"]).issubset(source_ids):
            raise ValueError(f"{location}: inférence avec source inconnue.")
        if inference["confidence"] not in {"high", "medium", "low"}:
            raise ValueError(f"{location}: confiance d'inférence invalide.")
    for relation in prospect["related_entities"]:
        for key in ("name", "relationship", "source_id"):
            _require_text(relation, key, location)
        if relation["source_id"] not in source_ids:
            raise ValueError(f"{location}: relation sans source connue.")
    if prospect["prequalification_status"] == "REJECTED" and not prospect["negative_signals"]:
        raise ValueError(f"{location}: un rejet exige au moins un signal négatif.")


def _merge_records(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fusionne les mêmes entités sans supprimer les sources ni contradictions."""

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[record["entity_key"]].append(record)
    merged: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    for entity_key in sorted(grouped):
        group = grouped[entity_key]
        primary = deepcopy(group[0])
        if len(group) == 1:
            merged.append(primary)
            continue
        seen_urls = {source["url"] for source in primary["sources"]}
        for duplicate in group[1:]:
            primary["facts"].extend(deepcopy(duplicate["facts"]))
            primary["inferences"].extend(deepcopy(duplicate["inferences"]))
            primary["missing_information"].extend(deepcopy(duplicate["missing_information"]))
            primary["negative_signals"].extend(deepcopy(duplicate["negative_signals"]))
            primary["related_entities"].extend(deepcopy(duplicate["related_entities"]))
            for source in duplicate["sources"]:
                if source["url"] not in seen_urls:
                    primary["sources"].append(deepcopy(source))
                    seen_urls.add(source["url"])
        primary["merged_from_prospect_ids"] = [item["prospect_id"] for item in group]
        statuses = {item["prequalification_status"] for item in group}
        primary["prequalification_status"] = (
            "CANDIDATE" if "CANDIDATE" in statuses else "UNCERTAIN" if "UNCERTAIN" in statuses else "REJECTED"
        )
        audit.append({
            "entity_key": entity_key,
            "action": "merged_exact_entity_key",
            "prospect_ids": primary["merged_from_prospect_ids"],
            "sources_preserved": len(primary["sources"]),
            "status_conflict_preserved_as": primary["prequalification_status"],
        })
        merged.append(primary)
    return merged, audit


def _contradictions(prospect: dict[str, Any]) -> list[dict[str, Any]]:
    values_by_field: dict[str, set[str]] = defaultdict(set)
    sources_by_field: dict[str, set[str]] = defaultdict(set)
    for fact in prospect["facts"]:
        values_by_field[fact["field"]].add(str(fact["value"]))
        sources_by_field[fact["field"]].add(fact["source_id"])
    return [
        {"field": field, "values": sorted(values), "source_ids": sorted(sources_by_field[field])}
        for field, values in sorted(values_by_field.items()) if len(values) > 1
    ]


def prepare(raw_path: Path = RAW_PATH, opposition_path: Path = OPPOSITION_PATH) -> dict[str, Any]:
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    opposition = json.loads(opposition_path.read_text(encoding="utf-8"))
    _assert_no_scoring_fields(raw)
    _assert_no_scoring_fields(opposition)
    records = raw.get("prospects")
    if not isinstance(records, list) or not records:
        raise ValueError("prospects_raw.json doit contenir une liste non vide de prospects.")
    for record in records:
        _validate_prospect(record)
    opposition_keys = {
        item["entity_key"] for item in opposition.get("oppositions", [])
        if item.get("status") == "DO_NOT_CONTACT"
    }
    merged, merge_audit = _merge_records(records)
    audit: list[dict[str, Any]] = merge_audit[:]
    prepared: list[dict[str, Any]] = []
    for record in merged:
        item = deepcopy(record)
        if item["entity_key"] in opposition_keys:
            item["prequalification_status"] = "REJECTED"
            item["negative_signals"].append({
                "kind": "opposition",
                "detail": "Entité présente dans la liste locale d'opposition.",
                "source_id": "local_opposition_list",
            })
            audit.append({"entity_key": item["entity_key"], "action": "excluded_do_not_contact"})
        item["contradictions"] = _contradictions(item)
        item["contacting_performed"] = False
        item["scoring_performed"] = False
        prepared.append(item)
    candidates = [item for item in prepared if item["prequalification_status"] != "REJECTED"]
    rejected = [item for item in prepared if item["prequalification_status"] == "REJECTED"]
    summary = {
        "schema_version": 1,
        "prepared_at": date.today().isoformat(),
        "phase": "PRE_SCORING_ONLY",
        "scoring_performed": False,
        "ranking_performed": False,
        "contact_messages_prepared": False,
        "contacts_sent": 0,
        "counts": dict(sorted(Counter(item["prequalification_status"] for item in prepared).items())),
        "deduplication_actions": len(audit),
        "opposition_entries_checked": len(opposition.get("oppositions", [])),
    }
    _write(DATA / "candidates_pre_scoring.json", {
        "schema_version": 1, "phase": "PRE_SCORING_ONLY", "prospects": candidates,
    })
    _write(DATA / "rejected_prequalification.json", {
        "schema_version": 1, "phase": "PRE_SCORING_ONLY", "prospects": rejected,
    })
    _write(DATA / "deduplication_audit.json", {
        "schema_version": 1, "actions": audit,
        "relations_retained_without_merge": [
            {"prospect_id": item["prospect_id"], "related_entities": item["related_entities"]}
            for item in prepared if item["related_entities"]
        ],
    })
    _write(DATA / "preparation_summary.json", summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(prepare(), ensure_ascii=False, indent=2))
