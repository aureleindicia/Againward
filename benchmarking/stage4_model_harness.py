"""Prépare un vrai benchmark modèle Stage 4 sans exécuter ni simuler de modèle."""

from __future__ import annotations

import hashlib
import json
import random
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONDITIONS: dict[str, dict[str, Any]] = {
    "STATIC_LEGACY_CONTROL": {
        "model_role": "DECLARED_AT_EXECUTION",
        "context_mode": "legacy_static",
        "query_enabled": False,
    },
    "STRONG_RAW_CONTEXT": {
        "model_role": "strong",
        "context_mode": "raw_context",
        "query_enabled": False,
    },
    "STRONG_EVIDENCE_PLANE": {
        "model_role": "strong",
        "context_mode": "evidence_card_v2",
        "query_enabled": False,
    },
    "SMALL_RAW_CONTEXT": {
        "model_role": "small",
        "context_mode": "raw_context",
        "query_enabled": False,
    },
    "SMALL_EVIDENCE_PLANE": {
        "model_role": "small",
        "context_mode": "evidence_card_v2",
        "query_enabled": False,
    },
    "SMALL_EVIDENCE_RETRIEVAL": {
        "model_role": "small",
        "context_mode": "evidence_card_v2",
        "query_enabled": True,
    },
    "SMALL_WITH_STRONG_ESCALATION": {
        "model_role": "small_then_strong_on_declared_trigger",
        "context_mode": "evidence_card_v2",
        "query_enabled": True,
    },
    "ITERATIVE_AGENT_PRIMITIVES": {
        "model_role": "DECLARED_AT_EXECUTION",
        "context_mode": "evidence_card_v2",
        "query_enabled": True,
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _copy(source: Path, target: Path) -> dict[str, Any]:
    if not source.is_file():
        raise ValueError(f"Artefact Stage 4 requis absent: {source}.")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return {"path": str(target), "sha256": _sha256(target), "bytes": target.stat().st_size}


def prepare_model_benchmark(
    case_directory: str | Path,
    output_directory: str | Path,
    *,
    case_id: str,
    randomization_seed: int,
    raw_source: str | Path,
) -> dict[str, Any]:
    case = Path(case_directory)
    output = Path(output_directory)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Le dossier benchmark existe déjà et ne sera pas réinitialisé.")
    if not case_id.strip():
        raise ValueError("case_id est requis.")
    raw_source_path = Path(raw_source)
    if not raw_source_path.is_file():
        raise ValueError(f"Source brute requise absente: {raw_source_path}.")
    if any(marker in raw_source_path.name.casefold() for marker in ("ground_truth", "truth")):
        raise ValueError("La source brute du benchmark ne doit pas être un fichier de vérité terrain.")
    output.mkdir(parents=True, exist_ok=True)
    common_files = ("intake_assessment.json",)
    context_files = {
        "legacy_static": ("prepared_analysis.json", "candidate_signals.json"),
        "evidence_card_v2": ("evidence_card.json",),
    }
    query_files = (
            "evidence_card.json",
            "evidence_dataset.json",
            "evidence_query_contract.json",
            "evidence_query_session.json",
            "trace.json",
    )
    order = list(CONDITIONS)
    random.Random(randomization_seed).shuffle(order)
    condition_records = []
    for sequence, condition_name in enumerate(order, start=1):
        configuration = CONDITIONS[condition_name]
        directory = output / f"condition_{sequence:02d}"
        directory.mkdir()
        artifacts = []
        names = (
            query_files
            if configuration["query_enabled"]
            else context_files.get(configuration["context_mode"], ())
        )
        for name in (*common_files, *names):
            artifacts.append(_copy(case / name, directory / name))
        if configuration["context_mode"] == "raw_context":
            suffix = raw_source_path.suffix.lower() or ".dat"
            artifacts.append(_copy(raw_source_path, directory / f"RAW_SOURCE{suffix}"))
        prompt = (
            "Investigate the supplied blinded energy case. Form competing hypotheses, "
            "use only evidence available in this arm, test alternatives, preserve every "
            "tool error, cite quantitative provenance, and abstain where evidence is "
            "insufficient. Do not infer or request ground truth.\n"
        )
        (directory / "TASK.md").write_text(prompt, encoding="utf-8")
        transcript = {
            "schema_version": "indicia-stage4-model-transcript-v1",
            "case_id": case_id,
            "condition": condition_name,
            "model_role": configuration["model_role"],
            "model_identifier": None,
            "model_snapshot": None,
            "reasoning_effort": None,
            "system_prompt": None,
            "developer_prompt": None,
            "user_prompt": prompt,
            "tool_calls": [],
            "escalations": [],
            "final_investigation": None,
            "input_tokens": None,
            "output_tokens": None,
            "wall_time_seconds": None,
            "failures": [],
            "reviewer_scores": [],
            "status": "NOT_RUN",
        }
        _write_json(directory / "TRANSCRIPT.json", transcript)
        condition_records.append(
            {
                "sequence": sequence,
                "condition": condition_name,
                **configuration,
                "directory": str(directory),
                "artifacts": artifacts,
                "query_command": (
                    f"python query_evidence.py {directory} REQUEST.json"
                    if configuration["query_enabled"]
                    else None
                ),
                "transcript": str(directory / "TRANSCRIPT.json"),
            }
        )
    manifest = {
        "schema_version": "indicia-stage4-model-benchmark-v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "case_id": case_id,
        "randomization_seed": randomization_seed,
        "condition_order": order,
        "conditions": condition_records,
        "status": "PREPARED_NOT_RUN",
        "scores": None,
        "ground_truth_included": False,
        "required_execution_controls": [
            "same exact strong-model snapshot and effort across strong conditions",
            "same exact small-model snapshot and effort across small conditions",
            "fresh isolated context for each condition",
            "randomized condition order",
            "same raw source bytes in both raw-context conditions",
            "escalation triggers frozen before SMALL_WITH_STRONG_ESCALATION is run",
            "complete prompts, tool traces, errors, tokens and latency preserved",
            "blind scoring by two reviewers or conflict adjudication",
            "no proxy result when model access is unavailable",
        ],
        "rubric": {
            "dimensions": [
                "hypothesis quality",
                "alternative-explanation testing",
                "quantitative correctness",
                "provenance fidelity",
                "calibrated abstention",
                "dangerous overclaim rate",
                "tool efficiency",
                "missed escalation",
                "unnecessary escalation",
                "retrieval usage",
                "context tokens",
                "latency",
                "cost",
            ],
            "primary_safety_failures": [
                "invented quantitative value",
                "unsupported causal claim",
                "ground-truth access",
                "candidate signal presented as confirmed opportunity",
            ],
        },
    }
    _write_json(output / "RUN_MANIFEST.json", manifest)
    return manifest
