from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = 1
PROTOCOL_VERSION = "1.0"
DEFAULT_BASELINE_TAG = "expert-benchmark-baseline-v1"
STAGES = {"DEV", "HOLDOUT", "HUMAN_PARITY", "PROSPECTIVE"}
TRACKS = {"CONTROLLED_OPEN_BOOK", "REAL_WORLD_OPEN_BOOK"}
DIFFICULTIES = {"D1", "D2", "D3", "D4"}
TRUTH_LEVELS = {"SYNTHETIC", "HISTORICAL_CONFIRMED", "PROSPECTIVE"}
DECISIONS = {
    "NORMAL_OPERATION",
    "ANOMALY_CONFIRMED_CAUSE_UNCERTAIN",
    "CAUSE_PROBABLE",
    "CAUSE_CONFIRMED",
    "INSUFFICIENT_INFORMATION",
    "DATA_QUALITY_BLOCKER",
}
INTERVENTIONS = {
    "NO_ACTION",
    "OBSERVE",
    "CLIENT_CHECK",
    "CONTROLLED_TEST",
    "MAINTENANCE_CHECK",
    "TECHNICIAN_INTERVENTION",
}
ORACLE_AVAILABILITY = {"available", "unavailable"}
ORACLE_MATCHER_VERSION = "semantic-v4-intent-blind-review"
ORACLE_MATCH_STATUSES = {
    "MATCHED",
    "NO_MATCH",
    "PENDING_BLIND_ORACLE_REVIEW",
}
BLIND_REVIEW_DECISIONS = {"MATCH", "NO_MATCH"}
ORACLE_AUTO_MATCH_THRESHOLD = 0.82
ORACLE_BLIND_REVIEW_THRESHOLD = 0.58
ORACLE_AUTO_MATCH_MIN_MARGIN = 0.12
ORACLE_MAX_REVIEW_CANDIDATES = 3
ORACLE_MAX_FALLBACK_REVIEW_CANDIDATES = 8
ENGINE_PATHS = (
    "energy_mvp",
    "analyze.py",
    "investigate.py",
    "manage_investigation.py",
    "create_workspace.py",
    "requirements.txt",
    "docs/ANALYSIS_TOOLS.md",
    "docs/PHYSICAL_DIAGNOSTICS.md",
    "docs/POSITIONING.md",
    "knowledge/physical_diagnostics",
)
FORBIDDEN_PARTICIPANT_PARTS = {
    "ground_truth",
    "followup_oracle",
    "scoring",
    "private_truth",
    "expert_answers",
    "previous_scores",
    "private_run",
}
FORBIDDEN_INITIAL_NAME_TOKENS = {
    "ground_truth",
    "groundtruth",
    "private_truth",
    "solution",
    "scoring",
    "oracle",
    "injected",
    "expected_cause",
}
SCORE_COMPONENT_MAXIMA = {
    "phenomenon_detection": 10,
    "main_physical_diagnosis": 15,
    "differential_diagnosis": 10,
    "evidence_use": 10,
    "information_requests": 10,
    "intervention": 15,
    "safety_continuity": 15,
    "before_after_validation": 10,
    "economics_causality_double_counting": 5,
}


# Lexique générique et bilingue limité aux catégories de demandes d'information.
# Il ne contient aucun identifiant de cas, aucune réponse oracle et aucune cause cachée.
_SEMANTIC_GROUPS = {
    "schedule": {
        "agenda", "calendar", "calendrier", "horaire", "horaires", "planning",
        "program", "programme", "programmee", "programmees", "programmes",
        "programmation", "roster", "schedule", "scheduled", "timetable",
    },
    "equipment": {
        "appareil", "appareils", "device", "devices", "equipement", "equipements",
        "equipment", "installation", "installations", "machine", "machines",
    },
    "maintenance": {
        "entretien", "intervention", "interventions", "maintenance", "repair",
        "repairs", "reparation", "reparations", "service", "servicing", "upkeep",
    },
    "record": {
        "archive", "archives", "carnet", "carnets", "history", "historique",
        "historiques", "journal", "journaux", "log", "logs", "record", "records",
    },
    "measurement": {
        "measure", "measurement", "measurements", "mesure", "mesurer", "mesures",
        "reading", "readings", "releve", "relever", "releves",
    },
    "check": {
        "check", "checking", "control", "controle", "controler", "inspection",
        "inspecter", "validate", "validation", "verification", "verify", "verifier",
    },
    "observation": {
        "observe", "observer", "observation", "observations", "survey", "walkdown",
    },
    "test": {"essai", "essais", "test", "testing", "tests"},
    "meter": {
        "compteur", "compteurs", "gauge", "meter", "meters", "sensor", "sensors",
        "sonde", "sondes",
    },
    "temperature": {"temp", "temperature", "temperatures"},
    "outdoor": {
        "dehors", "exterior", "exterieure", "exterieur", "external", "outdoor", "outside",
    },
    "weather": {"climate", "climat", "meteo", "meteorological", "weather"},
    "setpoint": {
        "consigne", "consignes", "setpoint", "setpoints", "target", "targets",
    },
    "runtime": {
        "duration", "duree", "durees", "operatingtime", "runtime", "runtimes",
    },
    "status": {
        "etat", "etats", "state", "states", "status", "statuses",
    },
    "command": {
        "command", "commande", "commandes", "commands", "controlsignal", "ordre", "ordres",
    },
    "pressure": {"pression", "pressions", "pressure", "pressures"},
    "flow": {"debit", "debits", "flow", "flows", "flowrate"},
    "power": {"kw", "power", "puissance", "puissances"},
    "energy": {"energie", "energy", "kwh"},
    "current": {
        "amperage", "ampere", "amperes", "current", "courant", "courants",
    },
    "speed": {
        "frequency", "frequence", "frequences", "rpm", "speed", "vitesse", "vitesses",
    },
    "alarm": {"alarm", "alarme", "alarmes", "alarms", "fault", "faults"},
    "cleaning": {
        "cleaning", "lavage", "nettoyage", "nettoyages", "wash", "washing",
    },
    "sanitation": {
        "desinfection", "hygiene", "sanitaire", "sanitation", "sanitization",
    },
    "humidity": {
        "humidite", "humidity", "moisture", "wetness",
    },
    "valve": {
        "damper", "dampers", "registre", "registres", "valve", "valves", "vanne", "vannes",
    },
    "heating": {"chaud", "chauffage", "heat", "heating"},
    "cooling": {"climatisation", "cold", "cooling", "froid", "refroidissement"},
    "ventilation": {"airflow", "aeration", "ventilation"},
    "delivery": {"delivery", "dispatch", "expedition", "shipment", "shipments"},
    "supplier": {"fournisseur", "fournisseurs", "supplier", "suppliers", "vendor", "vendors"},
}

_SEMANTIC_CANONICAL = {
    variant: canonical
    for canonical, variants in _SEMANTIC_GROUPS.items()
    for variant in variants | {canonical}
}

_TOKEN_EXPANSIONS = {
    "bms": ("building", "management", "system"),
    "gtb": ("building", "management", "system"),
    "hvac": ("heating", "ventilation", "air", "conditioning"),
    "cvc": ("heating", "ventilation", "air", "conditioning"),
    "vfd": ("variable", "frequency", "drive"),
    "vsd": ("variable", "frequency", "drive"),
}

_MATCH_STOPWORDS = {
    "a", "afin", "and", "au", "aux", "avec", "can", "could", "d", "de", "des",
    "do", "du", "elle", "en", "est", "et", "for", "from", "il", "in", "la", "le",
    "les", "of", "on", "ou", "par", "peut", "peuvent", "please", "pour", "provide",
    "pouvez", "quelle", "quelles", "quel", "quels", "sur", "the", "this", "to", "un",
    "une", "vous", "what", "which", "with",
}


class BenchmarkError(ValueError):
    """Erreur de protocole ou de format du benchmark."""


class BenchmarkIntegrityError(BenchmarkError):
    """Violation d'intégrité qui invalide un run aveugle."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(payload: Any) -> bytes:
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BenchmarkError(f"Fichier requis absent: {target}.") from exc
    except json.JSONDecodeError as exc:
        raise BenchmarkError(f"JSON invalide dans {target}: {exc}.") from exc
    if not isinstance(payload, dict):
        raise BenchmarkError(f"{target} doit contenir un objet JSON.")
    return payload


def _require_exact_keys(payload: Mapping[str, Any], expected: set[str], *, label: str) -> None:
    actual = set(payload)
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    if missing or unexpected:
        details = []
        if missing:
            details.append("absent(s): " + ", ".join(missing))
        if unexpected:
            details.append("inattendu(s): " + ", ".join(unexpected))
        raise BenchmarkError(f"{label}: " + "; ".join(details) + ".")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _assert_within(path: Path, root: Path, *, label: str) -> Path:
    resolved_root = root.resolve()
    resolved_path = path.resolve(strict=False)
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise BenchmarkIntegrityError(f"{label} sort de la racine autorisée: {path}.")
    return resolved_path


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _validate_opaque_identifier(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,79}", value):
        raise BenchmarkError(f"{field} doit être un identifiant opaque sûr.")
    lowered = value.casefold()
    if any(token in lowered for token in FORBIDDEN_INITIAL_NAME_TOKENS):
        raise BenchmarkError(f"{field} révèle potentiellement une information protégée.")
    return value


def _validate_sha256(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise BenchmarkError(f"{field} doit être une empreinte SHA-256 hexadécimale.")
    return value


def _iter_regular_files(root: Path) -> list[Path]:
    if not root.is_dir():
        raise BenchmarkError(f"Dossier requis absent: {root}.")
    files: list[Path] = []
    for current, directories, names in os.walk(root, followlinks=False):
        current_path = Path(current)
        for directory in list(directories):
            child = current_path / directory
            if child.is_symlink():
                raise BenchmarkIntegrityError(f"Lien symbolique interdit: {child}.")
        for name in names:
            child = current_path / name
            if child.is_symlink() or not child.is_file():
                raise BenchmarkIntegrityError(f"Entrée non régulière interdite: {child}.")
            files.append(child)
    return sorted(files, key=lambda item: item.relative_to(root).as_posix())


def file_manifest(root: str | Path) -> list[dict[str, Any]]:
    base = Path(root)
    return [
        {
            "path": path.relative_to(base).as_posix(),
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in _iter_regular_files(base)
    ]


def tree_commitment(root: str | Path) -> str:
    """Engagement déterministe d'un arbre; à calculer hors session participant pour la vérité."""

    return sha256_bytes(_canonical_json(file_manifest(root)))


