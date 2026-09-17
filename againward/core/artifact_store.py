"""Recoverable JSON transactions for local case artifacts.

JSON remains the public format. A fsynced redo journal is the commit point;
interrupted materialization is completed under the same process lock. Readers
must refuse a pending journal. This is cooperative local-process concurrency,
not protection against arbitrary external edits or broken storage hardware.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from pathlib import Path

JOURNAL = ".artifact-transaction.json"
LOCK = ".artifact.lock"
_active = ContextVar("artifact_transaction", default=None)


def _encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+"\n"


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def _sync_directory(root):
    descriptor = os.open(root, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _target(root, relative):
    part = Path(relative)
    if part.is_absolute() or ".." in part.parts or not part.parts or part.name in {JOURNAL, LOCK}:
        raise ValueError("Unsafe transaction path.")
    path = root / part
    if path.resolve().is_relative_to(root) is False:
        raise ValueError("Transaction path escapes case.")
    if any(parent.is_symlink() for parent in [path, *path.parents] if parent != root.parent):
        raise ValueError("Transaction paths must not be symlinks.")
    return path


def atomic_write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = _encode(value)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _sync_directory(path.parent)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def assert_artifacts_consistent(root):
    root = Path(root).resolve()
    active = _active.get()
    if (root / JOURNAL).exists() and not (active and active["root"] == root):
        raise ValueError("ARTIFACT_RECOVERY_REQUIRED: run manage_investigation.py recover-artifacts CASE.")


def read_json(path):
    path = Path(path).resolve()
    active = _active.get()
    if active and path in active["writes"]:
        return json.loads(_encode(active["writes"][path]))
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path.name}.")
    return value


def write_json(path, value):
    path = Path(path).resolve()
    active = _active.get()
    if active:
        _target(active["root"], str(path.relative_to(active["root"])))
        active["before"].setdefault(path, _digest(path))
        active["writes"][path] = json.loads(_encode(value))
    else:
        atomic_write_json(path, value)


def artifact_sha256(path):
    """Hash the bytes that will be materialized, including a staged JSON value."""
    path = Path(path).resolve()
    active = _active.get()
    if active and path in active["writes"]:
        return hashlib.sha256(_encode(active["writes"][path]).encode("utf-8")).hexdigest()
    return _digest(path)


def _replay(root):
    journal = root / JOURNAL
    if not journal.exists():
        return False
    payload = read_json(journal)
    entries = payload.get("entries")
    if payload.get("schema_version") != "againward-artifact-transaction-v1" or not isinstance(entries, list) or not entries:
        raise ValueError("Invalid artifact transaction journal.")
    targets = []
    for entry in entries:
        path = _target(root, entry["path"])
        after = hashlib.sha256(_encode(entry["value"]).encode("utf-8")).hexdigest()
        if after != entry["after_sha256"] or _digest(path) not in {entry["before_sha256"], after}:
            raise ValueError("Artifact changed outside transaction; recovery refused.")
        if path in targets:
            raise ValueError("Duplicate transaction target.")
        targets.append(path)
    # Validate the entire journal before replaying any entry.
    for path, entry in zip(targets, entries):
        atomic_write_json(path, entry["value"])
    journal.unlink()
    _sync_directory(root)
    return True


@contextmanager
def transaction(root):
    root = Path(root).resolve()
    existing = _active.get()
    if existing:
        if existing["root"] != root:
            raise ValueError("Cross-case nested transaction is not supported.")
        yield existing
        return
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / LOCK
    if lock_path.is_symlink() or (root / JOURNAL).is_symlink():
        raise ValueError("Transaction metadata must not be symlinks.")
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Case is being updated by another process; retry later.") from exc
        _replay(root)
        active = {"root": root, "writes": {}, "before": {}}
        token = _active.set(active)
        try:
            yield active
            if active["writes"]:
                entries = []
                for path, value in active["writes"].items():
                    if _digest(path) != active["before"][path]:
                        raise ValueError("Concurrent external artifact change; commit refused.")
                    entries.append({"path": str(path.relative_to(root)), "value": value,
                                    "before_sha256": active["before"][path],
                                    "after_sha256": hashlib.sha256(_encode(value).encode("utf-8")).hexdigest()})
                atomic_write_json(root / JOURNAL, {"schema_version":"againward-artifact-transaction-v1", "entries":entries})
                # Do not consult the staged overlay while materializing the journal.
                _active.reset(token)
                token = _active.set(None)
                _replay(root)
        finally:
            _active.reset(token)
            fcntl.flock(lock, fcntl.LOCK_UN)


def case_mutation(function):
    """Resolve aliases before acquiring the per-analysis-directory lock."""
    @wraps(function)
    def wrapped(case_directory, *args, **kwargs):
        from .workflow_paths import resolve_analysis_directory
        with transaction(resolve_analysis_directory(case_directory)):
            return function(case_directory, *args, **kwargs)
    return wrapped


def case_read(function):
    """Read a coherent set without creating files or recovering state implicitly."""
    @wraps(function)
    def wrapped(case_directory, *args, **kwargs):
        from .workflow_paths import resolve_analysis_directory
        root = resolve_analysis_directory(case_directory)
        active = _active.get()
        if active and active["root"] == root.resolve():
            return function(case_directory, *args, **kwargs)
        lock_path = root / LOCK
        if lock_path.is_symlink():
            raise ValueError("Transaction lock must not be a symlink.")
        if not lock_path.exists():
            assert_artifacts_consistent(root)
            return function(case_directory, *args, **kwargs)
        with lock_path.open("r") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ValueError("Case is being updated; retry reading later.") from exc
            try:
                assert_artifacts_consistent(root)
                return function(case_directory, *args, **kwargs)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
    return wrapped


def recover_artifacts(case_directory):
    from .workflow_paths import resolve_analysis_directory
    root = resolve_analysis_directory(case_directory)
    pending = (root / JOURNAL).exists()
    with transaction(root):
        pass
    return {"recovered":pending, "analysis_root":str(root)}
