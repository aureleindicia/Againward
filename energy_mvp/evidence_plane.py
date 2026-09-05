"""Evidence Plane de production, décisionnellement neutre et local-first.

Ce module conserve un snapshot typé et fournit des surfaces relationnelles. Il
ne formule ni anomalie, ni cause, ni économie récupérable.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from bisect import bisect_left
from collections import Counter
from dataclasses import dataclass
from statistics import median
from typing import Any, Iterable, Sequence

from .models import LoadedData, Reading


EPSILON = 1e-12
EVIDENCE_DATASET_SCHEMA = "indicia-evidence-dataset-v1"


def stable_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _round(value: float | None, digits: int = 6) -> float | None:
    return None if value is None else round(float(value), digits)


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _quantile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("Un quantile exige au moins une valeur.")
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _mad(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    center = median(values)
    return 1.4826 * median(abs(float(value) - center) for value in values)


def _numeric_profile(values: Sequence[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "median": None, "q25": None, "q75": None, "mad": None}
    return {
        "count": len(values),
        "median": _round(median(values)),
        "q25": _round(_quantile(values, 0.25)),
        "q75": _round(_quantile(values, 0.75)),
        "mad": _round(_mad(values)),
    }


def _categorical_profile(values: Sequence[Any], maximum_categories: int = 50) -> dict[str, Any]:
    counts = Counter(str(value) for value in values)
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return {
        "count": len(values),
        "distinct": len(counts),
        "counts": dict(ordered[:maximum_categories]),
        "counts_truncated": len(ordered) > maximum_categories,
    }


def _power_kw(reading: Reading) -> float | None:
    if reading.power_kw is not None:
        return reading.power_kw
    if reading.interval_hours is not None and reading.interval_hours > 0:
        return reading.energy_kwh / reading.interval_hours
    return None


@dataclass(frozen=True, slots=True)
class EvidenceDataset:
    dataset_id: str
    source_sha256: str
    dataset_sha256: str
    rows: list[dict[str, Any]]
    fields: list[dict[str, Any]]
    raw_auxiliary_source_rows: list[int]
    raw_auxiliary_columns: dict[str, list[Any]]
    measurement_kind: str
    timestamp_position: str
    site_timezone: str | None

    @classmethod
    def from_loaded_data(
        cls, loaded: LoadedData, *, source_sha256: str
    ) -> EvidenceDataset:
        rows: list[dict[str, Any]] = []
        for reading in loaded.readings:
            row = {
                "source_row": reading.source_row,
                "timestamp": reading.timestamp.isoformat(),
                "operational_timestamp": reading.operational_timestamp.isoformat(),
                "energy_kwh": reading.energy_kwh,
                "power_kw": _power_kw(reading),
                "interval_hours": reading.interval_hours,
            }
            optional_values = {
                "production": reading.production,
                "production_active": reading.production_active,
                "outside_temperature_c": reading.outside_temperature_c,
                "shift": reading.shift,
                "product_type": reading.product_type,
                "tariff_per_kwh": reading.tariff_per_kwh,
            }
            row.update({key: value for key, value in optional_values.items() if value is not None})
            row.update(loaded.auxiliary.values_for_row(reading.source_row))
            rows.append(row)
        raw_source_rows = list(loaded.auxiliary.source_rows)
        raw_auxiliary_columns = {
            key: list(values) for key, values in loaded.auxiliary.raw_columns.items()
        }
        canonical = [
            ("source_row", "source_row", "integer", None),
            ("timestamp", loaded.columns.get("date", "timestamp"), "datetime", None),
            ("operational_timestamp", "operational_timestamp", "datetime", None),
            ("energy_kwh", loaded.columns.get("energy", "energy_kwh"), "number", "kWh"),
            ("power_kw", loaded.columns.get("power", "power_kw"), "number", "kW"),
            ("production", loaded.columns.get("production", "production"), "number", None),
            (
                "production_active",
                loaded.columns.get("production_active", "production_active"),
                "boolean",
                None,
            ),
            (
                "outside_temperature_c",
                loaded.columns.get("temperature", "outside_temperature_c"),
                "number",
                "°C",
            ),
            ("shift", loaded.columns.get("shift", "shift"), "string", None),
            (
                "product_type",
                loaded.columns.get("product_type", "product_type"),
                "string",
                None,
            ),
            (
                "tariff_per_kwh",
                loaded.columns.get("tariff", "tariff_per_kwh"),
                "number",
                "currency/kWh",
            ),
            ("interval_hours", "interval_hours", "number", "h"),
        ]
        fields: list[dict[str, Any]] = []
        for key, original_name, data_type, unit in canonical:
            present = sum(row.get(key) is not None for row in rows)
            fields.append(
                {
                    "key": key,
                    "original_name": original_name,
                    "origin": "canonical",
                    "data_type": data_type,
                    "unit": unit,
                    "present_count": present,
                    "missing_count": len(rows) - present,
                    "completeness": _round(present / len(rows), 6) if rows else 0.0,
                    "source_column_index": None,
                    "high_cardinality": key in {"source_row", "timestamp"},
                }
            )
        for item in loaded.auxiliary.fields:
            fields.append(
                {
                    "key": item.key,
                    "original_name": item.original_name,
                    "normalized_name": item.normalized_name,
                    "origin": "auxiliary",
                    "data_type": item.inferred_type,
                    "unit": None,
                    "present_count": item.present_count,
                    "missing_count": item.missing_count,
                    "completeness": _round(
                        item.present_count / len(rows), 6
                    ) if rows else 0.0,
                    "distinct_count": item.distinct_count,
                    "source_column_index": item.source_column_index,
                    "high_cardinality": item.high_cardinality,
                    "truncated_value_count": item.truncated_value_count,
                }
            )
        body = {
            "source_sha256": source_sha256,
            "rows": rows,
            "fields": fields,
            "raw_auxiliary_source_rows": raw_source_rows,
            "raw_auxiliary_columns": raw_auxiliary_columns,
            "measurement_kind": loaded.measurement_kind.value,
            "timestamp_position": loaded.timestamp_position,
            "site_timezone": loaded.site_timezone,
        }
        dataset_sha256 = stable_hash(body)
        return cls(
            dataset_id=f"dataset-{source_sha256[:16]}",
            source_sha256=source_sha256,
            dataset_sha256=dataset_sha256,
            rows=rows,
            fields=fields,
            raw_auxiliary_source_rows=raw_source_rows,
            raw_auxiliary_columns=raw_auxiliary_columns,
            measurement_kind=loaded.measurement_kind.value,
            timestamp_position=loaded.timestamp_position,
            site_timezone=loaded.site_timezone,
        )

    @property
    def field_keys(self) -> set[str]:
        return {item["key"] for item in self.fields}

    def require_fields(self, names: Iterable[str]) -> list[str]:
        normalized = list(dict.fromkeys(str(name) for name in names))
        unknown = sorted(set(normalized) - self.field_keys)
        if unknown:
            raise ValueError("Champ(s) inconnu(s): " + ", ".join(unknown) + ".")
        return normalized

    def raw_auxiliary_for_row(self, source_row: int) -> dict[str, Any]:
        index = bisect_left(self.raw_auxiliary_source_rows, source_row)
        if (
            index >= len(self.raw_auxiliary_source_rows)
            or self.raw_auxiliary_source_rows[index] != source_row
        ):
            return {}
        return {
            key: values[index] for key, values in self.raw_auxiliary_columns.items()
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": EVIDENCE_DATASET_SCHEMA,
            "dataset_id": self.dataset_id,
            "source_sha256": self.source_sha256,
            "dataset_sha256": self.dataset_sha256,
            "rows": self.rows,
            "fields": self.fields,
            "raw_auxiliary_source_rows": self.raw_auxiliary_source_rows,
            "raw_auxiliary_columns": self.raw_auxiliary_columns,
            "measurement_kind": self.measurement_kind,
            "timestamp_position": self.timestamp_position,
            "site_timezone": self.site_timezone,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> EvidenceDataset:
        if payload.get("schema_version") != EVIDENCE_DATASET_SCHEMA:
            raise ValueError("Version de snapshot Evidence Plane inconnue.")
        rows = payload.get("rows")
        fields = payload.get("fields")
        raw_source_rows = payload.get("raw_auxiliary_source_rows", [])
        raw_auxiliary_columns = payload.get("raw_auxiliary_columns", {})
        if (
            not isinstance(rows, list)
            or not isinstance(fields, list)
            or not isinstance(raw_source_rows, list)
            or raw_source_rows != sorted(set(raw_source_rows))
            or not isinstance(raw_auxiliary_columns, dict)
            or any(
                not isinstance(values, list) or len(values) != len(raw_source_rows)
                for values in raw_auxiliary_columns.values()
            )
        ):
            raise ValueError("Snapshot Evidence Plane invalide.")
        body = {
            "source_sha256": payload.get("source_sha256"),
            "rows": rows,
            "fields": fields,
            "raw_auxiliary_source_rows": raw_source_rows,
            "raw_auxiliary_columns": raw_auxiliary_columns,
            "measurement_kind": payload.get("measurement_kind"),
            "timestamp_position": payload.get("timestamp_position"),
            "site_timezone": payload.get("site_timezone"),
        }
        actual_hash = stable_hash(body)
        if actual_hash != payload.get("dataset_sha256"):
            raise ValueError("Le hash du snapshot Evidence Plane ne correspond pas au contenu.")
        return cls(
            dataset_id=str(payload.get("dataset_id")),
            source_sha256=str(payload.get("source_sha256")),
            dataset_sha256=actual_hash,
            rows=rows,
            fields=fields,
            raw_auxiliary_source_rows=raw_source_rows,
            raw_auxiliary_columns=raw_auxiliary_columns,
            measurement_kind=str(payload.get("measurement_kind")),
            timestamp_position=str(payload.get("timestamp_position")),
            site_timezone=payload.get("site_timezone"),
        )


def describe_evidence_dataset(dataset: EvidenceDataset) -> dict[str, Any]:
    return {
        "rows": len(dataset.rows),
        "fields": dataset.fields,
        "canonical_field_count": sum(item["origin"] == "canonical" for item in dataset.fields),
        "auxiliary_field_count": sum(item["origin"] == "auxiliary" for item in dataset.fields),
        "measurement_kind": dataset.measurement_kind,
        "timestamp_position": dataset.timestamp_position,
        "site_timezone": dataset.site_timezone,
        "relationship_coverage": (
            "univariate schema only; request contrast, support, boundary or loss evidence"
        ),
        "decision": None,
    }


def contrast_surface(
    rows: Sequence[dict[str, Any]],
    *,
    group_field: str,
    left_value: Any,
    right_value: Any,
    fields: Sequence[str],
    minimum_group_rows: int = 5,
    maximum_categories: int = 50,
) -> dict[str, Any]:
    if left_value == right_value:
        raise ValueError("Les deux valeurs du contraste doivent être différentes.")
    if not 2 <= minimum_group_rows <= 100_000:
        raise ValueError("minimum_group_rows doit être compris entre 2 et 100000.")
    if not 1 <= maximum_categories <= 200:
        raise ValueError("maximum_categories doit être compris entre 1 et 200.")
    left = [row for row in rows if row.get(group_field) == left_value]
    right = [row for row in rows if row.get(group_field) == right_value]
    if len(left) < minimum_group_rows or len(right) < minimum_group_rows:
        raise ValueError(
            f"Chaque groupe doit contenir au moins {minimum_group_rows} lignes."
        )
    evidence: list[dict[str, Any]] = []
    for field in fields:
        left_present = [row.get(field) for row in left if row.get(field) is not None]
        right_present = [row.get(field) for row in right if row.get(field) is not None]
        left_completeness = len(left_present) / len(left)
        right_completeness = len(right_present) / len(right)
        missingness_shift = right_completeness - left_completeness
        combined = left_present + right_present
        base = {
            "field": field,
            "left_present": len(left_present),
            "right_present": len(right_present),
            "left_completeness": _round(left_completeness, 6),
            "right_completeness": _round(right_completeness, 6),
            "completeness_difference_right_minus_left": _round(missingness_shift, 6),
        }
        if not combined:
            item = {**base, "kind": "unavailable", "evidence_strength": abs(missingness_shift)}
        elif all(_is_number(value) for value in combined):
            left_numeric = [float(value) for value in left_present]
            right_numeric = [float(value) for value in right_present]
            if left_numeric and right_numeric:
                difference = median(right_numeric) - median(left_numeric)
                scales = [scale for scale in (_mad(left_numeric), _mad(right_numeric)) if scale > EPSILON]
                robust_scale = median(scales) if scales else 0.0
                standardized = (
                    0.0 if abs(difference) <= EPSILON
                    else math.copysign(25.0, difference) if robust_scale <= EPSILON
                    else max(-25.0, min(25.0, difference / robust_scale))
                )
            else:
                difference = robust_scale = standardized = None
            strength = max(abs(missingness_shift), 0.0 if standardized is None else abs(standardized))
            item = {
                **base,
                "kind": "numeric",
                "left": _numeric_profile(left_numeric),
                "right": _numeric_profile(right_numeric),
                "median_difference_right_minus_left": _round(difference),
                "within_group_robust_scale": _round(robust_scale),
                "robust_standardized_difference": _round(standardized),
                "effect_is_clipped": bool(standardized is not None and abs(standardized) >= 25.0),
                "evidence_strength": _round(strength),
            }
        else:
            left_counts = Counter(str(value) for value in left_present)
            right_counts = Counter(str(value) for value in right_present)
            categories = sorted(set(left_counts) | set(right_counts))
            shifts = {
                category: _round(
                    right_counts[category] / max(len(right_present), 1)
                    - left_counts[category] / max(len(left_present), 1)
                )
                for category in categories[:maximum_categories]
            }
            all_shifts = [
                right_counts[category] / max(len(right_present), 1)
                - left_counts[category] / max(len(left_present), 1)
                for category in categories
            ]
            total_variation = 0.5 * sum(abs(value) for value in all_shifts)
            item = {
                **base,
                "kind": "categorical",
                "left": _categorical_profile(left_present, maximum_categories),
                "right": _categorical_profile(right_present, maximum_categories),
                "category_share_difference_right_minus_left": shifts,
                "category_differences_truncated": len(categories) > maximum_categories,
                "total_variation_distance": _round(total_variation),
                "evidence_strength": _round(max(abs(missingness_shift), total_variation)),
            }
        evidence.append(item)
    evidence.sort(key=lambda item: (-float(item["evidence_strength"]), item["field"]))
    return {
        "schema_version": "indicia-contrast-surface-v1",
        "status": "decision_neutral_evidence",
        "contrast": {
            "group_field": group_field,
            "left_value": left_value,
            "right_value": right_value,
            "left_rows": len(left),
            "right_rows": len(right),
            "excluded_rows": len(rows) - len(left) - len(right),
        },
        "field_evidence": evidence,
        "ranking_policy": "exploratory robust effect, categorical distance or missingness; no multiplicity correction",
        "claim_boundary": "A ranked co-movement is not an anomaly, a cause or an opportunity.",
        "decision": None,
    }


def relationship_loss_certificate(
    field_names: Sequence[str],
    *,
    summarized_relations: Iterable[tuple[str, str]] = (),
    omitted_examples_limit: int = 20,
) -> dict[str, Any]:
    fields = sorted(set(field_names))
    if not 0 <= omitted_examples_limit <= 100:
        raise ValueError("omitted_examples_limit doit être compris entre 0 et 100.")
    known = set(fields)
    covered: set[tuple[str, str]] = set()
    for left, right in summarized_relations:
        if left == right:
            raise ValueError("Une relation exige deux champs différents.")
        if left not in known or right not in known:
            raise ValueError(f"Relation résumée inconnue: {left}, {right}.")
        covered.add(tuple(sorted((left, right))))
    omitted_examples: list[list[str]] = []
    for pair in itertools.combinations(fields, 2):
        if pair not in covered and len(omitted_examples) < omitted_examples_limit:
            omitted_examples.append(list(pair))
    possible_pairs = len(fields) * (len(fields) - 1) // 2
    return {
        "schema_version": "indicia-relationship-loss-certificate-v1",
        "fields": fields,
        "univariate_profiles_do_not_cover_relations": True,
        "possible_pairwise_relations": possible_pairs,
        "summarized_pairwise_relations": [list(pair) for pair in sorted(covered)],
        "summarized_pairwise_relation_count": len(covered),
        "omitted_pairwise_relation_count": possible_pairs - len(covered),
        "omitted_pairwise_relation_examples": omitted_examples,
        "higher_order_relations_summarized": False,
        "temporal_order_relations_summarized": False,
        "missing_row_topology_summarized": False,
        "raw_retrieval_is_executable": True,
        "claim_boundary": "Disponibilité et profils marginaux ne prouvent pas la conservation des relations utiles.",
        "decision": None,
    }


def _dimension_match(target: dict[str, Any], reference: dict[str, Any], spec: dict[str, Any]) -> bool:
    field = str(spec["field"])
    left = target.get(field)
    right = reference.get(field)
    if left is None or right is None:
        return False
    kind = spec.get("kind", "categorical")
    if kind == "categorical":
        return left == right
    if kind != "numeric" or not _is_number(left) or not _is_number(right):
        return False
    tolerance = float(spec.get("tolerance", 0.0))
    if tolerance < 0:
        raise ValueError(f"Tolérance négative pour {field}.")
    difference = abs(float(left) - float(right))
    scale = spec.get("scale", "absolute")
    if scale == "absolute":
        return difference <= tolerance
    if scale == "relative":
        denominator = max(abs(float(left)), abs(float(right)), EPSILON)
        return difference / denominator <= tolerance
    raise ValueError(f"Échelle inconnue pour {field}: {scale}.")


def _support_view(counts: Sequence[int], selected: Sequence[int], minimum_controls: int) -> dict[str, Any]:
    return {
        "dimension_indices": list(selected),
        "coverage_with_minimum_controls": _round(sum(count >= minimum_controls for count in counts) / len(counts), 6),
        "matched_target_rows": sum(count >= minimum_controls for count in counts),
        "target_rows": len(counts),
        "minimum_controls": minimum_controls,
        "minimum_controls_observed": min(counts),
        "median_controls": _round(median(counts)),
        "maximum_controls_observed": max(counts),
    }


def support_atlas(
    reference_rows: Sequence[dict[str, Any]],
    target_rows: Sequence[dict[str, Any]],
    *,
    dimensions: Sequence[dict[str, Any]],
    minimum_controls: int = 5,
    forbidden_outcome_fields: Sequence[str] = (),
    maximum_pair_comparisons: int = 2_000_000,
) -> dict[str, Any]:
    if not reference_rows or not target_rows:
        raise ValueError("SupportAtlas exige des cohortes référence et cible non vides.")
    if not dimensions or len(dimensions) > 12:
        raise ValueError("SupportAtlas exige entre 1 et 12 dimensions.")
    if minimum_controls < 1:
        raise ValueError("minimum_controls doit être positif.")
    comparisons = len(reference_rows) * len(target_rows)
    if not 1 <= maximum_pair_comparisons <= 10_000_000:
        raise ValueError("maximum_pair_comparisons doit être compris entre 1 et 10000000.")
    if comparisons > maximum_pair_comparisons:
        raise ValueError(
            f"La requête exige {comparisons} paires, au-dessus de la borne {maximum_pair_comparisons}; réduisez explicitement les cohortes."
        )
    names = [str(item.get("field", "")) for item in dimensions]
    if any(not name for name in names) or len(set(names)) != len(names):
        raise ValueError("Les dimensions de support doivent être nommées et uniques.")
    leaked = sorted(set(forbidden_outcome_fields).intersection(names))
    if leaked:
        raise ValueError("Un outcome ne peut définir le support: " + ", ".join(leaked) + ".")
    count = len(dimensions)
    full_mask = (1 << count) - 1
    sequential_masks = [(1 << (index + 1)) - 1 for index in range(count)]
    isolated_masks = [1 << index for index in range(count)]
    leave_masks = [full_mask ^ (1 << index) for index in range(count)]
    masks = set(sequential_masks + isolated_masks + leave_masks + [full_mask])
    counts = {mask: [0] * len(target_rows) for mask in masks}
    for target_index, target in enumerate(target_rows):
        for reference in reference_rows:
            passed = 0
            for index, spec in enumerate(dimensions):
                if _dimension_match(target, reference, spec):
                    passed |= 1 << index
            for mask in masks:
                if passed & mask == mask:
                    counts[mask][target_index] += 1

    def named(mask: int, indices: list[int]) -> dict[str, Any]:
        view = _support_view(counts[mask], indices, minimum_controls)
        view.pop("dimension_indices")
        return {"dimensions_used": [names[index] for index in indices], **view}

    return {
        "schema_version": "indicia-support-atlas-v1",
        "status": "decision_neutral_evidence",
        "outcome_blind": True,
        "forbidden_outcome_fields": sorted(set(forbidden_outcome_fields)),
        "pair_comparisons": comparisons,
        "maximum_pair_comparisons": maximum_pair_comparisons,
        "pair_storage_policy": "streamed bitmasks; no pair cube retained",
        "dimension_specs": [dict(item) for item in dimensions],
        "full_support": named(full_mask, list(range(count))),
        "sequential_support": [named(sequential_masks[index], list(range(index + 1))) for index in range(count)],
        "isolated_support": {names[index]: named(isolated_masks[index], [index]) for index in range(count)},
        "leave_one_dimension_out": {
            names[index]: named(leave_masks[index], [other for other in range(count) if other != index])
            for index in range(count)
        },
        "order_warning": "La perte séquentielle dépend de l’ordre déclaré; inspecter les vues isolées et leave-one-out.",
        "claim_boundary": "Le support mesure la comparabilité observable, pas la causalité.",
        "decision": None,
    }


def _field_boundary_evidence(
    before: Sequence[dict[str, Any]], after: Sequence[dict[str, Any]], field: str
) -> dict[str, Any]:
    left = [row.get(field) for row in before if row.get(field) is not None]
    right = [row.get(field) for row in after if row.get(field) is not None]
    left_complete = len(left) / len(before)
    right_complete = len(right) / len(after)
    missingness_shift = right_complete - left_complete
    base = {
        "field": field,
        "before_completeness": _round(left_complete, 6),
        "after_completeness": _round(right_complete, 6),
        "completeness_difference_after_minus_before": _round(missingness_shift, 6),
    }
    combined = left + right
    if not combined:
        return {**base, "kind": "unavailable", "field_score": abs(missingness_shift) * 3.0}
    if all(_is_number(value) for value in combined):
        left_numeric = [float(value) for value in left]
        right_numeric = [float(value) for value in right]
        if left_numeric and right_numeric:
            difference = median(right_numeric) - median(left_numeric)
            scales = [scale for scale in (_mad(left_numeric), _mad(right_numeric)) if scale > EPSILON]
            scale = median(scales) if scales else 0.0
            standardized = (
                0.0 if abs(difference) <= EPSILON
                else math.copysign(25.0, difference) if scale <= EPSILON
                else max(-25.0, min(25.0, difference / scale))
            )
            global_center = median(left_numeric + right_numeric)
            global_loss = sum(abs(value - global_center) for value in left_numeric + right_numeric)
            within_loss = sum(abs(value - median(left_numeric)) for value in left_numeric)
            within_loss += sum(abs(value - median(right_numeric)) for value in right_numeric)
            gain = 0.0 if global_loss <= EPSILON else max(0.0, min(1.0, (global_loss - within_loss) / global_loss))
        else:
            difference = scale = standardized = None
            gain = 0.0
        score = max(abs(missingness_shift) * 3.0, 0.0 if standardized is None else abs(standardized) * gain)
        return {
            **base,
            "kind": "numeric",
            "median_difference_after_minus_before": _round(difference),
            "within_segment_robust_scale": _round(scale),
            "robust_standardized_difference": _round(standardized),
            "robust_partition_gain": _round(gain),
            "effect_is_clipped": bool(standardized is not None and abs(standardized) >= 25.0),
            "field_score": _round(score),
        }
    left_counts = Counter(str(value) for value in left)
    right_counts = Counter(str(value) for value in right)
    categories = set(left_counts) | set(right_counts)
    distance = 0.5 * sum(
        abs(left_counts[value] / max(len(left), 1) - right_counts[value] / max(len(right), 1))
        for value in categories
    )
    return {
        **base,
        "kind": "categorical",
        "total_variation_distance": _round(distance),
        "field_score": _round(max(abs(missingness_shift) * 3.0, distance * 3.0)),
    }


def boundary_ledger(
    rows: Sequence[dict[str, Any]],
    *,
    order_field: str,
    fields: Sequence[str],
    minimum_segment_rows: int = 20,
    candidate_stride: int = 1,
    comparison_window_rows: int | None = None,
    maximum_coarse_boundaries: int = 256,
    maximum_candidates: int = 10,
    maximum_field_evidence: int = 8,
) -> dict[str, Any]:
    if minimum_segment_rows < 5:
        raise ValueError("minimum_segment_rows doit être au moins 5.")
    if not 1 <= maximum_coarse_boundaries <= 2048 or not 1 <= maximum_candidates <= 50:
        raise ValueError("Budgets de frontières invalides.")
    if not 1 <= maximum_field_evidence <= 64:
        raise ValueError("maximum_field_evidence doit être compris entre 1 et 64.")
    if not 1 <= candidate_stride <= 100_000:
        raise ValueError("candidate_stride doit être positif et borné.")
    selected = list(dict.fromkeys(fields))
    if not selected or len(selected) > 64:
        raise ValueError("BoundaryLedger exige entre 1 et 64 champs.")
    if any(row.get(order_field) is None for row in rows):
        raise ValueError("Le champ d’ordre doit être complet.")
    try:
        ordered = sorted(rows, key=lambda row: row[order_field])
    except TypeError as exc:
        raise ValueError("Le champ d’ordre contient des types non comparables.") from exc
    if len(ordered) < minimum_segment_rows * 2 + 1:
        raise ValueError("Pas assez de lignes pour deux segments protégés.")
    window = minimum_segment_rows if comparison_window_rows is None else int(comparison_window_rows)
    if not 5 <= window <= len(ordered):
        raise ValueError("comparison_window_rows est invalide.")
    valid = list(range(minimum_segment_rows, len(ordered) - minimum_segment_rows + 1, candidate_stride))
    coarse_step = max(1, math.ceil(len(valid) / maximum_coarse_boundaries))
    coarse = valid[::coarse_step]
    # La fenêtre reste celle déclarée par l’agent. L’élargir avec une grille
    # grossière rendrait le coût et la sémantique dépendants de la taille totale.
    coarse_window = window

    def evaluate(index: int, evaluation_window: int) -> dict[str, Any]:
        before = ordered[max(0, index - evaluation_window):index]
        after = ordered[index:min(len(ordered), index + evaluation_window)]
        evidence = [_field_boundary_evidence(before, after, field) for field in selected]
        evidence.sort(key=lambda item: (-float(item["field_score"]), item["field"]))
        top = [float(item["field_score"]) for item in evidence[:3]]
        weights = (1.0, 0.5, 0.25)[:len(top)]
        aggregate = sum(score * weight for score, weight in zip(top, weights)) / sum(weights)
        return {
            "boundary_index": index,
            "boundary_value": ordered[index][order_field],
            "before_rows": len(before),
            "after_rows": len(after),
            "aggregate_exploratory_score": _round(aggregate),
            "field_evidence": evidence[:maximum_field_evidence],
        }

    evaluated = {index: evaluate(index, coarse_window) for index in coarse}
    if coarse_step > 1:
        ranked = sorted(evaluated.values(), key=lambda item: (-float(item["aggregate_exploratory_score"]), item["boundary_index"]))
        refinement_step = max(1, math.ceil(coarse_step / 16))
        valid_set = set(valid)
        for seed in ranked[:8]:
            center = int(seed["boundary_index"])
            for offset in range(-coarse_step, coarse_step + 1, refinement_step):
                candidate = center + offset * candidate_stride
                if candidate in valid_set and candidate not in evaluated:
                    evaluated[candidate] = evaluate(candidate, window)
    candidates = sorted(evaluated.values(), key=lambda item: (-float(item["aggregate_exploratory_score"]), item["boundary_index"]))
    suppression_radius = max(1, min(window, minimum_segment_rows) // 2)
    diverse_candidates: list[dict[str, Any]] = []
    for candidate in candidates:
        if all(
            abs(int(candidate["boundary_index"]) - int(selected["boundary_index"]))
            >= suppression_radius
            for selected in diverse_candidates
        ):
            diverse_candidates.append(candidate)
        if len(diverse_candidates) >= maximum_candidates:
            break
    return {
        "schema_version": "indicia-boundary-ledger-v1",
        "status": "decision_neutral_query_candidates",
        "order_field": order_field,
        "fields_considered": selected,
        "minimum_segment_rows": minimum_segment_rows,
        "comparison_window_rows": window,
        "candidate_boundaries_evaluated": len(candidates),
        "candidate_suppression_radius_rows": suppression_radius,
        "candidates": diverse_candidates,
        "mandatory_alternatives": [
            "seasonality",
            "operating-regime change",
            "data coverage or export change",
            "meter or schema change",
            "isolated outlier",
        ],
        "claim_boundary": "Une frontière classée est une question d’enquête, pas un changement anormal confirmé.",
        "decision": None,
    }