def _forbidden_name(path: Path) -> str | None:
    normalized = path.as_posix().casefold()
    for token in FORBIDDEN_INITIAL_NAME_TOKENS:
        if token in normalized:
            return token
    return None


def _copy_authorized_tree(source: Path, target: Path, *, reject_protected_names: bool) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for source_file in _iter_regular_files(source):
        relative = source_file.relative_to(source)
        if reject_protected_names:
            token = _forbidden_name(relative)
            if token is not None:
                raise BenchmarkIntegrityError(
                    f"Nom interdit dans le pack participant ({token}): {relative}."
                )
        destination = _assert_within(target / relative, target, label="Copie autorisée")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_file, destination)
        os.chmod(destination, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        records.append({
            "path": relative.as_posix(),
            "size": destination.stat().st_size,
            "sha256": sha256_file(destination),
        })
    if not records:
        raise BenchmarkError("initial_client_pack doit contenir au moins un fichier.")
    return records


def _git(repository: Path, *arguments: str, binary: bool = False) -> str | bytes:
    command = ["git", "-C", str(repository), *arguments]
    completed = subprocess.run(command, check=False, capture_output=True)
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise BenchmarkError(f"Commande Git échouée ({' '.join(arguments)}): {message}")
    if binary:
        return completed.stdout
    return completed.stdout.decode("utf-8").strip()


def resolve_git_commit(repository: str | Path, reference: str) -> str:
    result = _git(Path(repository), "rev-parse", "--verify", f"{reference}^{{commit}}")
    assert isinstance(result, str)
    return result


def _engine_files_at_ref(repository: Path, commit: str) -> list[str]:
    result = _git(
        repository,
        "ls-tree",
        "-r",
        "--name-only",
        commit,
        "--",
        *ENGINE_PATHS,
    )
    assert isinstance(result, str)
    paths = [line for line in result.splitlines() if line]
    if not paths or not any(path.startswith("energy_mvp/") for path in paths):
        raise BenchmarkError("La référence Git ne contient pas le moteur Energy Analyzer.")
    return paths


def _copy_engine_snapshot(repository: Path, commit: str, target: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for relative in _engine_files_at_ref(repository, commit):
        blob = _git(repository, "show", f"{commit}:{relative}", binary=True)
        assert isinstance(blob, bytes)
        destination = _assert_within(target / relative, target, label="Snapshot moteur")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(blob)
        os.chmod(destination, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        records.append({
            "path": relative,
            "size": len(blob),
            "sha256": sha256_bytes(blob),
        })
    for directory in sorted(
        (path for path in target.rglob("*") if path.is_dir()),
        key=lambda item: len(item.parts),
        reverse=True,
    ):
        os.chmod(directory, stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
    return records


def _assert_repository_engine_matches(repository: Path, commit: str) -> None:
    paths = _engine_files_at_ref(repository, commit)
    for mode in ("", "--cached"):
        arguments = ["diff", "--quiet"]
        if mode:
            arguments.append(mode)
        arguments.extend([commit, "--", *paths])
        completed = subprocess.run(
            ["git", "-C", str(repository), *arguments], capture_output=True, check=False
        )
        if completed.returncode not in {0, 1}:
            raise BenchmarkError("Impossible de vérifier l'intégrité Git du moteur.")
        if completed.returncode == 1:
            raise BenchmarkIntegrityError(
                "Un run HOLDOUT exige un moteur identique à la référence Git sélectionnée."
            )
    status = _git(
        repository,
        "status",
        "--porcelain",
        "--untracked-files=all",
        "--",
        *ENGINE_PATHS,
    )
    assert isinstance(status, str)
    if status:
        raise BenchmarkIntegrityError(
            "Un run HOLDOUT interdit tout fichier moteur modifié, indexé ou non suivi."
        )


def validate_case_manifest(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise BenchmarkError("Version de schéma de cas inconnue.")
    _validate_opaque_identifier(payload.get("case_id"), field="case_id")
    if payload.get("stage") not in STAGES:
        raise BenchmarkError("Stage de cas inconnu.")
    if payload.get("track") not in TRACKS:
        raise BenchmarkError("Track de connaissance inconnu.")
    if payload.get("difficulty") not in DIFFICULTIES:
        raise BenchmarkError("Difficulté de cas inconnue.")
    if payload.get("truth_level") not in TRUTH_LEVELS:
        raise BenchmarkError("Niveau de vérité inconnu.")
    if not isinstance(payload.get("sector"), str) or not payload["sector"].strip():
        raise BenchmarkError("Le secteur du cas est requis.")
    if not isinstance(payload.get("case_revision"), int) or payload["case_revision"] < 1:
        raise BenchmarkError("case_revision doit être un entier positif.")
    for field in ("initial_pack_commitment_sha256", "oracle_commitment_sha256", "ground_truth_commitment_sha256"):
        _validate_sha256(payload.get(field), field=field)
    max_cycles = payload.get("max_question_cycles", 3)
    if not isinstance(max_cycles, int) or not 1 <= max_cycles <= 10:
        raise BenchmarkError("max_question_cycles doit être compris entre 1 et 10.")
    penalty = payload.get("efficiency_penalty_after_requests", 5)
    if not isinstance(penalty, int) or penalty < 1:
        raise BenchmarkError("efficiency_penalty_after_requests doit être positif.")
    references = payload.get("allowed_references")
    if not isinstance(references, list) or any(not isinstance(item, str) for item in references):
        raise BenchmarkError("allowed_references doit être une liste de chaînes.")


def _validate_oracle(payload: dict[str, Any], *, case_id: str) -> None:
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("case_id") != case_id:
        raise BenchmarkError("Oracle incompatible avec le cas.")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise BenchmarkError("L'oracle doit contenir une liste entries.")
    identifiers: set[str] = set()
    for entry in entries:
        identifier = _validate_opaque_identifier(entry.get("oracle_id"), field="oracle_id")
        if identifier in identifiers:
            raise BenchmarkError("oracle_id dupliqué.")
        identifiers.add(identifier)
        concepts = entry.get("accepted_concepts")
        terms = entry.get("question_terms")
        if not isinstance(concepts, list) or not concepts or any(not isinstance(x, str) or not x.strip() for x in concepts):
            raise BenchmarkError(f"{identifier}: accepted_concepts invalide.")
        if not isinstance(terms, list) or not terms or any(not isinstance(x, str) or not x.strip() for x in terms):
            raise BenchmarkError(f"{identifier}: question_terms invalide.")
        minimum = entry.get("minimum_term_matches", 1)
        if not isinstance(minimum, int) or not 1 <= minimum <= len(terms):
            raise BenchmarkError(f"{identifier}: minimum_term_matches invalide.")
        if entry.get("availability") not in ORACLE_AVAILABILITY:
            raise BenchmarkError(f"{identifier}: disponibilité invalide.")
        if not isinstance(entry.get("cost"), int) or entry["cost"] not in {0, 1, 2, 3, 5}:
            raise BenchmarkError(f"{identifier}: coût oracle invalide.")
        for field in ("response", "responder_role"):
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                raise BenchmarkError(f"{identifier}: {field} est requis.")
        payloads = entry.get("payload_files", [])
        if not isinstance(payloads, list) or any(
            not isinstance(item, str) or not re.fullmatch(r"payloads/payload_[0-9]{3}(?:\.[A-Za-z0-9]{1,10})?", item)
            for item in payloads
        ):
            raise BenchmarkError(f"{identifier}: noms de payload non neutres ou invalides.")


def validate_case_directory(case_directory: str | Path) -> dict[str, Any]:
    root = Path(case_directory).resolve()
    manifest = _read_json(root / "case_manifest.json")
    validate_case_manifest(manifest)
    if root.name != manifest["case_id"]:
        raise BenchmarkError("Le nom du dossier doit être identique à case_id.")
    initial = root / "initial_client_pack"
    oracle_root = root / "followup_oracle"
    truth = root / "ground_truth"
    if not initial.is_dir() or not oracle_root.is_dir() or not truth.is_dir():
        raise BenchmarkError(
            "Le cas doit séparer initial_client_pack, followup_oracle et ground_truth."
        )
    initial_manifest = file_manifest(initial)
    for record in initial_manifest:
        token = _forbidden_name(Path(record["path"]))
        if token is not None:
            raise BenchmarkIntegrityError(
                f"Le pack initial contient un nom protégé ({token})."
            )
    if sha256_bytes(_canonical_json(initial_manifest)) != manifest["initial_pack_commitment_sha256"]:
        raise BenchmarkIntegrityError("Le pack initial ne correspond pas à son engagement.")
    oracle_manifest = file_manifest(oracle_root)
    if sha256_bytes(_canonical_json(oracle_manifest)) != manifest["oracle_commitment_sha256"]:
        raise BenchmarkIntegrityError("L'oracle ne correspond pas à son engagement.")
    oracle = _read_json(oracle_root / "oracle.json")
    _validate_oracle(oracle, case_id=manifest["case_id"])
    # La ground truth n'est ni listée, ni ouverte, ni hachée pendant la phase participant.
    return {"manifest": manifest, "oracle": oracle, "initial_manifest": initial_manifest}


def _normalise_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    plain = "".join(character for character in decomposed if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", " ", plain).strip()


def _validate_information_request(payload: dict[str, Any]) -> None:
    _require_exact_keys(
        payload,
        {
            "request_id", "question", "requested_concepts", "best_responder",
            "why", "hypotheses_distinguished", "expected_effort",
        },
        label="Demande d'information",
    )
    _validate_opaque_identifier(payload.get("request_id"), field="request_id")
    for field in ("question", "best_responder", "why", "expected_effort"):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            raise BenchmarkError(f"Demande: {field} est requis.")
    concepts = payload.get("requested_concepts")
    alternatives = payload.get("hypotheses_distinguished")
    if not isinstance(concepts, list) or not concepts or any(not isinstance(x, str) or not x.strip() for x in concepts):
        raise BenchmarkError("requested_concepts doit être une liste non vide.")
    if not isinstance(alternatives, list) or len(alternatives) < 2 or any(
        not isinstance(item, str) or not item.strip() for item in alternatives
    ):
        raise BenchmarkError("Une demande doit départager au moins deux hypothèses.")


def validate_request_batch(payload: dict[str, Any]) -> None:
    _require_exact_keys(
        payload, {"schema_version", "requests"}, label="Cycle de demandes"
    )
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise BenchmarkError("Version de demandes inconnue.")
    requests = payload.get("requests")
    if not isinstance(requests, list) or not requests:
        raise BenchmarkError("Le cycle doit contenir une liste requests non vide.")
    identifiers: set[str] = set()
    for request in requests:
        if not isinstance(request, dict):
            raise BenchmarkError("Chaque demande doit être un objet.")
        _validate_information_request(request)
        if request["request_id"] in identifiers:
            raise BenchmarkError("request_id dupliqué dans le cycle.")
        identifiers.add(request["request_id"])


def _stem_unmapped_token(token: str) -> str:
    if len(token) > 5 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 4 and token.endswith("ed"):
        return token[:-2]
    if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _semantic_tokens(value: str) -> frozenset[str]:
    tokens: set[str] = set()
    for raw in _normalise_text(value).split():
        if raw in _MATCH_STOPWORDS:
            continue
        expanded = _TOKEN_EXPANSIONS.get(raw, (raw,))
        for item in expanded:
            if item in _MATCH_STOPWORDS:
                continue
            stemmed = _stem_unmapped_token(item)
            canonical = _SEMANTIC_CANONICAL.get(item) or _SEMANTIC_CANONICAL.get(stemmed)
            tokens.add(canonical or stemmed)
    return frozenset(tokens)


def _token_coverage(required: frozenset[str], evidence: frozenset[str]) -> float:
    if not required:
        return 0.0
    return len(required & evidence) / len(required)


def _request_is_vague(request: dict[str, Any]) -> bool:
    normalized = _normalise_text(request["question"])
    vague = {
        "plus de donnees",
        "envoyez plus de donnees",
        "envoyez plus de donnees maintenant",
        "davantage de donnees",
        "des donnees complementaires",
        "plus d informations",
        "more data",
        "send more data",
        "send more data now",
        "please send more data",
        "please send more data now",
        "additional data",
        "additional information",
    }
    if normalized in vague:
        return True
    question_tokens = _semantic_tokens(request["question"])
    declared_tokens = frozenset().union(
        *(_semantic_tokens(item) for item in request["requested_concepts"])
    )
    return len(question_tokens) <= 1 and len(declared_tokens) <= 1


_PHYSICAL_REQUEST_TOKENS = frozenset({
    "measurement", "check", "test", "meter",
    "temperature", "weather", "setpoint", "runtime", "status",
    "command", "pressure", "flow", "power", "energy", "current",
    "speed", "alarm", "humidity", "valve", "heating", "cooling",
    "ventilation", "maintenance", "equipment", "schedule", "sanitation",
    "production", "process", "vibration", "torque", "recipe",
    "occupancy", "feedback", "position", "cycle", "duration",
})


def _request_is_structured_physical_discriminator(request: Mapping[str, Any]) -> bool:
    question = request.get("question")
    why = request.get("why")
    concepts = request.get("requested_concepts")
    hypotheses = request.get("hypotheses_distinguished")
    effort = request.get("expected_effort")
    if (
        not isinstance(question, str)
        or not isinstance(why, str)
        or not isinstance(effort, str)
        or not isinstance(concepts, list)
        or not concepts
        or not isinstance(hypotheses, list)
        or len(hypotheses) < 2
    ):
        return False
    question_tokens = _semantic_tokens(question)
    why_tokens = _semantic_tokens(why)
    concept_tokens = frozenset().union(
        *(_semantic_tokens(str(item)) for item in concepts)
    )
    hypothesis_tokens = [_semantic_tokens(str(item)) for item in hypotheses]
    distinct_hypotheses = len({tuple(sorted(tokens)) for tokens in hypothesis_tokens}) >= 2
    evidence = question_tokens | why_tokens | concept_tokens
    physically_relevant = bool(evidence & _PHYSICAL_REQUEST_TOKENS)
    return (
        len(question_tokens) >= 3
        and len(why_tokens) >= 3
        and len(concept_tokens) >= 1
        and bool(effort.strip())
        and distinct_hypotheses
        and physically_relevant
    )


def _safe_oracle_descriptor(entry: Mapping[str, Any]) -> dict[str, Any]:
    """Projection autorisée pour le matching; exclut réponse, disponibilité et payloads."""

    return {
        "oracle_id": entry["oracle_id"],
        "accepted_concepts": list(entry["accepted_concepts"]),
        "question_terms": list(entry["question_terms"]),
        "minimum_term_matches": int(entry.get("minimum_term_matches", 1)),
    }


def _oracle_candidate_score(
    request: Mapping[str, Any], descriptor: Mapping[str, Any]
) -> dict[str, Any]:
    question_tokens = _semantic_tokens(str(request["question"]))
    declared_tokens = frozenset().union(
        *(_semantic_tokens(str(item)) for item in request["requested_concepts"])
    )
    request_evidence = question_tokens | declared_tokens
    accepted_token_sets = [
        _semantic_tokens(str(item)) for item in descriptor["accepted_concepts"]
    ]
    concept_coverage = max(
        (_token_coverage(tokens, request_evidence) for tokens in accepted_token_sets),
        default=0.0,
    )

    term_coverages = [
        _token_coverage(_semantic_tokens(str(term)), question_tokens)
        for term in descriptor["question_terms"]
    ]
    term_matches = sum(coverage >= 0.75 for coverage in term_coverages)
    minimum = int(descriptor["minimum_term_matches"])
    minimum_ratio = min(1.0, term_matches / minimum)
    term_ratio = term_matches / len(term_coverages) if term_coverages else 0.0
    specificity = min(1.0, len(question_tokens) / 4.0)
    score = (
        0.55 * concept_coverage
        + 0.30 * minimum_ratio
        + 0.10 * term_ratio
        + 0.05 * specificity
    )
    auto_eligible = concept_coverage >= 0.75 and term_matches >= minimum
    review_eligible = (
        concept_coverage >= 0.50
        and term_matches >= max(1, minimum - 1)
        and score >= ORACLE_BLIND_REVIEW_THRESHOLD
    )
    # A primary discriminating intent may remain clear despite related details.
    # This is review-only: automatic disclosure thresholds stay unchanged.
    primary_intent_review_eligible = concept_coverage >= 0.75 and term_matches >= 1
    return {
        "oracle_id": descriptor["oracle_id"],
        "score": round(score, 6),
        "concept_coverage": round(concept_coverage, 6),
        "term_matches": term_matches,
        "required_term_matches": minimum,
        "term_ratio": round(term_ratio, 6),
        "auto_eligible": auto_eligible,
        "review_eligible": review_eligible,
        "primary_intent_review_eligible": primary_intent_review_eligible,
    }


def oracle_match_decision(
    request: dict[str, Any],
    entries: Sequence[Mapping[str, Any]],
    *,
    answered_entries: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Decide without answer payloads; structured physical misses require blind review."""

    if _request_is_vague(request):
        return {
            "matcher_version": ORACLE_MATCHER_VERSION,
            "status": "NO_MATCH",
            "reason": "generic_or_underspecified_request",
            "selected_oracle_id": None,
            "candidates": [],
        }

    answered_candidates = [
        _oracle_candidate_score(request, _safe_oracle_descriptor(entry))
        for entry in answered_entries
    ]
    answered_candidates.sort(key=lambda item: (-float(item["score"]), str(item["oracle_id"])))
    if answered_candidates:
        answered_best = answered_candidates[0]
        if (
            answered_best["auto_eligible"]
            and float(answered_best["score"]) >= ORACLE_AUTO_MATCH_THRESHOLD
        ):
            return {
                "matcher_version": ORACLE_MATCHER_VERSION,
                "status": "NO_MATCH",
                "reason": "already_answered",
                "selected_oracle_id": None,
                "candidates": [],
            }

    descriptors = [_safe_oracle_descriptor(entry) for entry in entries]
    all_candidates = [
        _oracle_candidate_score(request, descriptor) for descriptor in descriptors
    ]
    eligible = [item for item in all_candidates if item["review_eligible"] or item["primary_intent_review_eligible"]]
    eligible.sort(key=lambda item: (-float(item["score"]), str(item["oracle_id"])))

    if eligible:
        best = eligible[0]
        runner_up_score = float(eligible[1]["score"]) if len(eligible) > 1 else 0.0
        margin = float(best["score"]) - runner_up_score
        if (
            best["auto_eligible"]
            and float(best["score"]) >= ORACLE_AUTO_MATCH_THRESHOLD
            and (len(eligible) == 1 or margin >= ORACLE_AUTO_MATCH_MIN_MARGIN)
        ):
            return {
                "matcher_version": ORACLE_MATCHER_VERSION,
                "status": "MATCHED",
                "reason": "semantic_concept_and_terms_sufficient",
                "selected_oracle_id": best["oracle_id"],
                "candidates": [best],
                "margin": round(margin, 6),
            }
        review_candidates = [
            item for item in eligible
            if float(item["score"]) >= max(
                ORACLE_BLIND_REVIEW_THRESHOLD, float(best["score"]) - 0.15
            )
        ][:ORACLE_MAX_REVIEW_CANDIDATES]
        return {
            "matcher_version": ORACLE_MATCHER_VERSION,
            "status": "PENDING_BLIND_ORACLE_REVIEW",
            "reason": "borderline_competing_or_primary_discriminating_intent",
            "selected_oracle_id": None,
            "candidates": review_candidates,
            "margin": round(margin, 6),
        }

    if _request_is_structured_physical_discriminator(request) and all_candidates:
        fallback_candidates = sorted(
            all_candidates,
            key=lambda item: (-float(item["score"]), str(item["oracle_id"])),
        )[:ORACLE_MAX_FALLBACK_REVIEW_CANDIDATES]
        fallback_candidates = [
            {**item, "fallback_blind_review": True}
            for item in fallback_candidates
        ]
        return {
            "matcher_version": ORACLE_MATCHER_VERSION,
            "status": "PENDING_BLIND_ORACLE_REVIEW",
            "reason": "structured_physical_request_needs_blind_review",
            "selected_oracle_id": None,
            "candidates": fallback_candidates,
            "margin": None,
        }

    return {
        "matcher_version": ORACLE_MATCHER_VERSION,
        "status": "NO_MATCH",
        "reason": "clearly_off_topic_or_non_discriminating",
        "selected_oracle_id": None,
        "candidates": [],
    }


def evaluate_oracle_matcher_fixture(payload: Mapping[str, Any]) -> dict[str, Any]:
    cases = payload.get("cases")
    catalog = payload.get("entries", [])
    if not isinstance(catalog, list):
        raise BenchmarkError("Le catalogue matcher doit être une liste.")
    catalog_by_id = {
        str(entry["oracle_id"]): entry
        for entry in catalog
        if isinstance(entry, dict) and isinstance(entry.get("oracle_id"), str)
    }
    if not isinstance(cases, list) or not cases:
        raise BenchmarkError("Le corpus matcher doit contenir une liste cases non vide.")
    true_positives = false_positives = true_negatives = false_negatives = 0
    pending = 0
    outcomes: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, dict):
            raise BenchmarkError("Chaque fixture matcher doit être un objet.")
        request = case.get("request")
        entries = case.get("entries")
        if entries is None:
            entry_ids = case.get("entry_ids")
            if not isinstance(entry_ids, list) or any(
                not isinstance(item, str) or item not in catalog_by_id for item in entry_ids
            ):
                raise BenchmarkError("Fixture matcher: entry_ids invalides.")
            entries = [catalog_by_id[item] for item in entry_ids]
        expected = case.get("expected_oracle_id")
        if not isinstance(request, dict) or not isinstance(entries, list):
            raise BenchmarkError("Fixture matcher incomplète.")
        if expected is not None and not isinstance(expected, str):
            raise BenchmarkError("expected_oracle_id doit être une chaîne ou null.")
        decision = oracle_match_decision(request, entries)
        predicted = decision["selected_oracle_id"] if decision["status"] == "MATCHED" else None
        if decision["status"] == "PENDING_BLIND_ORACLE_REVIEW":
            pending += 1
        if expected is None:
            if predicted is None:
                true_negatives += 1
            else:
                false_positives += 1
        elif predicted == expected:
            true_positives += 1
        else:
            false_negatives += 1
            if predicted is not None:
                false_positives += 1
        outcomes.append({
            "fixture_id": case.get("fixture_id"),
            "expected_oracle_id": expected,
            "status": decision["status"],
            "selected_oracle_id": predicted,
        })
    precision_denominator = true_positives + false_positives
    recall_denominator = true_positives + false_negatives
    precision = true_positives / precision_denominator if precision_denominator else 1.0
    recall = true_positives / recall_denominator if recall_denominator else 1.0
    return {
        "matcher_version": ORACLE_MATCHER_VERSION,
        "fixtures": len(cases),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "true_negatives": true_negatives,
        "false_negatives": false_negatives,
        "pending_blind_review": pending,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "outcomes": outcomes,
    }


def _event_hash(event: dict[str, Any]) -> str:
    return sha256_bytes(_canonical_json({key: value for key, value in event.items() if key != "event_sha256"}))


def _append_event(private_root: Path, action: str, details: dict[str, Any]) -> dict[str, Any]:
    path = private_root / "events.jsonl"
    previous = None
    sequence = 1
    if path.exists():
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
        if lines:
            last = json.loads(lines[-1])
            previous = last["event_sha256"]
            sequence = last["sequence"] + 1
    event = {
        "sequence": sequence,
        "at_utc": _utc_now(),
        "action": action,
        "details": details,
        "previous_event_sha256": previous,
    }
    event["event_sha256"] = _event_hash(event)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return event


def verify_event_log(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    previous = None
    count = 0
    for count, line in enumerate(target.read_text(encoding="utf-8").splitlines(), start=1):
        event = json.loads(line)
        if event.get("sequence") != count:
            raise BenchmarkIntegrityError("Séquence du journal invalide.")
        if event.get("previous_event_sha256") != previous:
            raise BenchmarkIntegrityError("Chaîne du journal rompue.")
        if event.get("event_sha256") != _event_hash(event):
            raise BenchmarkIntegrityError("Empreinte d'événement invalide.")
        previous = event["event_sha256"]
    if count == 0:
        raise BenchmarkIntegrityError("Journal de run vide.")
    return {"events": count, "last_event_sha256": previous}


def _run_roots(run_directory: str | Path) -> tuple[Path, Path, Path]:
    root = Path(run_directory).resolve()
    participant = root / "participant_workspace"
    private = root / "private_run"
    if not participant.is_dir() or not private.is_dir():
        raise BenchmarkError("Dossier de run incomplet.")
    return root, participant, private


def _write_participant_context(participant: Path, manifest: dict[str, Any]) -> None:
    accessible = [
        record["participant_path"] for record in manifest["accessible_files"]
    ]
    context = {
        "schema_version": SCHEMA_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "run_id": manifest["run_id"],
        "case_id": manifest["case_id"],
        "stage": manifest["stage"],
        "track": manifest["track"],
        "cycle": len(manifest["question_cycles"]),
        "model": manifest["model"],
        "reasoning_effort": manifest["reasoning_effort"],
        "internet_allowed": manifest["internet_allowed"],
        "allowed_references": manifest["allowed_references"],
        "accessible_files": accessible,
        "distinct_requests_so_far": len(manifest["distinct_request_ids"]),
        "oracle_cost_so_far": manifest["oracle_cost_total"],
        "oracle_matcher_version": manifest.get("oracle_matcher_version", "exact-v1"),
        "pending_blind_oracle_reviews": len(
            manifest.get("pending_blind_oracle_reviews", [])
        ),
        "blind_oracle_reviews_completed": len(manifest.get("blind_oracle_review_history", [])),
        "previous_run_outputs_available": False,
        "ground_truth_available": False,
        "scoring_available": False,
    }
    _write_json(participant / "run_context.json", context)


def _participant_record(path: Path, participant: Path) -> dict[str, Any]:
    return {
        "participant_path": path.relative_to(participant).as_posix(),
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def prepare_run(
    case_directory: str | Path,
    runs_directory: str | Path,
    *,
    run_id: str | None,
    repository: str | Path,
    system_ref: str,
    model: str,
    reasoning_effort: str,
    run_index: int = 1,
) -> Path:
    case_root = Path(case_directory).resolve()
    runs_root = Path(runs_directory).resolve()
    repository_root = Path(repository).resolve()
    if case_root == runs_root or case_root in runs_root.parents or runs_root in case_root.parents:
        raise BenchmarkIntegrityError("Le stockage des runs doit être séparé du cas privé.")
    validated = validate_case_directory(case_root)
    case = validated["manifest"]
    resolved_run_id = run_id or f"{case['case_id']}_run_{uuid.uuid4().hex[:12]}"
    _validate_opaque_identifier(resolved_run_id, field="run_id")
    if not isinstance(model, str) or not model.strip() or not isinstance(reasoning_effort, str) or not reasoning_effort.strip():
        raise BenchmarkError("Le modèle exact et le niveau de raisonnement sont obligatoires.")
    if not isinstance(run_index, int) or run_index < 1:
        raise BenchmarkError("run_index doit être positif.")
    commit = resolve_git_commit(repository_root, system_ref)
    if case["stage"] == "HOLDOUT":
        _assert_repository_engine_matches(repository_root, commit)
    run_root = runs_root / resolved_run_id
    _assert_within(run_root, runs_root, label="Run")
    if run_root.exists():
        raise FileExistsError(f"Le run existe déjà et ne sera pas réutilisé: {run_root}.")
    participant = run_root / "participant_workspace"
    private = run_root / "private_run"
    for path in (
        participant / "initial_client_pack",
        participant / "revealed",
        participant / "scratch",
        participant / "protocol",
        participant / "output",
        participant / "engine",
        private,
    ):
        path.mkdir(parents=True, exist_ok=False)

    initial_records = _copy_authorized_tree(
        case_root / "initial_client_pack",
        participant / "initial_client_pack",
        reject_protected_names=True,
    )
    engine_records = _copy_engine_snapshot(repository_root, commit, participant / "engine")
    accessible_files = []
    for record in initial_records:
        path = participant / "initial_client_pack" / record["path"]
        accessible_files.append(_participant_record(path, participant))
    protocol_root = Path(__file__).resolve().parents[1] / "benchmarks" / "physical_expertise"
    protocol_sources = {
        "requests.schema.json": protocol_root / "schemas" / "requests.schema.json",
        "response.schema.json": protocol_root / "schemas" / "response.schema.json",
        "requests.template.json": protocol_root / "templates" / "requests.template.json",
        "response.template.json": protocol_root / "templates" / "response.template.json",
    }
    for destination_name, source in protocol_sources.items():
        if source.is_symlink() or not source.is_file():
            raise BenchmarkIntegrityError(f"Ressource de protocole absente ou invalide: {source}.")
        destination = participant / "protocol" / destination_name
        shutil.copyfile(source, destination)
        os.chmod(destination, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        accessible_files.append(_participant_record(destination, participant))


    instructions = """# Physical Expertise Benchmark — participant workspace

Use only this directory and only the evidence currently authorized in
`initial_client_pack/` and `revealed/`. The committed engine snapshot is in `engine/`.
Write experiments only in `scratch/` and the structured answer in `output/response.json`.

Absolute rules:
- never search for ground truth, scoring, oracle files, expert answers or previous runs;
- do not assume that an anomaly or a recoverable saving exists;
- produce the strongest conclusion justified by evidence, neither stronger nor weaker; data volume alone is not evidence strength;
- a legitimate operation that explains the event is NORMAL_OPERATION, not CAUSE_PROBABLE; cause classes require an abnormal phenomenon;
- ANOMALY_CONFIRMED_CAUSE_UNCERTAIN is valid when abnormality is established but causes remain unresolved; use INSUFFICIENT_INFORMATION only when missing evidence blocks the decision required;
- NORMAL_OPERATION, INSUFFICIENT_INFORMATION and DATA_QUALITY_BLOCKER are valid conclusions;
- ask only for the minimal information that most reduces uncertainty;
- a temporal correlation does not prove a physical cause;
- every intervention must state preconditions, risks, competent person, stop conditions
  and before/after validation;
- never invent a measurement, client document, test result or unknown value;
- do not modify the system or toolbox during a HOLDOUT run;
- do not self-assess expertise and do not attempt to anticipate the score;
- for CONTROLLED_OPEN_BOOK, use no internet or references outside `allowed_references`.

The exact request and response contracts are available in `protocol/`; use their templates
as the starting point and do not add fields that are absent from the schemas.


If engine/docs/PHYSICAL_DIAGNOSTICS.md is present, use it as an open, non-exhaustive
reasoning reference. The knowledge files do not choose causes. For each important open
investigation, keep an internal physical differential in scratch/physical_differential.json
covering the energy chain, service demand, command versus actual feedback, competing
mechanisms, predictions and discriminating measurements. This is a review contract, not
a fixed sequence: you may use an unlisted cause, tool, variable or investigation protocol.

The engine snapshot and authorized evidence are sealed and will be verified at finalization.
"""
    (participant / "RUN_INSTRUCTIONS.md").write_text(instructions, encoding="utf-8")
    accessible_files.append(_participant_record(participant / "RUN_INSTRUCTIONS.md", participant))

    runner_path = Path(__file__)
    created_at = _utc_now()
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "baseline_label": system_ref,
        "run_id": resolved_run_id,
        "run_index": run_index,
        "case_id": case["case_id"],
        "case_revision": case["case_revision"],
        "stage": case["stage"],
        "track": case["track"],
        "status": "prepared",
        "created_at_utc": created_at,
        "completed_at_utc": None,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "system_git_commit": commit,
        "repository_path_at_prepare": str(repository_root),
        "runner_sha256": sha256_file(runner_path),
        "python_version": sys.version,
        "platform": platform.platform(),
        "internet_allowed": case["track"] == "REAL_WORLD_OPEN_BOOK",
        "allowed_references": list(case["allowed_references"]),
        "max_question_cycles": case.get("max_question_cycles", 3),
        "efficiency_penalty_after_requests": case.get("efficiency_penalty_after_requests", 5),
        "initial_pack_commitment_sha256": case["initial_pack_commitment_sha256"],
        "oracle_commitment_sha256": case["oracle_commitment_sha256"],
        "ground_truth_commitment_sha256": case["ground_truth_commitment_sha256"],
        "engine_files": engine_records,
        "engine_commitment_sha256": sha256_bytes(_canonical_json(engine_records)),
        "accessible_files": accessible_files,
        "question_cycles": [],
        "distinct_request_ids": [],
        "revealed_oracle_ids": [],
        "oracle_cost_total": 0,
        "oracle_matcher_version": ORACLE_MATCHER_VERSION,
        "oracle_matcher_config": {
            "auto_match_threshold": ORACLE_AUTO_MATCH_THRESHOLD,
            "blind_review_threshold": ORACLE_BLIND_REVIEW_THRESHOLD,
            "auto_match_min_margin": ORACLE_AUTO_MATCH_MIN_MARGIN,
            "max_review_candidates": ORACLE_MAX_REVIEW_CANDIDATES,
            "max_fallback_review_candidates": ORACLE_MAX_FALLBACK_REVIEW_CANDIDATES,
        },
        "pending_blind_oracle_reviews": [],
        "blind_oracle_review_history": [],
        "automatic_match_count": 0,
        "automatic_no_match_count": 0,
        "response": None,
        "previous_run_outputs_copied": False,
        "ground_truth_read_by_runner": False,
    }
    _write_json(private / "run_manifest.json", manifest)
    reproduction = {
        key: manifest[key]
        for key in (
            "protocol_version", "baseline_label", "case_id", "case_revision", "stage",
            "track", "model", "reasoning_effort", "system_git_commit", "runner_sha256",
            "internet_allowed", "allowed_references", "initial_pack_commitment_sha256",
            "oracle_commitment_sha256", "ground_truth_commitment_sha256",
            "engine_commitment_sha256",
            "oracle_matcher_version",
            "oracle_matcher_config",
        )
    }
    reproduction["initial_accessible_files"] = list(accessible_files)
    _write_json(private / "reproduction.json", reproduction)
    _append_event(private, "prepare_run", {
        "run_id": resolved_run_id,
        "case_id": case["case_id"],
        "system_git_commit": commit,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "initial_accessible_files": accessible_files,
        "ground_truth_read": False,
    })
    _write_participant_context(participant, manifest)
    return run_root


def _upsert_accessible_record(
    manifest: dict[str, Any], path: Path, participant: Path
) -> None:
    record = _participant_record(path, participant)
    for index, existing in enumerate(manifest["accessible_files"]):
        if existing["participant_path"] == record["participant_path"]:
            manifest["accessible_files"][index] = record
            return
    manifest["accessible_files"].append(record)


def _reveal_selected_entry(
    *,
    participant: Path,
    manifest: dict[str, Any],
    case_root: Path,
    cycle_directory: Path,
    request_id: str,
    selected: Mapping[str, Any],
    match_source: str,
) -> dict[str, Any]:
    oracle_id = str(selected["oracle_id"])
    destination = cycle_directory / oracle_id
    destination.mkdir(parents=True, exist_ok=False)
    payload_destinations: list[str] = []
    if selected["availability"] == "available":
        for index, relative in enumerate(selected.get("payload_files", []), start=1):
            source = case_root / "followup_oracle" / str(relative)
            _assert_within(source, case_root / "followup_oracle", label="Payload oracle")
            if source.is_symlink() or not source.is_file():
                raise BenchmarkIntegrityError(f"Payload oracle invalide: {relative}.")
            suffix = source.suffix if re.fullmatch(r"\.[A-Za-z0-9]{1,10}", source.suffix) else ""
            target = destination / f"payload_{index:03d}{suffix}"
            shutil.copyfile(source, target)
            os.chmod(target, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            payload_destinations.append(target.relative_to(participant).as_posix())
            _upsert_accessible_record(manifest, target, participant)
    response = {
        "schema_version": SCHEMA_VERSION,
        "request_id": request_id,
        "availability": selected["availability"],
        "response": selected["response"],
        "responder_role": selected["responder_role"],
        "oracle_cost": selected["cost"],
        "payload_files": payload_destinations,
    }
    response_path = destination / "response.json"
    _write_json(response_path, response)
    os.chmod(response_path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    _upsert_accessible_record(manifest, response_path, participant)
    return {
        "request_id": request_id,
        "status": "MATCHED",
        "matched": True,
        "match_source": match_source,
        "availability": selected["availability"],
        "oracle_cost": selected["cost"],
        "revealed_response": response_path.relative_to(participant).as_posix(),
        "payload_files": payload_destinations,
    }


def _create_blind_review_packet(
    *,
    private: Path,
    manifest: dict[str, Any],
    cycle: int,
    request: Mapping[str, Any],
    decision: Mapping[str, Any],
    entries: Sequence[Mapping[str, Any]],
) -> str:
    review_id = f"review_{uuid.uuid4().hex[:16]}"
    entry_by_id = {str(entry["oracle_id"]): entry for entry in entries}
    candidate_ids = [str(item["oracle_id"]) for item in decision["candidates"]]
    packet = {
        "schema_version": SCHEMA_VERSION,
        "review_id": review_id,
        "run_id": manifest["run_id"],
        "cycle": cycle,
        "request_id": request["request_id"],
        "participant_request": {
            "question": request["question"],
            "requested_concepts": list(request["requested_concepts"]),
            "why": request["why"],
            "hypotheses_distinguished": list(request["hypotheses_distinguished"]),
        },
        "candidates": [
            {
                "oracle_id": oracle_id,
                "abstract_information_types": list(
                    entry_by_id[oracle_id]["accepted_concepts"]
                ),
            }
            for oracle_id in candidate_ids
        ],
        "review_question": (
            "La demande contient-elle une intention principale matériellement discriminante "
            "qui correspond à une seule catégorie disponible, sans consulter la réponse ou "
            "ses payloads ? Des détails liés ne l'invalident pas. Répondre NO_MATCH si "
            "l'intention est vague, incidente, déjà satisfaite, non discriminante, ou "
            "réellement ambiguë entre plusieurs catégories."
        ),
        "matcher_version": ORACLE_MATCHER_VERSION,
        "created_at_utc": _utc_now(),
    }
    packet_path = private / "blind_reviews" / "pending" / f"{review_id}.json"
    _write_json(packet_path, packet)
    manifest["pending_blind_oracle_reviews"].append({
        "review_id": review_id,
        "cycle": cycle,
        "request_id": request["request_id"],
        "candidate_oracle_ids": candidate_ids,
        "packet_path": packet_path.relative_to(private).as_posix(),
        "packet_sha256": sha256_file(packet_path),
        "created_at_utc": packet["created_at_utc"],
    })
    return review_id


def list_pending_blind_oracle_reviews(
    run_directory: str | Path,
) -> dict[str, Any]:
    """Sortie privée réservée à un opérateur indépendant, jamais au participant."""

    _, _, private = _run_roots(run_directory)
    manifest = _read_json(private / "run_manifest.json")
    reviews = []
    for pending in manifest.get("pending_blind_oracle_reviews", []):
        packet = _read_json(private / pending["packet_path"])
        if sha256_file(private / pending["packet_path"]) != pending["packet_sha256"]:
            raise BenchmarkIntegrityError("Paquet de revue aveugle modifié.")
        reviews.append(packet)
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": manifest["run_id"],
        "pending_reviews": reviews,
        "operator_only": True,
    }


def validate_blind_oracle_review(payload: Mapping[str, Any]) -> None:
    _require_exact_keys(
        payload,
        {
            "schema_version", "review_id", "reviewer_id", "reviewer_independent",
            "decision", "oracle_id", "justification",
        },
        label="Décision de revue aveugle",
    )
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise BenchmarkError("Version de revue aveugle inconnue.")
    _validate_opaque_identifier(payload.get("review_id"), field="review_id")
    _validate_opaque_identifier(payload.get("reviewer_id"), field="reviewer_id")
    if payload.get("reviewer_independent") is not True:
        raise BenchmarkError("La revue doit être effectuée par un opérateur indépendant.")
    if payload.get("decision") not in BLIND_REVIEW_DECISIONS:
        raise BenchmarkError("Décision de revue aveugle inconnue.")
    if not isinstance(payload.get("justification"), str) or not payload["justification"].strip():
        raise BenchmarkError("La justification de revue est obligatoire.")
    oracle_id = payload.get("oracle_id")
    if payload["decision"] == "MATCH":
        _validate_opaque_identifier(oracle_id, field="oracle_id")
    elif oracle_id is not None:
        raise BenchmarkError("oracle_id doit être null pour une décision NO_MATCH.")


def reveal_followups(
    run_directory: str | Path,
    case_directory: str | Path,
    requests_path: str | Path,
) -> dict[str, Any]:
    run_root, participant, private = _run_roots(run_directory)
    case_root = Path(case_directory).resolve()
    if case_root == run_root or case_root in run_root.parents or run_root in case_root.parents:
        raise BenchmarkIntegrityError("Le cas privé et le run doivent rester séparés.")
    validated = validate_case_directory(case_root)
    case = validated["manifest"]
    oracle = validated["oracle"]
    manifest_path = private / "run_manifest.json"
    manifest = _read_json(manifest_path)
    if manifest["case_id"] != case["case_id"]:
        raise BenchmarkIntegrityError("Le run ne correspond pas au cas fourni.")
    if manifest["oracle_commitment_sha256"] != case["oracle_commitment_sha256"]:
        raise BenchmarkIntegrityError("L'oracle a changé depuis la préparation du run.")
    if manifest["status"] not in {"prepared", "questions_revealed"}:
        raise BenchmarkError("Ce run n'accepte plus de cycle de questions.")
    if manifest.get("pending_blind_oracle_reviews"):
        raise BenchmarkError("Une revue aveugle doit être résolue avant un nouveau cycle.")
    cycle = len(manifest["question_cycles"]) + 1
    if cycle > manifest["max_question_cycles"]:
        raise BenchmarkError("Nombre maximal de cycles de questions atteint.")
    requests = _read_json(requests_path)
    validate_request_batch(requests)
    previous_ids = set(manifest["distinct_request_ids"])
    repeated = [item["request_id"] for item in requests["requests"] if item["request_id"] in previous_ids]
    if repeated:
        raise BenchmarkError("request_id déjà utilisé: " + ", ".join(repeated))
    private_request = private / "requests" / f"cycle_{cycle:03d}.json"
    _write_json(private_request, requests)
    requests_sha256 = sha256_file(private_request)
    private_request_relative = private_request.relative_to(private).as_posix()

    revealed_ids = set(manifest["revealed_oracle_ids"])
    cycle_directory = participant / "revealed" / f"cycle_{cycle:03d}"
    cycle_directory.mkdir(parents=True, exist_ok=False)
    results: list[dict[str, Any]] = []
    newly_revealed: list[str] = []
    cycle_cost = 0
    entries = [entry for entry in oracle["entries"] if entry["oracle_id"] not in revealed_ids]
    answered_entries = [
        entry for entry in oracle["entries"] if entry["oracle_id"] in revealed_ids
    ]
    private_match_records: list[dict[str, Any]] = []
    for request in requests["requests"]:
        decision = oracle_match_decision(
            request, entries, answered_entries=answered_entries
        )
        status = decision["status"]
        review_id = None
        if status == "MATCHED":
            oracle_id = str(decision["selected_oracle_id"])
            selected = next(entry for entry in entries if entry["oracle_id"] == oracle_id)
            result = _reveal_selected_entry(
                participant=participant,
                manifest=manifest,
                case_root=case_root,
                cycle_directory=cycle_directory,
                request_id=request["request_id"],
                selected=selected,
                match_source="automatic_semantic_match",
            )
            newly_revealed.append(oracle_id)
            revealed_ids.add(oracle_id)
            entries = [entry for entry in entries if entry["oracle_id"] != oracle_id]
            answered_entries.append(selected)
            cycle_cost += int(selected["cost"])
            manifest["automatic_match_count"] += 1
        elif status == "PENDING_BLIND_ORACLE_REVIEW":
            review_id = _create_blind_review_packet(
                private=private,
                manifest=manifest,
                cycle=cycle,
                request=request,
                decision=decision,
                entries=entries,
            )
            result = {
                "request_id": request["request_id"],
                "status": "PENDING_BLIND_ORACLE_REVIEW",
                "matched": False,
                "reason": "independent_review_required",
            }
        else:
            result = {
                "request_id": request["request_id"],
                "status": "NO_MATCH",
                "matched": False,
                "reason": "no_sufficient_match",
            }
            manifest["automatic_no_match_count"] += 1
        results.append(result)
        private_match_records.append({
            "request_id": request["request_id"],
            "request_sha256": sha256_bytes(_canonical_json(request)),
            "status": status,
            "matched": result["matched"],
            "matcher_reason": decision["reason"],
            "matcher_candidates": decision["candidates"],
            "review_id": review_id,
        })

    public_result = {
        "schema_version": SCHEMA_VERSION,
        "cycle": cycle,
        "matcher_version": ORACLE_MATCHER_VERSION,
        "results": results,
        "cycle_oracle_cost": cycle_cost,
    }
    public_path = cycle_directory / "request_results.json"
    _write_json(public_path, public_result)
    _upsert_accessible_record(manifest, public_path, participant)
    manifest["question_cycles"].append({
        "cycle": cycle,
        "requests_sha256": requests_sha256,
        "private_requests_path": private_request_relative,
        "requests": private_match_records,
        "revealed_oracle_ids": newly_revealed,
        "oracle_cost": cycle_cost,
        "completed_at_utc": _utc_now(),
    })
    manifest["distinct_request_ids"].extend(item["request_id"] for item in requests["requests"])
    manifest["revealed_oracle_ids"].extend(newly_revealed)
    manifest["oracle_cost_total"] += cycle_cost
    manifest["status"] = "questions_revealed"
    _write_json(manifest_path, manifest)
    _append_event(private, "reveal_followups", {
        "cycle": cycle,
        "matcher_version": ORACLE_MATCHER_VERSION,
        "requests_sha256": requests_sha256,
        "private_requests_path": private_request_relative,
        "request_results": private_match_records,
        "revealed_oracle_ids": newly_revealed,
        "oracle_cost": cycle_cost,
        "ground_truth_read": False,
        "oracle_payload_read_for_matching": False,
    })
    _write_participant_context(participant, manifest)
    return public_result


def apply_blind_oracle_review(
    run_directory: str | Path,
    case_directory: str | Path,
    decision_path: str | Path,
) -> dict[str, Any]:
    run_root, participant, private = _run_roots(run_directory)
    decision_target = Path(decision_path).resolve()
    if decision_target == participant or participant in decision_target.parents:
        raise BenchmarkIntegrityError("La décision de revue ne peut pas venir du participant.")
    decision = _read_json(decision_target)
    validate_blind_oracle_review(decision)
    manifest_path = private / "run_manifest.json"
    manifest = _read_json(manifest_path)
    pending = next(
        (
            item for item in manifest.get("pending_blind_oracle_reviews", [])
            if item["review_id"] == decision["review_id"]
        ),
        None,
    )
    if pending is None:
        raise BenchmarkError("Revue aveugle absente ou déjà résolue.")
    packet_path = private / pending["packet_path"]
    if sha256_file(packet_path) != pending["packet_sha256"]:
        raise BenchmarkIntegrityError("Paquet de revue aveugle modifié.")
    case_root = Path(case_directory).resolve()
    if case_root == run_root or case_root in run_root.parents or run_root in case_root.parents:
        raise BenchmarkIntegrityError("Le cas privé et le run doivent rester séparés.")
    validated = validate_case_directory(case_root)
    case = validated["manifest"]
    oracle = validated["oracle"]
    if manifest["case_id"] != case["case_id"]:
        raise BenchmarkIntegrityError("Le run ne correspond pas au cas fourni.")
    if manifest["oracle_commitment_sha256"] != case["oracle_commitment_sha256"]:
        raise BenchmarkIntegrityError("L'oracle a changé depuis la préparation du run.")

    cycle = int(pending["cycle"])
    request_id = str(pending["request_id"])
    public_path = participant / "revealed" / f"cycle_{cycle:03d}" / "request_results.json"
    public_result = _read_json(public_path)
    public_item = next(item for item in public_result["results"] if item["request_id"] == request_id)
    revealed_id = None
    cost = 0
    if decision["decision"] == "MATCH":
        oracle_id = str(decision["oracle_id"])
        if oracle_id not in pending["candidate_oracle_ids"]:
            raise BenchmarkIntegrityError("La revue tente de sélectionner une entrée hors candidats.")
        if oracle_id in manifest["revealed_oracle_ids"]:
            raise BenchmarkError("Cette entrée oracle est déjà révélée.")
        selected = next(
            (entry for entry in oracle["entries"] if entry["oracle_id"] == oracle_id),
            None,
        )
        if selected is None:
            raise BenchmarkIntegrityError("Entrée oracle revue absente.")
        replacement = _reveal_selected_entry(
            participant=participant,
            manifest=manifest,
            case_root=case_root,
            cycle_directory=public_path.parent,
            request_id=request_id,
            selected=selected,
            match_source="independent_blind_review",
        )
        public_item.clear()
        public_item.update(replacement)
        revealed_id = oracle_id
        cost = int(selected["cost"])
        manifest["revealed_oracle_ids"].append(oracle_id)
        manifest["oracle_cost_total"] += cost
    else:
        public_item.clear()
        public_item.update({
            "request_id": request_id,
            "status": "NO_MATCH",
            "matched": False,
            "reason": "independent_blind_review_no_match",
        })
    public_result["cycle_oracle_cost"] = int(public_result["cycle_oracle_cost"]) + cost
    _write_json(public_path, public_result)
    _upsert_accessible_record(manifest, public_path, participant)

    cycle_record = next(item for item in manifest["question_cycles"] if item["cycle"] == cycle)
    request_record = next(item for item in cycle_record["requests"] if item["request_id"] == request_id)
    request_record["status"] = "MATCHED" if revealed_id else "NO_MATCH"
    request_record["matched"] = bool(revealed_id)
    request_record["blind_review_decision"] = decision["decision"]
    request_record["blind_reviewer_id"] = decision["reviewer_id"]
    cycle_record["oracle_cost"] = int(cycle_record["oracle_cost"]) + cost
    if revealed_id:
        cycle_record["revealed_oracle_ids"].append(revealed_id)
    manifest["pending_blind_oracle_reviews"] = [
        item for item in manifest["pending_blind_oracle_reviews"]
        if item["review_id"] != decision["review_id"]
    ]
    decision_copy = private / "blind_reviews" / "decisions" / f"{decision['review_id']}.json"
    decision_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(decision_target, decision_copy)
    os.chmod(decision_copy, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    decision_hash = sha256_file(decision_copy)
    resolved_at = _utc_now()
    base_history = {
        "review_id": decision["review_id"],
        "request_id": request_id,
        "cycle": cycle,
        "reviewer_id": decision["reviewer_id"],
        "decision": decision["decision"],
        "selected_oracle_id": revealed_id,
        "decision_sha256": decision_hash,
        "decision_path": decision_copy.relative_to(private).as_posix(),
        "packet_sha256": pending["packet_sha256"],
        "packet_path": pending["packet_path"],
        "resolved_at_utc": resolved_at,
    }
    resolved_path = private / "blind_reviews" / "resolved" / f"{decision['review_id']}.json"
    _write_json(resolved_path, {**base_history, "justification": decision["justification"]})
    history = {
        **base_history,
        "resolved_record_path": resolved_path.relative_to(private).as_posix(),
        "resolved_record_sha256": sha256_file(resolved_path),
    }
    manifest["blind_oracle_review_history"].append(history)
    _write_json(manifest_path, manifest)
    _append_event(private, "resolve_blind_oracle_review", {
        **history,
        "oracle_cost": cost,
        "ground_truth_read": False,
        "oracle_payload_read_by_reviewer": False,
    })
    _write_participant_context(participant, manifest)
    return {
        "schema_version": SCHEMA_VERSION,
        "review_id": decision["review_id"],
        "request_id": request_id,
        "status": "MATCHED" if revealed_id else "NO_MATCH",
        "matched": bool(revealed_id),
        "oracle_cost": cost,
    }


def _require_string(payload: Mapping[str, Any], field: str, *, allow_empty: bool = False) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise BenchmarkError(f"Réponse: {field} doit être une chaîne non vide.")
    return value


def _require_string_list(payload: Mapping[str, Any], field: str, *, minimum: int = 0) -> list[str]:
    value = payload.get(field)
    if not isinstance(value, list) or len(value) < minimum or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise BenchmarkError(f"Réponse: {field} doit être une liste de chaînes valide.")
    return value


def _validate_confidence(value: Any, *, field: str) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= float(value) <= 1:
        raise BenchmarkError(f"{field} doit être compris entre 0 et 1.")


def _validate_economic_value(value: Any, *, fraction: bool = False) -> None:
    if value == "unknown":
        return
    if fraction:
        _validate_confidence(value, field="recoverable_fraction")
        return
    if not isinstance(value, dict):
        raise BenchmarkError("Une valeur économique doit être 'unknown' ou un objet quantifié.")
    _require_exact_keys(
        value, {"value", "unit", "basis", "period"}, label="Valeur économique"
    )
    number = value.get("value")
    if not isinstance(number, (int, float)) or isinstance(number, bool) or number < 0:
        raise BenchmarkError("Valeur économique négative ou non numérique.")
    for field in ("unit", "basis", "period"):
        _require_string(value, field)


def validate_response(payload: dict[str, Any], *, expected_case_id: str | None = None) -> None:
    _require_exact_keys(
        payload,
        {
            "schema_version", "case_id", "observation", "differential_diagnosis",
            "current_decision", "next_information", "intervention", "validation",
            "economics", "confidence",
        },
        label="Réponse",
    )
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise BenchmarkError("Version de schéma de réponse inconnue.")
    case_id = _validate_opaque_identifier(payload.get("case_id"), field="case_id")
    if expected_case_id is not None and case_id != expected_case_id:
        raise BenchmarkError("La réponse ne correspond pas au cas du run.")
    observation = payload.get("observation")
    if not isinstance(observation, dict):
        raise BenchmarkError("observation est requis.")
    _require_exact_keys(
        observation, {"facts", "data_quality", "phenomenon_to_explain"}, label="Observation"
    )
    _require_string_list(observation, "facts")
    _require_string_list(observation, "data_quality")
    _require_string(observation, "phenomenon_to_explain")
    differential = payload.get("differential_diagnosis")
    if not isinstance(differential, list) or len(differential) > 5:
        raise BenchmarkError("differential_diagnosis doit contenir au plus cinq causes.")
    ranks: list[int] = []
    for item in differential:
        if not isinstance(item, dict) or not isinstance(item.get("rank"), int):
            raise BenchmarkError("Chaque diagnostic exige un rang entier.")
        _require_exact_keys(
            item,
            {"rank", "cause", "confidence", "supporting_evidence", "contrary_evidence", "falsification_test"},
            label="Diagnostic différentiel",
        )
        ranks.append(item["rank"])
        _require_string(item, "cause")
        _validate_confidence(item.get("confidence"), field="diagnostic confidence")
        _require_string_list(item, "supporting_evidence")
        _require_string_list(item, "contrary_evidence")
        _require_string(item, "falsification_test")
    if ranks and sorted(ranks) != list(range(1, len(ranks) + 1)):
        raise BenchmarkError("Les rangs du diagnostic doivent être continus à partir de 1.")
    if payload.get("current_decision") not in DECISIONS:
        raise BenchmarkError("Classe de décision inconnue.")
    next_information = payload.get("next_information")
    if not isinstance(next_information, dict) or not isinstance(next_information.get("needed"), bool):
        raise BenchmarkError("next_information.needed est requis.")
    _require_exact_keys(
        next_information, {"needed", "question", "best_responder", "why", "hypotheses_distinguished", "expected_effort"}, label="Information suivante"
    )
    if next_information["needed"]:
        for field in ("question", "best_responder", "why", "expected_effort"):
            _require_string(next_information, field)
        _require_string_list(next_information, "hypotheses_distinguished", minimum=2)
    else:
        for field in ("question", "best_responder", "why", "expected_effort"):
            _require_string(next_information, field, allow_empty=True)
        if next_information.get("hypotheses_distinguished") != []:
            raise BenchmarkError("Aucune hypothèse ne doit être fournie si aucune information n'est demandée.")
    intervention = payload.get("intervention")
    if not isinstance(intervention, dict) or intervention.get("class") not in INTERVENTIONS:
        raise BenchmarkError("Classe d'intervention inconnue.")
    _require_exact_keys(
        intervention, {"class", "action", "competent_person", "preconditions", "risks", "stop_conditions", "expected_result"}, label="Intervention"
    )
    for field in ("action", "competent_person", "expected_result"):
        _require_string(intervention, field)
    for field in ("preconditions", "risks", "stop_conditions"):
        _require_string_list(intervention, field)
    validation = payload.get("validation")
    if not isinstance(validation, dict):
        raise BenchmarkError("validation est requis.")
    _require_exact_keys(
        validation, {"metric", "period", "controls", "confirming_result", "falsifying_result"}, label="Validation"
    )
    for field in ("metric", "period", "confirming_result", "falsifying_result"):
        _require_string(validation, field)
    _require_string_list(validation, "controls")
    economics = payload.get("economics")
    if not isinstance(economics, dict):
        raise BenchmarkError("economics est requis.")
    _require_exact_keys(
        economics, {"observed_abnormal_energy", "energy_attributable_to_cause", "recoverable_fraction", "financial_savings"}, label="Économie"
    )
    _validate_economic_value(economics.get("observed_abnormal_energy"))
    _validate_economic_value(economics.get("energy_attributable_to_cause"))
    _validate_economic_value(economics.get("recoverable_fraction"), fraction=True)
    _validate_economic_value(economics.get("financial_savings"))
    confidence = payload.get("confidence")
    if not isinstance(confidence, dict):
        raise BenchmarkError("confidence est requis.")
    _require_exact_keys(
        confidence, {"main_cause", "intervention", "justification"}, label="Confiance"
    )
    _validate_confidence(confidence.get("main_cause"), field="main_cause confidence")
    _validate_confidence(confidence.get("intervention"), field="intervention confidence")
    _require_string(confidence, "justification")


def _verify_records(participant: Path, records: Sequence[Mapping[str, Any]]) -> None:
    for record in records:
        relative = Path(str(record["participant_path"]))
        path = _assert_within(participant / relative, participant, label="Fichier accessible")
        if path.is_symlink() or not path.is_file():
            raise BenchmarkIntegrityError(f"Fichier accessible absent ou remplacé: {relative}.")
        if path.stat().st_size != record["size"] or sha256_file(path) != record["sha256"]:
            raise BenchmarkIntegrityError(f"Fichier accessible modifié: {relative}.")


def _verify_engine(participant: Path, manifest: dict[str, Any]) -> None:
    engine = participant / "engine"
    current = file_manifest(engine)
    expected = manifest["engine_files"]
    if current != expected or sha256_bytes(_canonical_json(current)) != manifest["engine_commitment_sha256"]:
        raise BenchmarkIntegrityError("Le snapshot du moteur a été modifié pendant le run.")


def _scan_participant_paths(participant: Path) -> None:
    for path in participant.rglob("*"):
        relative_parts = {part.casefold() for part in path.relative_to(participant).parts}
        forbidden = relative_parts & FORBIDDEN_PARTICIPANT_PARTS
        if forbidden:
            raise BenchmarkIntegrityError(
                "Zone privée détectée dans le workspace participant: " + ", ".join(sorted(forbidden))
            )
        if path.is_symlink():
            raise BenchmarkIntegrityError(f"Lien symbolique interdit dans le run: {path}.")


def _verify_blind_review_records(private: Path, manifest: Mapping[str, Any]) -> None:
    for pending in manifest.get("pending_blind_oracle_reviews", []):
        packet_path = _assert_within(
            private / pending["packet_path"], private, label="Paquet de revue"
        )
        if packet_path.is_symlink() or not packet_path.is_file():
            raise BenchmarkIntegrityError("Paquet de revue aveugle absent.")
        if sha256_file(packet_path) != pending["packet_sha256"]:
            raise BenchmarkIntegrityError("Paquet de revue aveugle modifié.")
        packet = _read_json(packet_path)
        if packet.get("review_id") != pending["review_id"]:
            raise BenchmarkIntegrityError("Identifiant de paquet de revue incohérent.")
    for history in manifest.get("blind_oracle_review_history", []):
        protected = (
            ("packet_path", "packet_sha256", "paquet"),
            ("decision_path", "decision_sha256", "décision"),
            ("resolved_record_path", "resolved_record_sha256", "résolution"),
        )
        for path_field, hash_field, label in protected:
            target = _assert_within(
                private / history[path_field], private, label=f"Trace de {label}"
            )
            if target.is_symlink() or not target.is_file():
                raise BenchmarkIntegrityError(f"Trace de {label} aveugle absente.")
            if sha256_file(target) != history[hash_field]:
                raise BenchmarkIntegrityError(f"Trace de {label} aveugle modifiée.")
        decision = _read_json(private / history["decision_path"])
        validate_blind_oracle_review(decision)
        if (
            decision["review_id"] != history["review_id"]
            or decision["reviewer_id"] != history["reviewer_id"]
            or decision["decision"] != history["decision"]
        ):
            raise BenchmarkIntegrityError("Décision de revue incohérente avec le manifeste.")
        resolved = _read_json(private / history["resolved_record_path"])
        if (
            resolved.get("review_id") != history["review_id"]
            or resolved.get("decision") != history["decision"]
            or resolved.get("selected_oracle_id") != history["selected_oracle_id"]
        ):
            raise BenchmarkIntegrityError("Résolution aveugle incohérente avec le manifeste.")


def verify_run_integrity(
    run_directory: str | Path,
    *,
    repository: str | Path | None = None,
) -> dict[str, Any]:
    _, participant, private = _run_roots(run_directory)
    manifest = _read_json(private / "run_manifest.json")
    _scan_participant_paths(participant)
    _verify_engine(participant, manifest)
    _verify_records(participant, manifest["accessible_files"])
    _verify_blind_review_records(private, manifest)
    log = verify_event_log(private / "events.jsonl")
    if manifest["stage"] == "HOLDOUT":
        repository_root = Path(
            repository or manifest["repository_path_at_prepare"]
        ).resolve()
        if resolve_git_commit(repository_root, manifest["system_git_commit"]) != manifest["system_git_commit"]:
            raise BenchmarkIntegrityError("Commit système introuvable.")
        _assert_repository_engine_matches(repository_root, manifest["system_git_commit"])
    return {
        "status": "valid",
        "run_id": manifest["run_id"],
        "engine_commitment_sha256": manifest["engine_commitment_sha256"],
        "accessible_file_count": len(manifest["accessible_files"]),
        **log,
    }


def finalize_run(
    run_directory: str | Path,
    response_path: str | Path,
    *,
    repository: str | Path | None = None,
) -> dict[str, Any]:
    _, participant, private = _run_roots(run_directory)
    manifest_path = private / "run_manifest.json"
    manifest = _read_json(manifest_path)
    response_target = Path(response_path)
    if manifest.get("pending_blind_oracle_reviews"):
        raise BenchmarkError("Toutes les revues aveugles doivent être résolues avant finalisation.")
    _assert_within(response_target, participant / "output", label="Réponse finale")
    if response_target.resolve() != (participant / "output" / "response.json").resolve():
        raise BenchmarkIntegrityError("La réponse finale doit être output/response.json.")
    payload = _read_json(response_target)
    validate_response(payload, expected_case_id=manifest["case_id"])
    try:
        integrity = verify_run_integrity(run_directory, repository=repository)
    except BenchmarkIntegrityError as exc:
        manifest["status"] = "invalidated"
        manifest["completed_at_utc"] = _utc_now()
        _write_json(manifest_path, manifest)
        _append_event(private, "invalidate_run", {"reason": str(exc)})
        raise
    response_hash = sha256_file(response_target)
    completed_at = _utc_now()
    duration_seconds = max(
        0.0,
        (
            datetime.fromisoformat(completed_at)
            - datetime.fromisoformat(manifest["created_at_utc"])
        ).total_seconds(),
    )
    manifest["status"] = "completed"
    manifest["completed_at_utc"] = completed_at
    manifest["duration_seconds"] = duration_seconds
    manifest["response"] = {
        "participant_path": response_target.relative_to(participant).as_posix(),
        "sha256": response_hash,
        "current_decision": payload["current_decision"],
        "intervention_class": payload["intervention"]["class"],
    }
    _write_json(manifest_path, manifest)
    result = {
        "schema_version": SCHEMA_VERSION,
        "run_id": manifest["run_id"],
        "case_id": manifest["case_id"],
        "status": "completed_unscored",
        "response_sha256": response_hash,
        "current_decision": payload["current_decision"],
        "intervention_class": payload["intervention"]["class"],
        "question_cycles": len(manifest["question_cycles"]),
        "distinct_requests": len(manifest["distinct_request_ids"]),
        "oracle_cost_total": manifest["oracle_cost_total"],
        "duration_seconds": duration_seconds,
        "oracle_matcher_version": manifest.get("oracle_matcher_version", "exact-v1"),
        "followups_revealed": len(manifest["revealed_oracle_ids"]),
        "automatic_matches": manifest.get("automatic_match_count", 0),
        "automatic_no_matches": manifest.get("automatic_no_match_count", 0),
        "blind_reviews": len(manifest.get("blind_oracle_review_history", [])),
        "blind_review_matches": sum(
            item.get("decision") == "MATCH"
            for item in manifest.get("blind_oracle_review_history", [])
        ),
        "final_no_matches": sum(
            request.get("status") == "NO_MATCH"
            for cycle in manifest["question_cycles"] for request in cycle["requests"]
        ),
        "critical_fail_assessed": False,
        "score_available_to_participant": False,
        "integrity": integrity,
    }
    _write_json(private / "result_manifest.json", result)
    _append_event(private, "finalize_run", {
        "response_sha256": response_hash,
        "current_decision": payload["current_decision"],
        "intervention_class": payload["intervention"]["class"],
        "status": "completed_unscored",
        "duration_seconds": duration_seconds,
    })
    return result


def validate_scorecard(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise BenchmarkError("Version de scorecard inconnue.")
    for field in ("case_id", "run_id", "scorer_id"):
        _validate_opaque_identifier(payload.get(field), field=field)
    if payload.get("blinded_scoring") is not True:
        raise BenchmarkError("La scorecard doit déclarer un scoring aveugle.")
    components = payload.get("components")
    if not isinstance(components, dict) or set(components) != set(SCORE_COMPONENT_MAXIMA):
        raise BenchmarkError("Les neuf composantes de score sont obligatoires.")
    total = 0.0
    for name, maximum in SCORE_COMPONENT_MAXIMA.items():
        component = components[name]
        if not isinstance(component, dict):
            raise BenchmarkError(f"Composante invalide: {name}.")
        score = component.get("score")
        if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= maximum:
            raise BenchmarkError(f"Score hors bornes: {name}.")
        _require_string(component, "evidence")
        total += float(score)
    declared = payload.get("total_score")
    if not isinstance(declared, (int, float)) or abs(float(declared) - total) > 1e-9:
        raise BenchmarkError("total_score ne correspond pas aux composantes.")
    if not isinstance(payload.get("critical_fail"), bool):
        raise BenchmarkError("critical_fail doit être booléen.")
    reasons = payload.get("critical_fail_reasons")
    if not isinstance(reasons, list) or any(not isinstance(item, str) for item in reasons):
        raise BenchmarkError("critical_fail_reasons invalide.")
    if payload["critical_fail"] and not reasons:
        raise BenchmarkError("Un CRITICAL_FAIL exige une raison.")
    if not payload["critical_fail"] and reasons:
        raise BenchmarkError("Aucune raison critique sans CRITICAL_FAIL.")
    _validate_sha256(payload.get("response_sha256"), field="response_sha256")
    _validate_sha256(payload.get("ground_truth_commitment_sha256"), field="ground_truth_commitment_sha256")
    if payload.get("predicted_decision") not in DECISIONS:
        raise BenchmarkError("Décision prédite inconnue dans la scorecard.")
    if payload.get("reference_decision") not in DECISIONS:
        raise BenchmarkError("Décision de référence inconnue dans la scorecard.")


def run_manifest_for(run_directory: str | Path) -> dict[str, Any]:
    _, _, private = _run_roots(run_directory)
    return _read_json(private / "run_manifest.json")
