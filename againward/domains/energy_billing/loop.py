"""Bounded local Investigator with persistent budgets and Python-owned state.

This is an internal analysis entrypoint on an already approved source batch.
It does not create privacy approval, supply a financial oracle, or approve delivery.
"""
from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
import fcntl
import os
from pathlib import Path
import time
from typing import Any

from againward.core.artifact_store import read_json, transaction, write_json
from againward.documents.contracts import DocumentError, SourceBatch
from againward.documents.readers import read_document
from againward.documents.sources import assert_document_action, verify_batch
from againward.evidence.hashing import stable_hash

from .agenda import next_issue
from .calculation import calculate, readiness
from .investigator import propose_action, semantic_hash, semantic_progress
from .protocol import BillingFailure
from .provider import ModelBoundary, Transport
from .reader import read_source, source_context
from .review import request_review
from .state import commit_event, load_state

VERSION = "energy-billing-investigator-v2"
LEGACY_VERSION = "energy-billing-investigator-v1"


@contextmanager
def runtime_lease(root: Path):
    """Separate job lock: each domain commit and call reservation stays durable."""
    directory = root / "energy_billing"
    if any(p.is_symlink() for p in (directory, *directory.parents)):
        raise BillingFailure("RUNTIME_REPLAY_INVALID", stage="RUNTIME", expected="unlinked workspace")
    fd = os.open(directory / "investigator.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "r+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise BillingFailure("RUNTIME_BUSY", stage="RUNTIME", expected="one active investigator") from exc
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


@dataclass(frozen=True)
class Budget:
    max_turns: int = 24
    max_model_calls: int = 32
    max_rereads: int = 4
    max_stagnant_turns: int = 3
    max_repeated_state: int = 4
    max_repeated_rejection: int = 2
    max_protocol_repairs: int = 4
    max_provider_resumes: int = 2
    wall_seconds: int = 900

    def __post_init__(self) -> None:
        if any(type(v) is not int or not 1 <= v <= 3600 for v in asdict(self).values()):
            raise ValueError("Positive bounded integer budgets required")
        if self.max_provider_resumes > 2:
            raise ValueError("At most two provider continuations")


def inspect_sources(state: dict[str, Any], issue: dict[str, Any], root: Path) -> dict[str, dict[str, Any]]:
    targets = set(issue["targets"])
    for rid in targets & state["relations"].keys():
        row = state["relations"][rid]
        targets = targets | {row["invoice_id"], row["tariff_id"]}
    sources = {row["source_id"] for oid, row in state["occurrences"].items() if oid in targets}
    if "source_id" in issue:
        sources.add(issue["source_id"])
    batch = SourceBatch.from_dict(state["batch"])
    documents = tuple(d for d in batch.documents if d.source_id in sources)
    try:
        verify_batch(replace(batch, documents=documents), root)
        return {d.source_id: source_context(read_document(d, root)) for d in documents}
    except OSError as exc:
        raise BillingFailure("SOURCE_UNREADABLE", stage="SOURCE", expected="accessible original source bytes",
                             cause=type(exc).__name__) from exc


def investigate(root: Path, *, model: str, transport: Transport, budget: Budget = Budget(),
                clock: Callable[[], float] = time.perf_counter,
                resume_provider_failure: bool = False) -> dict[str, Any]:
    """Explicit bounded provider recovery or external semantic change; no resets.

    A checkpoint is saved before each model call. An interrupted invocation is
    explicit and cannot silently replay an unknown remote call. The workspace
    job lock prevents concurrent investigators from sharing/resetting budgets.
    """
    if type(resume_provider_failure) is not bool:
        raise ValueError("Provider continuation must be an explicit boolean")
    assert_document_action(root, mutation=True)
    with runtime_lease(root):
        state = load_state(root)
        path = root / "energy_billing" / "investigator.json"
        if path.exists():
            saved = read_json(path)
            log = {k: v for k, v in saved.items() if k != "receipt_sha256"}
            legacy = log.get("schema_version") == LEGACY_VERSION
            expected_budget = asdict(budget)
            if legacy:
                expected_budget.pop("max_provider_resumes")
            if (saved.get("receipt_sha256") != stable_hash(log)
                    or log.get("schema_version") not in {VERSION, LEGACY_VERSION}
                    or log.get("model") != model or log.get("budget") != expected_budget
                    or (legacy and budget.max_provider_resumes != 2)):
                raise BillingFailure("RUNTIME_REPLAY_INVALID", stage="RUNTIME", expected="same hashed runtime/model/budgets")
            if log["pending"]:
                raise BillingFailure("RUNTIME_INTERRUPTED", stage="RUNTIME", expected="operator inspection of interrupted turn",
                                     model_calls_reserved=log["model_calls"])
            terminal = log["terminal_reason"]
            if resume_provider_failure:
                if terminal is None or terminal["code"] != "MODEL_PROVIDER_FAILURE":
                    raise BillingFailure("RUNTIME_RESUME_REFUSED", stage="RUNTIME",
                                         expected="explicit terminal provider failure, no pending invocation")
                resumes = log.get("provider_resumes", []) if legacy else log["provider_resumes"]
                if len(resumes) >= budget.max_provider_resumes:
                    raise BillingFailure("RESOURCE_LIMIT", stage="RUNTIME", expected="remaining provider resumptions",
                                         budget="max_provider_resumes", limit=budget.max_provider_resumes)
                continuation = {"previous_receipt_sha256": saved["receipt_sha256"],
                                "previous_schema_version": log["schema_version"], "failure": terminal,
                                "state_sha256": log["state_sha256"], "current_state_sha256": stable_hash(state),
                                "model_calls": log["model_calls"], "turns": log["turns"],
                                "rereads": log["rereads"], "protocol_repairs": log["protocol_repairs"],
                                "wall_seconds": log["wall_seconds"]}
            elif terminal is not None and (terminal["code"] == "MODEL_PROVIDER_FAILURE"
                                          or log["state_sha256"] == stable_hash(state)):
                return log
            if legacy:
                # Verify the original receipt first; migrate without changing any
                # prior failure, step, evidence or lifetime resource counter.
                log.update(schema_version=VERSION, budget=asdict(budget), provider_resumes=[])
            if resume_provider_failure:
                log["provider_resumes"].append(continuation)
        else:
            if resume_provider_failure:
                raise BillingFailure("RUNTIME_RESUME_REFUSED", stage="RUNTIME", expected="existing failed runtime")
            log = {"schema_version": VERSION, "model": model, "budget": asdict(budget),
                   "model_calls": 0, "turns": 0, "rereads": 0, "protocol_repairs": 0,
                   "wall_seconds": 0.0, "stagnant_turns": 0, "visited": {}, "rejections": {},
                   "steps": [], "diagnostics": [], "terminal_reason": None, "pending": False,
                   "state_sha256": stable_hash(state), "calculation": None, "readiness": None,
                   "provider_resumes": []}
        log["terminal_reason"] = None
        log["calculation"] = None
        started, previous_wall = clock(), log["wall_seconds"]
        feedback: dict[str, Any] | None = None
        if log["steps"]:
            previous_step = log["steps"][-1]
            feedback = {"issue_id": previous_step["issue_id"],
                        "value": {key: previous_step[key] for key in ("inspection", "rejection") if key in previous_step}}

        def save() -> None:
            log["wall_seconds"] = previous_wall + max(0.0, clock() - started)
            log["state_sha256"] = stable_hash(state)
            with transaction(root):
                write_json(path, {**log, "receipt_sha256": stable_hash(log)})

        def limit(name: str) -> None:
            raise BillingFailure("RESOURCE_LIMIT", stage="RUNTIME", expected="remaining " + name,
                                 budget=name, limit=getattr(budget, name))

        def bounded(prompt: str, schema: dict[str, Any]) -> bytes:
            if log["model_calls"] >= budget.max_model_calls:
                limit("max_model_calls")
            if previous_wall + clock() - started >= budget.wall_seconds:
                limit("wall_seconds")
            log["model_calls"] += 1
            save()  # Reservation survives an interrupted provider invocation.
            raw = transport(prompt, schema)
            if previous_wall + clock() - started >= budget.wall_seconds:
                limit("wall_seconds")
            return raw

        def observe_attempt(attempt: int) -> None:
            if attempt:
                if log["protocol_repairs"] >= budget.max_protocol_repairs:
                    limit("max_protocol_repairs")
                log["protocol_repairs"] += 1

        boundary = ModelBoundary(bounded, attempt_observer=observe_attempt)
        save()  # Persist continuation intent before another turn or remote call.
        try:
            while True:
                if log["turns"] >= budget.max_turns:
                    limit("max_turns")
                if previous_wall + clock() - started >= budget.wall_seconds:
                    limit("wall_seconds")
                before = semantic_hash(state)
                previous_state = state
                issue = next_issue(state, root)
                contexts = inspect_sources(state, issue, root)
                issue["source_handles"] = {sid: [{"location": u["location"], "unit_sha256": u["unit_sha256"]}
                                                 for u in c["units"]] for sid, c in contexts.items()}
                # Feedback is only from this focused issue, never another dossier.
                if feedback is not None and feedback["issue_id"] == issue["issue_id"]:
                    issue["feedback"] = feedback["value"]
                log["turns"] += 1
                log["pending"] = True
                save()
                step: dict[str, Any] = {"turn": log["turns"], "issue_id": issue["issue_id"], "issue_code": issue["code"],
                                        "before_semantic_sha256": before, "model_calls_before": log["model_calls"]}
                turn_started = clock()
                result: dict[str, Any] = {}
                try:
                    response = propose_action(state, issue, boundary)
                    action = response["action"]
                    step["action"] = action
                    kind = action["type"]
                    if kind in {"DECLARE_INVOICE", "DECLARE_TARIFF", "LINK_TARIFF"}:
                        state = commit_event(state, {"type": "ACTION", "focus": issue["issue_id"], "response": response}, root)
                    elif kind == "REQUEST_REVIEW":
                        digest = request_review(state, action["target"], root, model=model, boundary=boundary)
                        state = commit_event(state, {"type": "REVIEW", "receipt_sha256": digest}, root)
                    elif kind == 'REQUEST_DISPOSITION':
                        from .disposition import request_disposition
                        digest = request_disposition(state, action, root, model=model, boundary=boundary)
                        state = commit_event(state, {'type': 'DISPOSITION', 'receipt_sha256': digest}, root)
                    elif kind == "REQUEST_REREAD":
                        if log["rereads"] >= budget.max_rereads:
                            limit("max_rereads")
                        log["rereads"] += 1
                        save()
                        digest = read_source(SourceBatch.from_dict(state["batch"]), action["source_id"], root,
                                             model=model, boundary=boundary, role="RECOVERY")
                        state = commit_event(state, {"type": "READ", "receipt_sha256": digest}, root)
                    elif kind == "REQUEST_INSPECTION":
                        context = contexts[action["source_id"]]
                        unit = next(u for u in context["units"] if u["location"] == action["location"])
                        if len(unit["text"]) > 8000:
                            raise BillingFailure("RESOURCE_LIMIT", stage="INSPECTION", expected="native unit <=8000 characters")
                        result = {"inspection": unit}
                    elif kind == "MARK_UNRESOLVED":
                        log["terminal_reason"] = {"code": "UNRESOLVED", "stage": "INVESTIGATOR",
                                                  "issue": {k: v for k, v in issue.items() if k != "feedback"}, "reason": action["reason"]}
                    elif kind == "PROPOSE_READY":
                        decision = readiness(state, root)
                        if decision["ready"]:
                            log["calculation"] = calculate(state, root)
                            log["terminal_reason"] = {"code": "CALCULATION_CREATED", "stage": "CALCULATION"}
                        else:
                            result = {"rejection": decision["root_issues"][0]}
                except (BillingFailure, DocumentError) as exc:
                    diagnostic = exc.diagnostic if isinstance(exc, BillingFailure) else {"code": exc.code, "stage": "SOURCE"}
                    if exc.code not in {"MATERIAL_EVIDENCE_MISSING", "OCCURRENCE_AMBIGUOUS", "RELATION_AMBIGUOUS", "BUSINESS_AMBIGUITY"}:
                        raise
                    result = {"rejection": diagnostic}
                step.update(result)
                if "rejection" in result:
                    # Model wording/call count are not a new rejection family.
                    sig = stable_hash({"issue": issue["issue_id"], "code": result["rejection"]["code"],
                                       "path": result["rejection"].get("path"), "before": before})
                    log["rejections"][sig] = log["rejections"].get(sig, 0) + 1
                    if log["rejections"][sig] >= budget.max_repeated_rejection:
                        log["terminal_reason"] = {"code": "REPEATED_REJECTION", "stage": "RUNTIME", "root_cause": result["rejection"]}
                feedback = {"issue_id": issue["issue_id"], "value": result}
                after = semantic_hash(state)
                progress = semantic_progress(previous_state, state)
                log["stagnant_turns"] = 0 if progress else log["stagnant_turns"] + 1
                log["visited"][after] = log["visited"].get(after, 0) + 1
                step.update(after_semantic_sha256=after, progress=progress, model_calls_after=log["model_calls"],
                            wall_seconds=max(0.0, clock() - turn_started))
                log["steps"].append(step)
                log["pending"] = False
                if log["terminal_reason"] is None:
                    if log["stagnant_turns"] >= budget.max_stagnant_turns:
                        log["terminal_reason"] = {"code": "NO_SEMANTIC_PROGRESS", "stage": "RUNTIME", "issue_id": issue["issue_id"]}
                    elif log["visited"][after] >= budget.max_repeated_state:
                        log["terminal_reason"] = {"code": "REPEATED_STATE", "stage": "RUNTIME", "issue_id": issue["issue_id"]}
                save()
                if log["terminal_reason"] is not None:
                    break
        except (BillingFailure, DocumentError) as exc:
            log["terminal_reason"] = exc.diagnostic if isinstance(exc, BillingFailure) else {"code": exc.code, "stage": "SOURCE"}
            log["pending"] = False
        log["diagnostics"].extend(boundary.diagnostics)
        state = load_state(root)
        log["readiness"] = readiness(state, root)
        save()
        return log
