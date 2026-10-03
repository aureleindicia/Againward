"""Small schema-native CLI transport, private diagnostics and bounded repair."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from againward.evidence.hashing import stable_hash

from .protocol import VERSION, BillingFailure, decode, validate

Transport = Callable[[str, dict[str, Any]], bytes]


def _private_write(root: Path, name: str, body: bytes) -> None:
    if any(p.is_symlink() for p in (root, *root.parents)):
        raise BillingFailure("EVALUATION_RETENTION_FAILURE", stage="PROVIDER", expected="unlinked private directory")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    path = root / name
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(body)


@dataclass
class CodexTransport:
    model: str
    timeout_seconds: int = 90
    evaluation_root: Path | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, prompt: str, schema_body: dict[str, Any]) -> bytes:
        invocation = str(uuid.uuid4())
        started = time.perf_counter()
        receipt: dict[str, Any] = {"invocation_id": invocation, "model": self.model,
            "schema_version": VERSION, "schema_sha256": stable_hash(schema_body),
            "state_mutated": False, "raw_retained": self.evaluation_root is not None}
        with tempfile.TemporaryDirectory(prefix="againward-billing-model-") as directory:
            temporary = Path(directory)
            schema = temporary / "schema.json"
            output = temporary / "response.json"
            schema.write_text(json.dumps(schema_body), encoding="utf-8")
            command = ["codex", "exec", "--ephemeral", "--skip-git-repo-check",
                "--sandbox", "read-only", "--cd", str(temporary), "--model", self.model,
                "--config", "model_reasoning_effort=low", "--output-schema", str(schema),
                "--output-last-message", str(output), "-"]
            streams: dict[str, bytes] = {"schema.json": schema.read_bytes()}
            failure = None
            raw = b""
            try:
                result = subprocess.run(command, input=prompt.encode("utf-8"), capture_output=True,
                                        timeout=self.timeout_seconds, check=False)
                streams.update({"stdout.bin": result.stdout, "stderr.bin": result.stderr})
                receipt["exit_code"] = result.returncode
                raw = output.read_bytes() if output.is_file() else b""
                if result.returncode:
                    # Schema rejection is a model-contract failure, not domain unsupported.
                    stderr = result.stderr.lower()
                    schema_failure = any(fragment in stderr for fragment in (
                        b"invalid schema", b"invalid_json_schema", b"schema_validation_error"))
                    failure = BillingFailure("MODEL_PROTOCOL_FAILURE" if schema_failure else "MODEL_PROVIDER_FAILURE",
                        stage="PROVIDER", expected="provider accepts exact output schema" if schema_failure else "successful CLI",
                        cause="SCHEMA_REJECTED" if schema_failure else "CLI_EXIT", exit_code=result.returncode)
                elif not raw:
                    failure = BillingFailure("MODEL_PROTOCOL_INVALID", stage="PROVIDER", expected="nonempty output",
                                             cause="EMPTY_RESPONSE")
            except subprocess.TimeoutExpired as exc:
                streams.update({"stdout.bin": exc.stdout or b"", "stderr.bin": exc.stderr or b""})
                failure = BillingFailure("MODEL_PROVIDER_FAILURE", stage="PROVIDER", expected="CLI within timeout",
                                         cause="TIMEOUT")
            except OSError as exc:
                failure = BillingFailure("MODEL_PROVIDER_FAILURE", stage="PROVIDER", expected="available CLI",
                                         cause=type(exc).__name__)
            finally:
                receipt.update(duration_seconds=time.perf_counter() - started,
                    response_sha256=hashlib.sha256(raw).hexdigest(), response_bytes=len(raw),
                    stream_sha256={key: hashlib.sha256(value).hexdigest() for key, value in streams.items()})
                if failure is not None:
                    receipt["failure"] = dict(failure.diagnostic)
                self.calls.append(receipt)
                if self.evaluation_root is not None:
                    retained = self.evaluation_root / invocation
                    for name, body in {**streams, "response.bin": raw,
                                       "receipt.json": json.dumps(receipt).encode("utf-8")}.items():
                        _private_write(retained, name, body)
            if failure is not None:
                failure.diagnostic.update({key: value for key, value in receipt.items() if key != "failure"})
                raise failure
            return raw


@dataclass
class ModelBoundary:
    transport: Transport
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    calls: int = 0
    attempt_observer: Callable[[int], None] | None = None

    def ask(self, prompt: str, schema: dict[str, Any], *, stage: str,
            checker: Callable[[Any], None] | None = None,
            source_id: str | None = None) -> dict[str, Any]:
        """At most one model repair. State mutation belongs to caller after return."""
        serialized_schema = json.dumps(schema)
        references = "Evidence IDs must be distinct. " if '"evidence_ids"' in serialized_schema else ""
        base = prompt + "\n" + references + "Never encode a JSON structure inside a string. " \
            "Return only the direct JSON object defined by this exact schema:\n" + serialized_schema
        attempt_prompt = base
        for attempt in range(2):
            raw = b""
            try:
                if self.attempt_observer is not None:
                    self.attempt_observer(attempt)
                self.calls += 1
                raw = self.transport(attempt_prompt, schema)
                value = decode(raw, stage=stage)
                if checker is None:
                    validate(value, schema, stage=stage)
                else:
                    checker(value)
                return value
            except BillingFailure as exc:
                diagnostic = {**exc.diagnostic, "stage": stage, "retry_count": attempt,
                    "schema_sha256": stable_hash(schema), "source_id": source_id,
                    "response_sha256": hashlib.sha256(raw).hexdigest() if raw else
                        exc.diagnostic.get("response_sha256"), "state_mutated": False}
                self.diagnostics.append(diagnostic)
                if exc.code != "MODEL_PROTOCOL_INVALID":
                    # Retain the causal metadata (budget, root IDs, invocation,
                    # transport cause), not only a generic wrapper error code.
                    exc.diagnostic = diagnostic
                    raise
                if attempt == 1:
                    raise BillingFailure("MODEL_PROTOCOL_FAILURE", stage=stage,
                        expected="valid output after one repair", root_cause=diagnostic,
                        retry_count=1) from exc
                # Schema-owned diagnostic only, not previous untrusted response or a new business answer.
                attempt_prompt = base + "\nThe last response was rejected without state mutation. Repair this exact " \
                    "protocol error; never change evidence or infer a missing business fact:\n" + json.dumps(diagnostic)
        raise RuntimeError("Unreachable bounded repair")
