"""Protocole exécutable, fini, borné et auditable pour l’Evidence Plane."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from copy import deepcopy
from datetime import datetime, timezone
from enum import Enum
import math
from typing import Any

from .evidence_plane import (
    EvidenceDataset,
    boundary_ledger,
    contrast_surface,
    describe_evidence_dataset,
    relationship_loss_certificate,
    stable_hash,
    support_atlas,
)


QUERY_SCHEMA = "indicia-evidence-query-v1"
RESPONSE_SCHEMA = "indicia-evidence-response-v1"
SESSION_SCHEMA = "indicia-evidence-session-v1"


class QueryOperation(str, Enum):
    DESCRIBE_SCHEMA = "describe_schema"
    RAW_SLICE = "raw_slice"
    CONTRAST_SURFACE = "contrast_surface"
    RELATIONSHIP_LOSS = "relationship_loss_certificate"
    SUPPORT_ATLAS = "support_atlas"
    BOUNDARY_LEDGER = "boundary_ledger"


@dataclass(frozen=True, slots=True)
class EvidenceQuery:
    query_id: str
    dataset_id: str
    operation: QueryOperation
    arguments: dict[str, Any]
    purpose: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> EvidenceQuery:
        if not isinstance(payload, dict):
            raise ValueError("Une requête Evidence Plane doit être un objet JSON.")
        allowed = {"schema_version", "query_id", "dataset_id", "operation", "arguments", "purpose"}
        unknown = set(payload) - allowed
        if unknown:
            raise ValueError("Clé(s) de requête inconnue(s): " + ", ".join(sorted(unknown)) + ".")
        if payload.get("schema_version", QUERY_SCHEMA) != QUERY_SCHEMA:
            raise ValueError("Version de requête Evidence Plane inconnue.")
        query_id = str(payload.get("query_id", "")).strip()
        if not query_id or len(query_id) > 80 or not all(
            character.isalnum() or character in "-_" for character in query_id
        ):
            raise ValueError("query_id doit contenir 1 à 80 caractères alphanumériques, '-' ou '_'.")
        dataset_id = str(payload.get("dataset_id", "")).strip()
        if not dataset_id:
            raise ValueError("dataset_id est requis.")
        try:
            operation = QueryOperation(str(payload.get("operation", "")))
        except ValueError as exc:
            raise ValueError("Opération Evidence Plane inconnue.") from exc
        arguments = payload.get("arguments", {})
        if not isinstance(arguments, dict):
            raise ValueError("arguments doit être un objet JSON.")
        purpose = str(payload.get("purpose", "")).strip()
        if not purpose or len(purpose) > 500:
            raise ValueError("purpose doit expliquer en 1 à 500 caractères le test demandé.")
        return cls(query_id, dataset_id, operation, arguments, purpose)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": QUERY_SCHEMA,
            "query_id": self.query_id,
            "dataset_id": self.dataset_id,
            "operation": self.operation.value,
            "arguments": self.arguments,
            "purpose": self.purpose,
        }


@dataclass(frozen=True, slots=True)
class QueryBudget:
    maximum_calls: int = 16
    maximum_returned_rows: int = 600
    maximum_context_bytes: int = 400_000
    maximum_pair_comparisons: int = 2_000_000
    maximum_handles: int = 80
    maximum_rejected_calls: int = 8

    def __post_init__(self) -> None:
        if any(type(value) is not int for value in asdict(self).values()):
            raise ValueError("Les budgets doivent être des entiers.")
        if not 1 <= self.maximum_rejected_calls <= 100:
            raise ValueError("maximum_rejected_calls doit être compris entre 1 et 100.")
        if not 1 <= self.maximum_calls <= 100:
            raise ValueError("maximum_calls doit être compris entre 1 et 100.")
        if not 1 <= self.maximum_returned_rows <= 10_000:
            raise ValueError("maximum_returned_rows doit être compris entre 1 et 10000.")
        if not 1_000 <= self.maximum_context_bytes <= 20_000_000:
            raise ValueError("maximum_context_bytes doit être compris entre 1000 et 20000000.")
        if not 1 <= self.maximum_pair_comparisons <= 10_000_000:
            raise ValueError("maximum_pair_comparisons doit être compris entre 1 et 10000000.")
        if not 1 <= self.maximum_handles <= 500:
            raise ValueError("maximum_handles doit être compris entre 1 et 500.")


def query_contract() -> dict[str, Any]:
    return {
        "schema_version": "indicia-evidence-query-contract-v1",
        "request_schema": QUERY_SCHEMA,
        "operations": {
            "describe_schema": {"arguments": [], "purpose": "inventorier avant de formuler un test"},
            "raw_slice": {
                "arguments": ["handle?", "fields", "start?", "limit?", "representation?"],
                "limits": {"fields": 32, "limit": 200},
            },
            "contrast_surface": {
                "arguments": ["group_field", "left_value", "right_value", "fields", "minimum_group_rows?"],
                "limits": {"fields": 32},
            },
            "relationship_loss_certificate": {
                "arguments": ["summarized_relations?", "omitted_examples_limit?"],
            },
            "support_atlas": {
                "arguments": ["split_field", "reference_value", "target_value", "dimensions", "minimum_controls?", "forbidden_outcome_fields?"],
                "limits": {"dimensions": 12, "pair_comparisons": "session budget"},
            },
            "boundary_ledger": {
                "arguments": ["order_field", "fields", "minimum_segment_rows?", "comparison_window_rows?", "candidate_stride?", "maximum_candidates?"],
                "limits": {"fields": 32, "maximum_candidates": 20},
            },
        },
        "arbitrary_code": False,
        "outputs_are_decision_neutral": True,
        "agent_responsibilities": [
            "form hypothesis and choose meaningful fields",
            "justify cohorts, dimensions and tolerances",
            "test alternative explanations",
            "retrieve source slices when summaries are insufficient",
            "abstain when the evidence is insufficient",
        ],
    }


def _allowed_arguments(arguments: dict[str, Any], allowed: set[str]) -> None:
    unknown = set(arguments) - allowed
    if unknown:
        raise ValueError("Argument(s) inconnu(s): " + ", ".join(sorted(unknown)) + ".")


def _list_argument(arguments: dict[str, Any], name: str, maximum: int) -> list[Any]:
    value = arguments.get(name)
    if not isinstance(value, list) or not value or len(value) > maximum:
        raise ValueError(f"{name} doit être une liste de 1 à {maximum} éléments.")
    return value


def _selection_rows(dataset: EvidenceDataset, selector: dict[str, Any]) -> list[dict[str, Any]]:
    kind = selector.get("kind")
    if kind == "all":
        return dataset.rows
    if kind == "equals":
        field = selector["field"]
        value = selector.get("value")
        return [row for row in dataset.rows if row.get(field) == value]
    if kind == "source_rows":
        wanted = set(selector.get("values", []))
        return [row for row in dataset.rows if row["source_row"] in wanted]
    if kind == "ordered_window":
        ordered = sorted(dataset.rows, key=lambda row: row[selector["order_field"]])
        return ordered[int(selector["start_index"]):int(selector["end_index"])]
    raise ValueError("Sélecteur de handle inconnu.")


def _semantic_arguments(query: EvidenceQuery) -> dict[str, Any]:
    """Normalize equivalent requests without changing the declared test or field values."""
    arguments = deepcopy(query.arguments)
    for key in {"start", "limit", "minimum_group_rows", "maximum_categories", "minimum_controls",
                "maximum_pair_comparisons", "omitted_examples_limit", "minimum_segment_rows",
                "candidate_stride", "comparison_window_rows", "maximum_coarse_boundaries",
                "maximum_candidates", "maximum_field_evidence"}:
        if key in arguments and type(arguments[key]) is not int:
            raise ValueError(f"{key} doit être un entier explicite.")
    if query.operation is QueryOperation.RAW_SLICE:
        for key, value in (("start",0),("limit",50),("representation","typed")):
            arguments.setdefault(key,value)
    for key in ("fields", "forbidden_outcome_fields"):
        if isinstance(arguments.get(key), list):
            if any(not isinstance(x,str) for x in arguments[key]):
                raise ValueError(f"{key} exige des noms de champs textuels.")
            arguments[key] = sorted(set(arguments[key]))
    for dimension in arguments.get("dimensions", []):
        if isinstance(dimension,dict) and "tolerance" in dimension:
            value=dimension["tolerance"]
            if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value) or value<0:
                raise ValueError("Tolérance numérique finie et non négative requise.")
    return arguments


def _handle_descriptor(
    dataset: EvidenceDataset,
    *,
    selector: dict[str, Any],
    fields: list[str],
    purpose: str,
    query_id: str,
) -> dict[str, Any]:
    body = {
        "dataset_sha256": dataset.dataset_sha256,
        "selector": selector,
        "fields": sorted(set(fields)),
        "purpose": purpose,
        "query_id": query_id,
    }
    return {
        "handle": "evh-" + stable_hash(body)[:24],
        **body,
    }


@dataclass(slots=True)
class EvidenceQuerySession:
    session_id: str
    dataset_id: str
    dataset_sha256: str
    budget: QueryBudget = field(default_factory=QueryBudget)
    calls: list[dict[str, Any]] = field(default_factory=list)
    handles: dict[str, dict[str, Any]] = field(default_factory=dict)
    returned_rows_used: int = 0
    context_bytes_used: int = 0
    pair_comparisons_used: int = 0
    status: str = "open"
    continuations: list[dict[str, Any]] = field(default_factory=list)
    transport_replays: int = 0

    @classmethod
    def create(
        cls, dataset: EvidenceDataset, *, budget: QueryBudget | None = None
    ) -> EvidenceQuerySession:
        return cls(
            session_id="session-" + stable_hash({"dataset": dataset.dataset_sha256, "contract": QUERY_SCHEMA})[:20],
            dataset_id=dataset.dataset_id,
            dataset_sha256=dataset.dataset_sha256,
            budget=budget or QueryBudget(),
        )

    @property
    def successful_query_ids(self) -> set[str]:
        return {item["query_id"] for item in self.calls if item.get("status") == "success"}

    def _audit_failure(
        self,
        payload: Any,
        message: str,
        *,
        semantic_sha256: str | None = None,
        pair_comparisons: int = 0,
    ) -> None:
        if sum(item.get("status") == "rejected" for item in self.calls) >= self.budget.maximum_rejected_calls:
            return  # CLI trace records further refused attempts without growing session context.
        query_id = payload.get("query_id") if isinstance(payload, dict) else None
        self.calls.append(
            {
                "attempt": len(self.calls) + 1,
                "at_utc": datetime.now(timezone.utc).isoformat(),
                "query_id": str(query_id or "INVALID"),
                "status": "rejected",
                "semantic_sha256": semantic_sha256,
                "request_sha256": stable_hash(payload),
                "error": message,
                "pair_comparisons": pair_comparisons,
            }
        )
        self.pair_comparisons_used += pair_comparisons
        if sum(item.get("status") == "rejected" for item in self.calls) >= self.budget.maximum_rejected_calls:
            self.status = "failure_budget_exhausted"

    def execute(self, dataset: EvidenceDataset, payload: dict[str, Any]) -> dict[str, Any]:
        if self.status != "open":
            raise ValueError("La session Evidence Plane est fermée.")
        if dataset.dataset_id != self.dataset_id or dataset.dataset_sha256 != self.dataset_sha256:
            raise ValueError("La session ne correspond pas au snapshot Evidence Plane.")
        if len(self.successful_query_ids) >= self.budget.maximum_calls:
            self.status = "budget_exhausted"
            raise ValueError("Budget d’appels Evidence Plane épuisé; conclure ou s’abstenir.")
        try:
            query = EvidenceQuery.from_dict(payload)
            query = EvidenceQuery(query.query_id, query.dataset_id, query.operation, deepcopy(query.arguments), query.purpose)
            if query.query_id in self.successful_query_ids:
                raise ValueError("query_id déjà utilisé par une requête réussie.")
            if query.dataset_id != dataset.dataset_id:
                raise ValueError("dataset_id ne correspond pas à la session.")
            semantic_sha256 = stable_hash(
                {
                    "dataset_sha256": dataset.dataset_sha256,
                    "operation": query.operation.value,
                    "arguments": _semantic_arguments(query),
                }
            )
            if any(item.get("status") == "success" and item.get("semantic_sha256") == semantic_sha256 for item in self.calls):
                raise ValueError("Requête sémantiquement répétée; utilisez la preuve existante ou changez le test.")
            response, pending_handles, returned_rows, pair_comparisons, relations = self._dispatch(dataset, query)
            if len(self.handles) + len(pending_handles) > self.budget.maximum_handles:
                raise ValueError("Budget de handles Evidence Plane dépassé.")
            if self.returned_rows_used + returned_rows > self.budget.maximum_returned_rows:
                raise ValueError("Budget cumulé de lignes retournées dépassé.")
            if self.pair_comparisons_used + pair_comparisons > self.budget.maximum_pair_comparisons:
                raise ValueError("Budget cumulé de comparaisons de paires dépassé.")
            request_sha256 = stable_hash(query.to_dict())
            relationship_metadata = relationship_loss_certificate(
                sorted(dataset.field_keys),
                summarized_relations=relations,
                omitted_examples_limit=5,
            )
            envelope = {
                "schema_version": RESPONSE_SCHEMA,
                "session_id": self.session_id,
                "query_id": query.query_id,
                "dataset_id": dataset.dataset_id,
                "dataset_sha256": dataset.dataset_sha256,
                "operation": query.operation.value,
                "purpose": query.purpose,
                "request_sha256": request_sha256,
                "semantic_sha256": semantic_sha256,
                "result": response,
                "retrieval_handles": pending_handles,
                "relationship_metadata": relationship_metadata,
                "uncertainty": {
                    "status": "not_resolved_by_deterministic_tool",
                    "claim_boundary": response.get(
                        "claim_boundary",
                        "Retrieved or summarized values require agent interpretation and alternative testing.",
                    ),
                    "omitted_pairwise_relations": relationship_metadata[
                        "omitted_pairwise_relation_count"
                    ],
                    "higher_order_relations_summarized": False,
                },
                "evidence_sufficiency": {
                    "status": "requires_agent_assessment",
                    "common_support": (
                        response.get("full_support")
                        if query.operation is QueryOperation.SUPPORT_ATLAS
                        else "not_evaluated_in_this_query"
                    ),
                    "raw_retrieval_available": bool(pending_handles),
                    "abstention_is_valid": True,
                },
                "provenance": {
                    "source_sha256": dataset.source_sha256,
                    "snapshot": "evidence_dataset.json",
                    "source_row_field": "source_row",
                    "value_layers": ["canonical_normalized", "auxiliary_typed", "auxiliary_raw_when_requested"],
                },
                "resource_usage": {
                    "call": len(self.calls) + 1,
                    "returned_rows_this_call": returned_rows,
                    "pair_comparisons_this_call": pair_comparisons,
                },
                "decision": None,
                "agent_owns_interpretation": True,
            }
            envelope["resource_usage"].update(
                {
                    "response_bytes": 0,
                    "cumulative_calls": len(self.calls) + 1,
                    "cumulative_returned_rows": self.returned_rows_used + returned_rows,
                    "cumulative_context_bytes": self.context_bytes_used,
                    "cumulative_pair_comparisons": self.pair_comparisons_used + pair_comparisons,
                    "budget": asdict(self.budget),
                }
            )
            # The digest field is part of the actual response bytes. Its length is fixed.
            envelope["response_sha256"] = "0" * 64
            encoded_size = 0
            for _ in range(10):
                encoded_size = len(stable_json_bytes(envelope))
                if envelope["resource_usage"]["response_bytes"] == encoded_size:
                    break
                envelope["resource_usage"]["response_bytes"] = encoded_size
                envelope["resource_usage"]["cumulative_context_bytes"] = (
                    self.context_bytes_used + encoded_size
                )
            encoded_size = len(stable_json_bytes(envelope))
            envelope["resource_usage"]["response_bytes"] = encoded_size
            envelope["resource_usage"]["cumulative_context_bytes"] = (
                self.context_bytes_used + encoded_size
            )
            if self.context_bytes_used + encoded_size > self.budget.maximum_context_bytes:
                raise ValueError("Budget cumulé d’octets de contexte dépassé.")
        except (TypeError, ValueError, KeyError) as exc:
            semantic = locals().get("semantic_sha256")
            self._audit_failure(payload, str(exc), semantic_sha256=semantic,
                                pair_comparisons=locals().get("pair_comparisons", 0))
            if len(self.successful_query_ids) >= self.budget.maximum_calls:
                self.status = "budget_exhausted"
            raise ValueError(str(exc)) from exc
        for descriptor in pending_handles:
            self.handles[descriptor["handle"]] = descriptor
        self.returned_rows_used += returned_rows
        self.context_bytes_used += encoded_size
        self.pair_comparisons_used += pair_comparisons
        del envelope["response_sha256"]
        response_sha256 = stable_hash(envelope)
        envelope["response_sha256"] = response_sha256
        self.calls.append(
            {
                "attempt": len(self.calls) + 1,
                "at_utc": datetime.now(timezone.utc).isoformat(),
                "query_id": query.query_id,
                "operation": query.operation.value,
                "purpose": query.purpose,
                "status": "success",
                "request_sha256": request_sha256,
                "semantic_sha256": semantic_sha256,
                "response_sha256": response_sha256,
                "handles": [item["handle"] for item in pending_handles],
                "returned_rows": returned_rows,
                "context_bytes": encoded_size,
                "pair_comparisons": pair_comparisons,
            }
        )
        if len(self.successful_query_ids) >= self.budget.maximum_calls:
            self.status = "budget_exhausted"
        return envelope

    def continue_investigation(self, *, budget: dict[str, Any], progress_query_ids: list[str],
                               unresolved_hypotheses: list[str], next_tests: list[str],
                               decision_impact: str) -> dict[str, Any]:
        """Bounded continuation chosen by the analyst; never an evidence promotion.

        Retains all usage/history. Requires new successful evidence since the last
        continuation. Hard resource ceilings still apply to the entire session.
        This is an auditable planning checkpoint, not a calibrated value estimate.
        """
        if self.status in {"closed", "failure_budget_exhausted"}:
            raise ValueError("Une session close ou sans progrès ne peut être prolongée.")
        previous = {q for entry in self.continuations for q in entry["progress_query_ids"]}
        ids = set(progress_query_ids)
        if not ids or ids - self.successful_query_ids or ids & previous:
            raise ValueError("La continuation exige de nouvelles preuves réussies non réutilisées.")
        if (not unresolved_hypotheses or not next_tests or
            any(not isinstance(x, str) or not x.strip() for x in [*unresolved_hypotheses, *next_tests, decision_impact])):
            raise ValueError("Hypothèses non résolues, prochains tests et impact décisionnel requis.")
        current = asdict(self.budget)
        if set(budget) - set(current):
            raise ValueError("Ressource de budget inconnue.")
        proposed = QueryBudget(**{**current, **budget})
        target = asdict(proposed)
        if any(target[k] < current[k] for k in current) or target == current:
            raise ValueError("La continuation doit augmenter un budget sans remettre les compteurs à zéro.")
        if target["maximum_rejected_calls"] != current["maximum_rejected_calls"]:
            raise ValueError("Le budget d'échecs ne peut être prolongé.")
        if target["maximum_calls"] - current["maximum_calls"] > max(4, 2*len(set(unresolved_hypotheses))):
            raise ValueError("Prolongation trop large pour les hypothèses déclarées.")
        record = {"at_utc":datetime.now(timezone.utc).isoformat(),
                  "progress_query_ids":sorted(ids), "unresolved_hypotheses":unresolved_hypotheses,
                  "next_tests":next_tests, "decision_impact":decision_impact,
                  "before":current, "after":target, "decision":None}
        self.continuations.append(record)
        self.budget = proposed
        self.status = "open"
        return record

    def _dispatch(
        self, dataset: EvidenceDataset, query: EvidenceQuery
    ) -> tuple[dict[str, Any], list[dict[str, Any]], int, int, list[tuple[str, str]]]:
        arguments = query.arguments
        operation = query.operation
        handles: list[dict[str, Any]] = []
        returned_rows = 0
        pair_comparisons = 0
        relations: list[tuple[str, str]] = []
        if operation is QueryOperation.DESCRIBE_SCHEMA:
            _allowed_arguments(arguments, set())
            result = describe_evidence_dataset(dataset)
            handles.append(_handle_descriptor(dataset, selector={"kind": "all"}, fields=sorted(dataset.field_keys), purpose="dataset row scope", query_id=query.query_id))
        elif operation is QueryOperation.RAW_SLICE:
            _allowed_arguments(arguments, {"handle", "fields", "start", "limit", "representation"})
            fields = dataset.require_fields(_list_argument(arguments, "fields", 32))
            start = int(arguments.get("start", 0))
            limit = int(arguments.get("limit", 50))
            if start < 0 or not 1 <= limit <= 200:
                raise ValueError("raw_slice impose start >= 0 et limit entre 1 et 200.")
            representation = str(arguments.get("representation", "typed"))
            if representation not in {"typed", "raw_auxiliary"}:
                raise ValueError("representation doit valoir typed ou raw_auxiliary.")
            handle = arguments.get("handle")
            if handle is None:
                selected_rows = dataset.rows
            else:
                descriptor = self.handles.get(str(handle))
                if descriptor is None:
                    raise ValueError("Handle de récupération inconnu.")
                if descriptor.get("dataset_sha256") != dataset.dataset_sha256:
                    raise ValueError("Handle associé à un autre dataset.")
                selected_rows = _selection_rows(dataset, descriptor["selector"])
            sliced = selected_rows[start:start + limit]
            auxiliary_keys = {item["key"] for item in dataset.fields if item["origin"] == "auxiliary"}
            output_rows = []
            for row in sliced:
                values: dict[str, Any] = {}
                for field_name in fields:
                    if representation == "raw_auxiliary" and field_name in auxiliary_keys:
                        values[field_name] = dataset.raw_auxiliary_for_row(
                            row["source_row"]
                        ).get(field_name)
                    else:
                        values[field_name] = row.get(field_name)
                output_rows.append({"row_id": f"source-row-{row['source_row']}", "source_row": row["source_row"], **values})
            result = {
                "row_scope_size": len(selected_rows),
                "start": start,
                "limit": limit,
                "returned": len(output_rows),
                "representation": representation,
                "rows": output_rows,
                "decision": None,
            }
            returned_rows = len(output_rows)
            handles.append(_handle_descriptor(dataset, selector={"kind": "source_rows", "values": [row["source_row"] for row in sliced]}, fields=fields, purpose="exact returned source slice", query_id=query.query_id))
        elif operation is QueryOperation.CONTRAST_SURFACE:
            _allowed_arguments(arguments, {"group_field", "left_value", "right_value", "fields", "minimum_group_rows", "maximum_categories"})
            group_field = dataset.require_fields([str(arguments.get("group_field", ""))])[0]
            fields = dataset.require_fields(_list_argument(arguments, "fields", 32))
            if group_field in fields:
                raise ValueError("group_field ne doit pas être répété dans fields.")
            result = contrast_surface(dataset.rows, group_field=group_field, left_value=arguments.get("left_value"), right_value=arguments.get("right_value"), fields=fields, minimum_group_rows=int(arguments.get("minimum_group_rows", 5)), maximum_categories=int(arguments.get("maximum_categories", 50)))
            for label, value in (("left", arguments.get("left_value")), ("right", arguments.get("right_value"))):
                handles.append(_handle_descriptor(dataset, selector={"kind": "equals", "field": group_field, "value": value}, fields=[group_field, *fields], purpose=f"contrast {label} cohort", query_id=query.query_id))
            relations = [(group_field, field_name) for field_name in fields]
        elif operation is QueryOperation.RELATIONSHIP_LOSS:
            _allowed_arguments(arguments, {"summarized_relations", "omitted_examples_limit"})
            supplied = arguments.get("summarized_relations", [])
            if not isinstance(supplied, list) or len(supplied) > 100:
                raise ValueError("summarized_relations doit être une liste bornée à 100 relations.")
            relations = []
            for pair in supplied:
                if not isinstance(pair, list) or len(pair) != 2:
                    raise ValueError("Chaque relation résumée doit contenir exactement deux champs.")
                left, right = dataset.require_fields([str(pair[0]), str(pair[1])])
                relations.append((left, right))
            result = relationship_loss_certificate(sorted(dataset.field_keys), summarized_relations=relations, omitted_examples_limit=int(arguments.get("omitted_examples_limit", 20)))
            handles.append(_handle_descriptor(dataset, selector={"kind": "all"}, fields=sorted(dataset.field_keys), purpose="raw retrieval for omitted relationships", query_id=query.query_id))
        elif operation is QueryOperation.SUPPORT_ATLAS:
            _allowed_arguments(arguments, {"split_field", "reference_value", "target_value", "dimensions", "minimum_controls", "forbidden_outcome_fields", "maximum_pair_comparisons"})
            split_field = dataset.require_fields([str(arguments.get("split_field", ""))])[0]
            reference_value = arguments.get("reference_value")
            target_value = arguments.get("target_value")
            if reference_value == target_value:
                raise ValueError("Référence et cible doivent être distinctes.")
            dimensions = _list_argument(arguments, "dimensions", 12)
            if any(not isinstance(item, dict) for item in dimensions):
                raise ValueError("Chaque dimension doit être un objet typé.")
            dimension_fields = dataset.require_fields([str(item.get("field", "")) for item in dimensions])
            for item, field_name in zip(dimensions, dimension_fields):
                unknown = set(item) - {"field", "kind", "tolerance", "scale"}
                if unknown:
                    raise ValueError("Paramètre(s) de dimension inconnu(s): " + ", ".join(sorted(unknown)) + ".")
                if item.get("kind", "categorical") not in {"categorical", "numeric"}:
                    raise ValueError("kind de dimension doit valoir categorical ou numeric.")
                item["field"] = field_name
            forbidden = dataset.require_fields([str(item) for item in arguments.get("forbidden_outcome_fields", [])]) if arguments.get("forbidden_outcome_fields") else []
            reference = [row for row in dataset.rows if row.get(split_field) == reference_value]
            target = [row for row in dataset.rows if row.get(split_field) == target_value]
            requested_limit = int(arguments.get("maximum_pair_comparisons", self.budget.maximum_pair_comparisons - self.pair_comparisons_used))
            remaining = self.budget.maximum_pair_comparisons - self.pair_comparisons_used
            if requested_limit > remaining:
                raise ValueError("maximum_pair_comparisons dépasse le budget restant de session.")
            result = support_atlas(reference, target, dimensions=dimensions, minimum_controls=int(arguments.get("minimum_controls", 5)), forbidden_outcome_fields=forbidden, maximum_pair_comparisons=requested_limit)
            result["split"] = {"field": split_field, "reference_value": reference_value, "target_value": target_value}
            pair_comparisons = int(result["pair_comparisons"])
            for label, value in (("reference", reference_value), ("target", target_value)):
                handles.append(_handle_descriptor(dataset, selector={"kind": "equals", "field": split_field, "value": value}, fields=[split_field, *dimension_fields], purpose=f"support {label} cohort", query_id=query.query_id))
            relations = [(split_field, field_name) for field_name in dimension_fields]
        else:
            _allowed_arguments(arguments, {"order_field", "fields", "minimum_segment_rows", "candidate_stride", "comparison_window_rows", "maximum_coarse_boundaries", "maximum_candidates", "maximum_field_evidence"})
            order_field = dataset.require_fields([str(arguments.get("order_field", ""))])[0]
            fields = dataset.require_fields(_list_argument(arguments, "fields", 32))
            if order_field in fields:
                raise ValueError("order_field ne doit pas être répété dans fields.")
            result = boundary_ledger(dataset.rows, order_field=order_field, fields=fields, minimum_segment_rows=int(arguments.get("minimum_segment_rows", 20)), candidate_stride=int(arguments.get("candidate_stride", 1)), comparison_window_rows=arguments.get("comparison_window_rows"), maximum_coarse_boundaries=int(arguments.get("maximum_coarse_boundaries", 256)), maximum_candidates=int(arguments.get("maximum_candidates", 10)), maximum_field_evidence=int(arguments.get("maximum_field_evidence", 8)))
            window = int(result["comparison_window_rows"])
            for index, candidate in enumerate(result["candidates"]):
                boundary = int(candidate["boundary_index"])
                for side, start, end in (("before", max(0, boundary - window), boundary), ("after", boundary, min(len(dataset.rows), boundary + window))):
                    handles.append(_handle_descriptor(dataset, selector={"kind": "ordered_window", "order_field": order_field, "start_index": start, "end_index": end}, fields=[order_field, *fields], purpose=f"boundary candidate {index + 1} {side} window", query_id=query.query_id))
            relations = [(order_field, field_name) for field_name in fields]
        return result, handles, returned_rows, pair_comparisons, relations

    def close(self, *, reason: str) -> None:
        if not reason.strip():
            raise ValueError("Une raison de clôture est requise.")
        if self.status == "open":
            self.status = "closed"

    def to_dict(self) -> dict[str, Any]:
        body = {
            "schema_version": SESSION_SCHEMA,
            "session_id": self.session_id,
            "dataset_id": self.dataset_id,
            "dataset_sha256": self.dataset_sha256,
            "budget": asdict(self.budget),
            "usage": {
                "calls": len(self.calls),
                "returned_rows": self.returned_rows_used,
                "context_bytes": self.context_bytes_used,
                "pair_comparisons": self.pair_comparisons_used,
                "handles": len(self.handles),
                "transport_replays": self.transport_replays,
            },
            "calls": self.calls,
            "handles": self.handles,
            "status": self.status,
            "continuations": self.continuations,
            "termination_policy": "agent concludes, abstains, or stops when budgets/repetition prevent useful new evidence",
        }
        return {**body, "session_sha256": stable_hash(body)}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> EvidenceQuerySession:
        if payload.get("schema_version") != SESSION_SCHEMA:
            raise ValueError("Version de session Evidence Plane inconnue.")
        body = {key: value for key, value in payload.items() if key != "session_sha256"}
        if payload.get("session_sha256") != stable_hash(body):
            raise ValueError("Le hash de session Evidence Plane ne correspond pas au contenu.")
        usage = payload.get("usage")
        if not isinstance(usage, dict):
            raise ValueError("Usage de session Evidence Plane absent.")
        if any(type(usage.get(key)) is not int for key in ("calls","handles","returned_rows","context_bytes","pair_comparisons")):
            raise ValueError("Compteurs de session entiers requis.")
        if type(usage.get("transport_replays",0)) is not int:
            raise ValueError("Compteur de replay entier requis.")
        if (not isinstance(payload.get("calls"),list) or any(not isinstance(x,dict) or
            x.get("status") not in {"success","rejected"} for x in payload["calls"])
            or not isinstance(payload.get("handles"),dict)):
            raise ValueError("Journal de session invalide.")
        session = cls(
            session_id=str(payload.get("session_id")),
            dataset_id=str(payload.get("dataset_id")),
            dataset_sha256=str(payload.get("dataset_sha256")),
            budget=QueryBudget(**payload.get("budget", {})),
            calls=list(payload.get("calls", [])),
            handles=dict(payload.get("handles", {})),
            returned_rows_used=int(usage.get("returned_rows", 0)),
            context_bytes_used=int(usage.get("context_bytes", 0)),
            pair_comparisons_used=int(usage.get("pair_comparisons", 0)),
            status=str(payload.get("status", "open")),
            continuations=list(payload.get("continuations", [])),
            transport_replays=usage.get("transport_replays",0),
        )
        if usage.get("calls") != len(session.calls) or usage.get("handles") != len(session.handles):
            raise ValueError("Compteurs de session Evidence Plane incohérents.")
        if len(session.successful_query_ids) > session.budget.maximum_calls:
            raise ValueError("La session dépasse son budget d’appels déclaré.")
        if any(value < 0 for value in (
            session.returned_rows_used,
            session.context_bytes_used,
            session.pair_comparisons_used,
        )):
            raise ValueError("Compteurs de session Evidence Plane négatifs.")
        for handle, descriptor in session.handles.items():
            if descriptor.get("handle") != handle or descriptor.get("dataset_sha256") != session.dataset_sha256:
                raise ValueError("Handle de session Evidence Plane incohérent.")
            body = {key:value for key,value in descriptor.items() if key != "handle"}
            if handle != "evh-" + stable_hash(body)[:24] or descriptor.get("query_id") not in session.successful_query_ids:
                raise ValueError("Handle de session Evidence Plane sans provenance valide.")
        successful = [call for call in session.calls if call.get("status") == "success"]
        if len(successful) != len(session.successful_query_ids):
            raise ValueError("Identifiants de requête dupliqués.")
        for key, used, limit in (("returned_rows", session.returned_rows_used, session.budget.maximum_returned_rows),
                                ("context_bytes", session.context_bytes_used, session.budget.maximum_context_bytes),
                                ("pair_comparisons", session.pair_comparisons_used, session.budget.maximum_pair_comparisons)):
            accounted = session.calls if key == "pair_comparisons" else successful
            if any(type(call.get(key,0)) is not int or call.get(key,0) < 0 for call in accounted) or sum(call.get(key,0) for call in accounted) != used or used > limit:
                raise ValueError("Compteurs de session incohérents avec les preuves réussies.")
        if len(session.handles) > session.budget.maximum_handles or session.status not in {"open", "closed", "budget_exhausted", "failure_budget_exhausted"}:
            raise ValueError("État ou handles de session invalides.")
        if not 0 <= session.transport_replays <= session.budget.maximum_rejected_calls:
            raise ValueError("Compteur de replay hors budget.")
        return session


def stable_json_bytes(value: Any) -> bytes:
    import json

    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def validate_finding_provenance(
    payload: dict[str, Any], session: EvidenceQuerySession
) -> None:
    """Valide les liens de preuve sans juger le contenu analytique du constat."""

    if payload.get("schema_version") != "indicia-agent-findings-v1":
        raise ValueError("Version de registre de constats inconnue.")
    if payload.get("ground_truth_used") is not False:
        raise ValueError("Le registre de constats doit déclarer ground_truth_used=false.")
    findings = payload.get("findings")
    if not isinstance(findings, list):
        raise ValueError("findings doit être une liste.")
    allowed_statuses = {
        "CONFIRME",
        "A_CONSERVER_AVEC_RESERVES",
        "INSUFFISAMMENT_ETAYE",
        "REJETE",
        "ABSTAIN",
    }
    successful = session.successful_query_ids
    seen = set()
    for finding in findings:
        identifier = str(finding.get("finding_id", "")).strip()
        if not identifier or identifier in seen:
            raise ValueError("Chaque constat exige finding_id.")
        seen.add(identifier)
        if finding.get("status") not in allowed_statuses:
            raise ValueError(f"{identifier}: statut inconnu.")
        if not str(finding.get("claim_or_abstention", "")).strip():
            raise ValueError(f"{identifier}: claim_or_abstention est requis.")
        query_ids = finding.get("evidence_query_ids", [])
        handles = finding.get("evidence_handles", [])
        if not isinstance(query_ids, list) or not isinstance(handles, list):
            raise ValueError(f"{identifier}: références probatoires invalides.")
        unknown_queries = sorted(set(query_ids) - successful)
        unknown_handles = sorted(set(handles) - set(session.handles))
        if unknown_queries or unknown_handles:
            raise ValueError(f"{identifier}: référence de preuve inconnue.")
        if any(session.handles[h]["query_id"] not in query_ids for h in handles):
            raise ValueError(f"{identifier}: handle sans sa requête source.")
        if finding["status"] in {"CONFIRME", "A_CONSERVER_AVEC_RESERVES"}:
            if not query_ids or not handles:
                raise ValueError(f"{identifier}: une conclusion conservée exige requêtes et handles.")
            alternatives = finding.get("alternative_explanations_tested")
            if not isinstance(alternatives, list) or not alternatives:
                raise ValueError(f"{identifier}: au moins une alternative testée est requise.")
        if finding["status"] in {"ABSTAIN", "INSUFFISAMMENT_ETAYE"} and not str(
            finding.get("evidence_gap", "")
        ).strip():
            raise ValueError(f"{identifier}: l’insuffisance de preuve doit être explicitée.")
