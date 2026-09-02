"""Attribution prudente à partir de signatures électriques et de preuves minimales.

Cette couche ne détecte pas elle-même les anomalies et ne diagnostique aucun
mécanisme physique. Elle reçoit une signature déjà établie, conserve toujours
``unknown`` comme hypothèse, compare des compatibilités (pas des probabilités)
et plafonne les revendications par des garde-fous déterministes.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum, IntEnum
from statistics import median
from typing import Any, Iterable, Sequence


UNKNOWN_ASSET_ID = "unknown"


class EvidenceLevel(IntEnum):
    DETECTABLE_CHANGE = 1
    REPRODUCIBLE_SIGNATURE = 2
    ANONYMOUS_COMPONENT = 3
    COMPATIBLE_ASSET_FAMILY = 4
    PROBABLE_ASSET = 5
    ROBUST_ATTRIBUTION = 6
    PHYSICAL_MECHANISM = 7
    PROGNOSIS = 8


class IdentifiabilityStatus(str, Enum):
    IDENTIFIABLE = "identifiable"
    PARTIALLY_IDENTIFIABLE = "partially_identifiable"
    MULTIPLE_COMPATIBLE = "multiple_compatible_candidates"
    OBSERVATIONALLY_EQUIVALENT = "observationally_equivalent"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    LIKELY_ABSENT_FROM_INVENTORY = "likely_absent_from_inventory"


@dataclass(frozen=True, slots=True)
class EquipmentRecord:
    """Entrée volontairement partielle d'un registre local d'équipements."""

    asset_id: str
    name: str | None = None
    family: str | None = None
    nominal_power_kw: float | None = None
    nominal_power_range_kw: tuple[float, float] | None = None
    usual_start_hour: float | None = None
    usual_stop_hour: float | None = None
    operating_days: tuple[int, ...] | None = None
    operation_mode: str | None = None
    production_dependency: str | None = None
    simultaneous_with: tuple[str, ...] = ()
    auxiliaries: tuple[str, ...] = ()
    installed_at: str | None = None
    maintenance_dates: tuple[str, ...] = ()
    known_shutdowns: tuple[tuple[str, str], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.asset_id.strip() or self.asset_id == UNKNOWN_ASSET_ID:
            raise ValueError("asset_id doit être renseigné et ne peut pas être 'unknown'.")
        if self.nominal_power_kw is not None and self.nominal_power_kw < 0:
            raise ValueError("La puissance nominale doit être positive ou inconnue.")
        if self.nominal_power_range_kw is not None:
            low, high = self.nominal_power_range_kw
            if low < 0 or high < low:
                raise ValueError("Plage de puissance invalide.")
        for hour in (self.usual_start_hour, self.usual_stop_hour):
            if hour is not None and not 0 <= hour < 24:
                raise ValueError("Une heure habituelle doit être comprise entre 0 et 24.")
        if self.operating_days is not None and any(day not in range(7) for day in self.operating_days):
            raise ValueError("Les jours de fonctionnement utilisent 0=lundi à 6=dimanche.")
        if self.operation_mode not in {None, "continuous", "intermittent", "batch"}:
            raise ValueError("Mode de fonctionnement inconnu.")
        if self.production_dependency not in {None, "dependent", "independent", "mixed"}:
            raise ValueError("Dépendance à la production inconnue.")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        # Les inconnues restent explicitement nulles; aucune imputation silencieuse.
        payload["unknown_fields"] = sorted(
            key for key, value in payload.items() if value is None
        )
        return payload


@dataclass(frozen=True, slots=True)
class ComponentOccurrence:
    """Une occurrence déjà extraite par une méthode de détection séparée."""

    start: datetime
    end: datetime
    amplitude_kw: float
    production_active: bool | None
    source_ref: str

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError("Une occurrence doit avoir une durée strictement positive.")
        if not math.isfinite(self.amplitude_kw) or self.amplitude_kw < 0:
            raise ValueError("Amplitude d'occurrence invalide.")
        if not self.source_ref.strip():
            raise ValueError("Chaque occurrence exige une référence de provenance.")


def _quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("Un quantile exige au moins une valeur.")
    position = (len(ordered) - 1) * probability
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    fraction = position - low
    return ordered[low] * (1 - fraction) + ordered[high] * fraction


def _mad(values: Sequence[float]) -> float:
    center = median(values)
    return 1.4826 * median(abs(value - center) for value in values)


def _circular_hour_center(values: Sequence[float]) -> tuple[float | None, float]:
    angles = [value / 24 * 2 * math.pi for value in values]
    sine = sum(math.sin(value) for value in angles) / len(angles)
    cosine = sum(math.cos(value) for value in angles) / len(angles)
    concentration = math.hypot(sine, cosine)
    if concentration < 0.2:
        return None, concentration
    angle = math.atan2(sine, cosine) % (2 * math.pi)
    return angle / (2 * math.pi) * 24, concentration


def build_anonymous_component(
    component_id: str,
    occurrences: Sequence[ComponentOccurrence],
    *,
    overlap_suspected: bool = False,
) -> AnonymousElectricalComponent:
    """Résume des occurrences sans prétendre les séparer en actifs physiques."""

    if not occurrences:
        raise ValueError("Au moins une occurrence est requise.")
    ordered = sorted(occurrences, key=lambda item: item.start)
    amplitudes = [item.amplitude_kw for item in ordered]
    durations = [(item.end - item.start).total_seconds() / 3600 for item in ordered]
    starts = [item.start.hour + item.start.minute / 60 + item.start.second / 3600 for item in ordered]
    stops = [item.end.hour + item.end.minute / 60 + item.end.second / 3600 for item in ordered]
    amplitude_center = float(median(amplitudes))
    relative_dispersion = _mad(amplitudes) / max(amplitude_center, 0.5)
    duration_dispersion = _mad(durations) / max(float(median(durations)), 0.25)
    stability = _clamp(1 - 0.7 * relative_dispersion - 0.3 * duration_dispersion)
    repeatability = 0.0 if len(ordered) == 1 else _clamp(stability * min(1.0, len(ordered) / 5))
    counts = Counter(item.start.date().isoformat() for item in ordered)
    start_center, start_concentration = _circular_hour_center(starts)
    stop_center, stop_concentration = _circular_hour_center(stops)
    production_states = [item.production_active for item in ordered if item.production_active is not None]
    if production_states and all(production_states):
        production_relation = "dependent"
    elif production_states and not any(production_states):
        production_relation = "independent"
    elif production_states:
        production_relation = "mixed"
    else:
        production_relation = None
    days = tuple(sorted({item.start.weekday() for item in ordered}))
    periodicity = (
        "observed_weekday_pattern"
        if days and set(days) <= set(range(5))
        else "observed_weekend_pattern"
        if days and set(days) <= {5, 6}
        else "observed_mixed_day_pattern"
    )
    return AnonymousElectricalComponent(
        component_id=component_id,
        amplitude_kw=round(amplitude_center, 6),
        amplitude_range_kw=(round(_quantile(amplitudes, 0.1), 6), round(_quantile(amplitudes, 0.9), 6)),
        typical_start_hour=None if start_center is None else round(start_center, 6),
        typical_stop_hour=None if stop_center is None else round(stop_center, 6),
        duration_hours=round(float(median(durations)), 6),
        frequency_per_day=round(sum(counts.values()) / len(counts), 6),
        periodicity=periodicity,
        operating_days=days,
        first_seen=ordered[0].start.isoformat(),
        last_seen=ordered[-1].end.isoformat(),
        stability=round(stability, 6),
        repeatability=round(repeatability, 6),
        occurrence_count=len(ordered),
        production_relation=production_relation,
        uncertainty={
            "occurrence_count": len(ordered),
            "amplitude_mad_kw": round(_mad(amplitudes), 6),
            "duration_mad_hours": round(_mad(durations), 6),
            "start_hour_circular_concentration": round(start_concentration, 6),
            "stop_hour_circular_concentration": round(stop_concentration, 6),
            "coverage_days_unknown": True,
        },
        source_refs=tuple(item.source_ref for item in ordered),
        separation_status=("overlap_ambiguous" if overlap_suspected else "aggregate_signature_not_submetering"),
    )


@dataclass(frozen=True, slots=True)
class AnonymousElectricalComponent:
    """Signature agrégée reproductible; ce n'est jamais un sous-compteur virtuel."""

    component_id: str
    amplitude_kw: float | None
    amplitude_range_kw: tuple[float, float] | None = None
    typical_start_hour: float | None = None
    typical_stop_hour: float | None = None
    duration_hours: float | None = None
    frequency_per_day: float | None = None
    periodicity: str | None = None
    operating_days: tuple[int, ...] | None = None
    seasonality: str | None = None
    first_seen: str | None = None
    last_seen: str | None = None
    stability: float | None = None
    repeatability: float | None = None
    occurrence_count: int = 0
    production_relation: str | None = None
    uncertainty: dict[str, float | str | None] = field(default_factory=dict)
    source_refs: tuple[str, ...] = ()
    separation_status: str = "aggregate_signature_not_submetering"

    def __post_init__(self) -> None:
        if not self.component_id.strip():
            raise ValueError("component_id est requis.")
        if self.amplitude_kw is not None and self.amplitude_kw < 0:
            raise ValueError("L'amplitude doit être positive ou inconnue.")
        if self.amplitude_range_kw is not None:
            low, high = self.amplitude_range_kw
            if low < 0 or high < low:
                raise ValueError("Plage d'amplitude invalide.")
        for value in (self.stability, self.repeatability):
            if value is not None and not 0 <= value <= 1:
                raise ValueError("Stabilité et répétabilité doivent être dans [0, 1].")
        if self.occurrence_count < 0:
            raise ValueError("occurrence_count ne peut pas être négatif.")
        if self.production_relation not in {None, "dependent", "independent", "mixed"}:
            raise ValueError("Relation de production inconnue.")
        if self.separation_status not in {
            "aggregate_signature_not_submetering",
            "overlap_ambiguous",
            "field_anchored",
        }:
            raise ValueError("Statut de séparation inconnu.")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["claim_boundary"] = (
            "signature électrique agrégée; ne démontre ni un actif unique, "
            "ni un mécanisme physique"
        )
        return payload


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    evidence_id: str
    kind: str
    direction: str
    candidate_ids: tuple[str, ...]
    reliability: float
    observed_at: str
    provenance: str
    statement: str
    observed_or_inferred: str = "observed"
    source_class: str = "operator_observation"
    anchor_verified: bool = False
    supersedes_evidence_id: str | None = None
    status: str = "active"
    synthetic: bool = False

    def __post_init__(self) -> None:
        if not self.evidence_id.strip() or not self.provenance.strip() or not self.statement.strip():
            raise ValueError("Une preuve exige identité, provenance et énoncé.")
        if self.direction not in {"supports", "contradicts"}:
            raise ValueError("direction doit valoir supports ou contradicts.")
        if not self.candidate_ids:
            raise ValueError("Une preuve doit viser au moins une hypothèse.")
        if not 0 <= self.reliability <= 1:
            raise ValueError("reliability doit être dans [0, 1].")
        if self.observed_or_inferred not in {"observed", "inferred"}:
            raise ValueError("observed_or_inferred invalide.")
        if self.status not in {"active", "superseded", "invalidated"}:
            raise ValueError("Statut de preuve inconnu.")


@dataclass(slots=True)
class EvidenceLedger:
    """Journal append-only; les corrections ajoutent une nouvelle entrée."""

    component_id: str
    items: list[EvidenceItem] = field(default_factory=list)
    assessment_history: list[dict[str, Any]] = field(default_factory=list)

    def append(self, item: EvidenceItem) -> None:
        if any(existing.evidence_id == item.evidence_id for existing in self.items):
            raise ValueError(f"evidence_id déjà présent: {item.evidence_id}.")
        if item.supersedes_evidence_id is not None and not any(
            existing.evidence_id == item.supersedes_evidence_id for existing in self.items
        ):
            raise ValueError("Une révision doit référencer une preuve antérieure du journal.")
        self.items.append(item)

    def active_items(self) -> list[EvidenceItem]:
        superseded = {
            item.supersedes_evidence_id
            for item in self.items
            if item.status == "active" and item.supersedes_evidence_id is not None
        }
        return [
            item for item in self.items
            if item.status == "active" and item.evidence_id not in superseded
        ]

    def record_assessment(self, assessment: "AttributionAssessment") -> None:
        self.assessment_history.append(assessment.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "indicia-minimal-evidence-ledger-v1",
            "component_id": self.component_id,
            "append_only": True,
            "items": [asdict(item) for item in self.items],
            "assessment_history": self.assessment_history,
        }


@dataclass(frozen=True, slots=True)
class CompatibilityCandidate:
    asset_id: str
    family: str | None
    compatibility_score: float
    feature_scores: dict[str, float]
    supporting_evidence: tuple[str, ...]
    contradicting_evidence: tuple[str, ...]
    eliminated: bool
    elimination_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AttributionAssessment:
    component_id: str
    method: str
    candidates: tuple[CompatibilityCandidate, ...]
    selected_asset_id: str | None
    identifiability: IdentifiabilityStatus
    evidence_level: EvidenceLevel
    confidence: str
    posterior_probability: None
    posterior_status: str
    more_same_type_data_will_help: bool | None
    observed: tuple[str, ...]
    inferred: tuple[str, ...]
    alternatives: tuple[str, ...]
    claim_limit: str
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "indicia-minimal-attribution-assessment-v1",
            "component_id": self.component_id,
            "method": self.method,
            "candidates": [asdict(candidate) for candidate in self.candidates],
            "selected_asset_id": self.selected_asset_id,
            "identifiability": self.identifiability.value,
            "evidence_level": {
                "code": self.evidence_level.name,
                "ordinal": int(self.evidence_level),
            },
            "confidence": self.confidence,
            "confidence_scope": "confidence_in_the_assessment_not_asset_probability",
            "posterior_probability": None,
            "posterior_status": self.posterior_status,
            "more_same_type_data_will_help": self.more_same_type_data_will_help,
            "observed": list(self.observed),
            "inferred": list(self.inferred),
            "alternatives": list(self.alternatives),
            "claim_limit": self.claim_limit,
            "limitations": list(self.limitations),
        }


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _range_similarity(value: float | None, low: float | None, high: float | None) -> float | None:
    if value is None or low is None or high is None:
        return None
    if low <= value <= high:
        return 1.0
    scale = max(high - low, value, 0.5)
    distance = min(abs(value - low), abs(value - high))
    return _clamp(1.0 - distance / scale)


def _power_similarity(component: AnonymousElectricalComponent, asset: EquipmentRecord) -> float | None:
    if component.amplitude_kw is None:
        return None
    if asset.nominal_power_range_kw is not None:
        return _range_similarity(component.amplitude_kw, *asset.nominal_power_range_kw)
    if asset.nominal_power_kw is None:
        return None
    denominator = max(component.amplitude_kw, asset.nominal_power_kw, 0.5)
    return _clamp(1.0 - abs(component.amplitude_kw - asset.nominal_power_kw) / denominator)


def _circular_hour_similarity(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    distance = abs(left - right) % 24
    distance = min(distance, 24 - distance)
    return _clamp(1.0 - distance / 6.0)


def _set_similarity(left: tuple[int, ...] | None, right: tuple[int, ...] | None) -> float | None:
    if left is None or right is None:
        return None
    union = set(left) | set(right)
    return 1.0 if not union else len(set(left) & set(right)) / len(union)


def _categorical_similarity(left: str | None, right: str | None) -> float | None:
    if left is None or right is None:
        return None
    if left == right:
        return 1.0
    if "mixed" in {left, right}:
        return 0.5
    return 0.0


def _duration_similarity(component: AnonymousElectricalComponent, asset: EquipmentRecord) -> float | None:
    if component.duration_hours is None or asset.usual_start_hour is None or asset.usual_stop_hour is None:
        return None
    expected = (asset.usual_stop_hour - asset.usual_start_hour) % 24
    if expected == 0 and asset.operation_mode == "continuous":
        expected = 24
    denominator = max(expected, component.duration_hours, 1.0)
    return _clamp(1.0 - abs(component.duration_hours - expected) / denominator)


FEATURE_WEIGHTS = {
    "amplitude": 2.0,
    "start_hour": 1.0,
    "stop_hour": 1.0,
    "duration": 0.75,
    "operating_days": 1.0,
    "production_relation": 1.0,
}


def _feature_scores(
    component: AnonymousElectricalComponent, asset: EquipmentRecord, method: str
) -> dict[str, float]:
    values: dict[str, float | None] = {
        "amplitude": _power_similarity(component, asset),
        "start_hour": _circular_hour_similarity(component.typical_start_hour, asset.usual_start_hour),
        "stop_hour": _circular_hour_similarity(component.typical_stop_hour, asset.usual_stop_hour),
        "duration": _duration_similarity(component, asset),
        "operating_days": _set_similarity(component.operating_days, asset.operating_days),
        "production_relation": _categorical_similarity(
            component.production_relation, asset.production_dependency
        ),
    }
    if method == "amplitude_only":
        values = {"amplitude": values["amplitude"]}
    present = {key: value for key, value in values.items() if value is not None}
    reliabilities = asset.metadata.get("field_reliability", {})
    if isinstance(reliabilities, dict):
        for key, value in list(present.items()):
            reliability = reliabilities.get(key, 1.0)
            if isinstance(reliability, (int, float)) and not isinstance(reliability, bool):
                # Une donnée déclarée peu fiable devient neutre (0,5); elle ne
                # produit ni concordance ni contradiction forte.
                present[key] = 0.5 + (value - 0.5) * _clamp(float(reliability))
    return present


def _weighted_score(scores: dict[str, float]) -> float:
    if not scores:
        return 0.5  # absence d'information, jamais compatibilité positive forte
    total_weight = sum(FEATURE_WEIGHTS.get(key, 1.0) for key in scores)
    return sum(value * FEATURE_WEIGHTS.get(key, 1.0) for key, value in scores.items()) / total_weight


def _observable_fingerprint(
    asset: EquipmentRecord,
    component: AnonymousElectricalComponent,
    method: str,
) -> tuple[Any, ...]:
    """Projection limitée aux variables réellement observées dans la signature."""

    values: list[Any] = []
    if component.amplitude_kw is not None:
        values.append(asset.nominal_power_range_kw or asset.nominal_power_kw)
    if method == "amplitude_only":
        return tuple(values)
    if component.typical_start_hour is not None:
        values.append(asset.usual_start_hour)
    if component.typical_stop_hour is not None:
        values.append(asset.usual_stop_hour)
    if component.operating_days is not None:
        values.append(asset.operating_days)
    if component.production_relation is not None:
        values.append(asset.production_dependency)
    return tuple(values)


def _direct_anchor_ids(items: Sequence[EvidenceItem]) -> set[str]:
    return {
        candidate
        for item in items
        if item.status == "active"
        and item.direction == "supports"
        and item.observed_or_inferred == "observed"
        and item.source_class in {"direct_observation", "temporary_measurement", "preregistered_field_test"}
        and item.anchor_verified
        and item.reliability >= 0.8
        for candidate in item.candidate_ids
    }


def assess_attribution(
    component: AnonymousElectricalComponent,
    inventory: Sequence[EquipmentRecord],
    *,
    evidence: Sequence[EvidenceItem] = (),
    method: str = "contextual",
    compatibility_threshold: float = 0.62,
    selection_threshold: float = 0.72,
    separation_margin: float = 0.14,
) -> AttributionAssessment:
    """Compare sans transformer le score en probabilité ni forcer une attribution."""

    if method not in {"amplitude_only", "contextual", "evidence_aware", "guarded_evidence"}:
        raise ValueError("Méthode de compatibilité inconnue.")
    asset_ids = [asset.asset_id for asset in inventory]
    if len(set(asset_ids)) != len(asset_ids):
        raise ValueError("Le registre contient des asset_id dupliqués.")
    unknown_targets = {
        candidate for item in evidence for candidate in item.candidate_ids
        if candidate not in set(asset_ids) | {UNKNOWN_ASSET_ID}
    }
    if unknown_targets:
        raise ValueError("Une preuve cible un actif absent du registre: " + ", ".join(sorted(unknown_targets)))

    active_evidence = [item for item in evidence if item.status == "active"]
    candidates: list[CompatibilityCandidate] = []
    for asset in inventory:
        feature_scores = _feature_scores(component, asset, method)
        score = _weighted_score(feature_scores)
        # Une incompatibilité de puissance très forte doit empêcher que cinq
        # concordances calendaires compensent artificiellement le désaccord.
        # L'evidence-aware peut ensuite lever ce plafond avec une ancre directe.
        if feature_scores.get("amplitude", 1.0) < 0.25:
            score = min(score, 0.45)
        supporting: list[str] = []
        contradicting: list[str] = []
        if method in {"evidence_aware", "guarded_evidence"}:
            for item in active_evidence:
                if asset.asset_id not in item.candidate_ids:
                    continue
                if item.direction == "supports":
                    score += 0.22 * item.reliability
                    supporting.append(item.evidence_id)
                else:
                    score -= 0.35 * item.reliability
                    contradicting.append(item.evidence_id)
        score = _clamp(score)
        strongest_support = max(
            (
                item.reliability for item in active_evidence
                if asset.asset_id in item.candidate_ids and item.direction == "supports"
            ),
            default=0.0,
        )
        hard_contradictions = [
            item for item in active_evidence
            if asset.asset_id in item.candidate_ids
            and item.direction == "contradicts"
            and item.reliability >= 0.9
            and item.observed_or_inferred == "observed"
            and item.anchor_verified
            and strongest_support < item.reliability - 0.1
        ]
        candidates.append(
            CompatibilityCandidate(
                asset_id=asset.asset_id,
                family=asset.family,
                compatibility_score=round(score, 6),
                feature_scores={key: round(value, 6) for key, value in feature_scores.items()},
                supporting_evidence=tuple(supporting),
                contradicting_evidence=tuple(contradicting),
                eliminated=bool(hard_contradictions) or score < 0.25,
                elimination_reasons=tuple(
                    [f"high_reliability_contradiction:{item.evidence_id}" for item in hard_contradictions]
                    + (["incompatible_observed_features"] if score < 0.25 else [])
                ),
            )
        )

    # L'hypothèse unknown est structurelle. Son score exprime seulement le manque
    # de couverture du registre, jamais une probabilité postérieure.
    best_known = max((item.compatibility_score for item in candidates if not item.eliminated), default=0.0)
    unknown_support = [
        item.evidence_id for item in active_evidence
        if UNKNOWN_ASSET_ID in item.candidate_ids and item.direction == "supports"
    ]
    unknown_contradiction = [
        item.evidence_id for item in active_evidence
        if UNKNOWN_ASSET_ID in item.candidate_ids and item.direction == "contradicts"
    ]
    unknown_score = (
        0.55
        if best_known < compatibility_threshold
        else max(0.35, 0.8 - best_known)
    )
    if method in {"evidence_aware", "guarded_evidence"}:
        unknown_score += sum(
            (0.22 if item.direction == "supports" else -0.22) * item.reliability
            for item in active_evidence if UNKNOWN_ASSET_ID in item.candidate_ids
        )
    candidates.append(
        CompatibilityCandidate(
            asset_id=UNKNOWN_ASSET_ID,
            family=None,
            compatibility_score=round(_clamp(unknown_score), 6),
            feature_scores={},
            supporting_evidence=tuple(unknown_support),
            contradicting_evidence=tuple(unknown_contradiction),
            eliminated=False,
            elimination_reasons=(),
        )
    )
    verified_supported_ids = {
        candidate
        for item in active_evidence
        if item.direction == "supports" and item.anchor_verified and item.reliability >= 0.8
        for candidate in item.candidate_ids
    }
    unique_verified_id = (
        next(iter(verified_supported_ids)) if len(verified_supported_ids) == 1 else None
    )
    candidates.sort(
        key=lambda item: (
            0 if item.asset_id == unique_verified_id else 1,
            -item.compatibility_score,
            item.asset_id,
        )
    )

    viable_known = [
        item for item in candidates
        if item.asset_id != UNKNOWN_ASSET_ID and not item.eliminated
        and (
            item.compatibility_score >= compatibility_threshold
            or item.asset_id == unique_verified_id
        )
    ]
    known_lookup = {asset.asset_id: asset for asset in inventory}
    enough_signature = (
        component.occurrence_count >= 3
        and (component.repeatability or 0.0) >= 0.55
        and (component.stability or 0.0) >= 0.45
    )
    top = viable_known[0] if viable_known else None
    second = viable_known[1] if len(viable_known) > 1 else None
    equivalent = False
    if top and second:
        discriminating_support = any(
            item.direction == "supports"
            and top.asset_id in item.candidate_ids
            and second.asset_id not in item.candidate_ids
            and item.reliability >= 0.8
            and item.anchor_verified
            for item in active_evidence
        )
        equivalent = (
            _observable_fingerprint(known_lookup[top.asset_id], component, method)
            == _observable_fingerprint(known_lookup[second.asset_id], component, method)
            and not discriminating_support
        )

    if not enough_signature:
        identifiability = IdentifiabilityStatus.INSUFFICIENT_EVIDENCE
        more_same = True
    elif not viable_known or best_known < compatibility_threshold:
        identifiability = IdentifiabilityStatus.LIKELY_ABSENT_FROM_INVENTORY
        more_same = False
    elif equivalent:
        identifiability = IdentifiabilityStatus.OBSERVATIONALLY_EQUIVALENT
        more_same = False
    elif (
        second
        and top.compatibility_score - second.compatibility_score < separation_margin
        and not any(
            item.direction == "supports"
            and top.asset_id in item.candidate_ids
            and second.asset_id not in item.candidate_ids
            and item.reliability >= 0.8
            and item.anchor_verified
            for item in active_evidence
        )
    ):
        identifiability = IdentifiabilityStatus.MULTIPLE_COMPATIBLE
        more_same = None
    elif top and (
        top.compatibility_score >= selection_threshold
        or top.asset_id == unique_verified_id
    ):
        identifiability = IdentifiabilityStatus.IDENTIFIABLE
        more_same = False
    else:
        identifiability = IdentifiabilityStatus.PARTIALLY_IDENTIFIABLE
        more_same = None

    selected: str | None = None
    reproducible = component.occurrence_count >= 2 and (component.repeatability or 0.0) >= 0.4
    level = (
        EvidenceLevel.ANONYMOUS_COMPONENT
        if enough_signature
        else EvidenceLevel.REPRODUCIBLE_SIGNATURE
        if reproducible
        else EvidenceLevel.DETECTABLE_CHANGE
    )
    if enough_signature and viable_known:
        families = {item.family for item in viable_known if item.family}
        if len(families) == 1:
            level = max(level, EvidenceLevel.COMPATIBLE_ASSET_FAMILY)
    if identifiability == IdentifiabilityStatus.IDENTIFIABLE and top is not None:
        selected = top.asset_id
        level = max(level, EvidenceLevel.PROBABLE_ASSET)

    anchors = _direct_anchor_ids(active_evidence)
    if component.separation_status == "overlap_ambiguous" and not anchors:
        # Une somme de charges simultanées peut imiter un actif plus puissant.
        # Sans ancre indépendante, nommer cet actif serait du faux sous-comptage.
        selected = None
        identifiability = IdentifiabilityStatus.INSUFFICIENT_EVIDENCE
        more_same = False
        level = min(level, EvidenceLevel.ANONYMOUS_COMPONENT)
    high_contradiction = any(
        item.direction == "contradicts" and item.reliability >= 0.8
        and top is not None and top.asset_id in item.candidate_ids
        for item in active_evidence
    )
    if (
        selected is not None
        and selected in anchors
        and component.occurrence_count >= 5
        and (component.repeatability or 0.0) >= 0.7
        and not high_contradiction
    ):
        level = EvidenceLevel.ROBUST_ATTRIBUTION

    if method == "guarded_evidence" and selected is not None:
        has_verified_discriminator = any(
            item.direction == "supports"
            and selected in item.candidate_ids
            and item.reliability >= 0.8
            and item.anchor_verified
            for item in active_evidence
        )
        if not has_verified_discriminator:
            selected = None
            identifiability = IdentifiabilityStatus.PARTIALLY_IDENTIFIABLE
            more_same = None
            level = min(level, EvidenceLevel.COMPATIBLE_ASSET_FAMILY)

    # Une couche d'attribution ne peut jamais promouvoir mécanisme ou pronostic.
    level = EvidenceLevel(min(int(level), int(EvidenceLevel.ROBUST_ATTRIBUTION)))
    score_gap = (
        top.compatibility_score - second.compatibility_score
        if top is not None and second is not None else (top.compatibility_score if top else 0.0)
    )
    conflict_count = sum(
        bool(item.supporting_evidence and item.contradicting_evidence)
        for item in candidates
    )
    if identifiability in {
        IdentifiabilityStatus.INSUFFICIENT_EVIDENCE,
        IdentifiabilityStatus.OBSERVATIONALLY_EQUIVALENT,
        IdentifiabilityStatus.LIKELY_ABSENT_FROM_INVENTORY,
    }:
        confidence = "low" if not enough_signature else "moderate"
    elif high_contradiction or conflict_count:
        confidence = "low"
    elif level >= EvidenceLevel.ROBUST_ATTRIBUTION and score_gap >= separation_margin:
        confidence = "high"
    elif score_gap >= separation_margin:
        confidence = "moderate"
    else:
        confidence = "low"

    alternatives = tuple(
        item.asset_id for item in candidates
        if item.asset_id != selected and not item.eliminated
        and (item.compatibility_score >= compatibility_threshold or item.asset_id == UNKNOWN_ASSET_ID)
    )
    claim_limit = {
        EvidenceLevel.REPRODUCIBLE_SIGNATURE: "signature_reproductible_sans_composant_unique",
        EvidenceLevel.ANONYMOUS_COMPONENT: "composant_electrique_anonyme_sans_actif",
        EvidenceLevel.COMPATIBLE_ASSET_FAMILY: "famille_compatible_sans_actif_unique",
        EvidenceLevel.PROBABLE_ASSET: "actif_probablement_responsable_sans_mecanisme",
        EvidenceLevel.ROBUST_ATTRIBUTION: "attribution_robuste_sans_mecanisme_ni_pronostic",
    }.get(level, "changement_detectable_uniquement")
    inferred = []
    if selected:
        inferred.append(f"{selected} est l'actif connu le plus compatible")
    elif viable_known:
        inferred.append("plusieurs actifs connus restent compatibles")
    else:
        inferred.append("aucun actif connu n'est suffisamment compatible")

    return AttributionAssessment(
        component_id=component.component_id,
        method=method,
        candidates=tuple(candidates),
        selected_asset_id=selected,
        identifiability=identifiability,
        evidence_level=level,
        confidence=confidence,
        posterior_probability=None,
        posterior_status="not_computed_compatibility_scores_are_not_probabilities",
        more_same_type_data_will_help=more_same,
        observed=(
            f"signature {component.component_id} observée {component.occurrence_count} fois",
            f"amplitude agrégée: {component.amplitude_kw!r} kW",
        ),
        inferred=tuple(inferred),
        alternatives=alternatives,
        claim_limit=claim_limit,
        limitations=(
            "Le compteur agrégé ne constitue pas un sous-comptage d'actif.",
            "La compatibilité ne démontre ni causalité, ni mécanisme physique, ni pronostic.",
        ),
    )


@dataclass(frozen=True, slots=True)
class MicroQuestion:
    question_id: str
    prompt: str
    answer_by_candidate: dict[str, str]
    effort: float
    availability: float
    reliability: float
    source_class: str = "operator_question"

    def __post_init__(self) -> None:
        if not self.question_id or not self.prompt or len(set(self.answer_by_candidate.values())) < 1:
            raise ValueError("Question incomplète.")
        if self.effort <= 0:
            raise ValueError("L'effort doit être strictement positif.")
        if not 0 <= self.availability <= 1 or not 0 <= self.reliability <= 1:
            raise ValueError("Disponibilité et fiabilité doivent être dans [0, 1].")


def _entropy(probabilities: Iterable[float]) -> float:
    return -sum(value * math.log2(value) for value in probabilities if value > 0)


def rank_micro_questions(
    candidate_ids: Sequence[str],
    questions: Sequence[MicroQuestion],
    *,
    strategy: str = "reliability_adjusted_voi",
) -> list[dict[str, Any]]:
    """Classe des partitions d'hypothèses sans inventer de posterior d'actif."""

    hypotheses = tuple(dict.fromkeys(candidate_ids))
    if len(hypotheses) < 2:
        return []
    if strategy not in {"information_gain", "expected_elimination", "reliability_adjusted_voi"}:
        raise ValueError("Stratégie de micro-question inconnue.")
    prior_entropy = math.log2(len(hypotheses))
    ranked: list[dict[str, Any]] = []
    for question in questions:
        missing = set(hypotheses) - set(question.answer_by_candidate)
        if missing:
            raise ValueError(
                f"{question.question_id}: réponses manquantes pour " + ", ".join(sorted(missing))
            )
        groups: dict[str, list[str]] = {}
        for candidate in hypotheses:
            groups.setdefault(question.answer_by_candidate[candidate], []).append(candidate)
        expected_entropy = sum(
            len(group) / len(hypotheses) * math.log2(len(group))
            for group in groups.values()
        )
        information_gain = prior_entropy - expected_entropy
        expected_remaining = sum(len(group) ** 2 for group in groups.values()) / len(hypotheses)
        expected_elimination = len(hypotheses) - expected_remaining
        if strategy == "information_gain":
            utility = information_gain
        elif strategy == "expected_elimination":
            utility = expected_elimination
        else:
            utility = information_gain * question.availability * question.reliability / question.effort
        ranked.append(
            {
                "question_id": question.question_id,
                "prompt": question.prompt,
                "strategy": strategy,
                "prior_entropy_bits": round(prior_entropy, 6),
                "expected_entropy_bits": round(expected_entropy, 6),
                "information_gain_bits": round(information_gain, 6),
                "expected_hypothesis_elimination": round(expected_elimination, 6),
                "effort": question.effort,
                "availability": question.availability,
                "reliability": question.reliability,
                "utility": round(utility, 6),
                "discriminating": len(groups) > 1,
                "answer_groups": {answer: sorted(group) for answer, group in sorted(groups.items())},
            }
        )
    return sorted(ranked, key=lambda item: (-item["utility"], item["question_id"]))


@dataclass(frozen=True, slots=True)
class NaturalOperationalEvent:
    event_id: str
    event_type: str
    start: str
    end: str | None
    affected_asset_ids: tuple[str, ...]
    concurrent_event_ids: tuple[str, ...]
    signature_change: str
    reliability: float
    provenance: str
    synthetic: bool = False
    confounder_audit_status: str = "unknown"

    def __post_init__(self) -> None:
        if not self.event_id.strip() or not self.event_type.strip() or not self.provenance.strip():
            raise ValueError("Un événement naturel exige identité, type et provenance.")
        if not 0 <= self.reliability <= 1:
            raise ValueError("La fiabilité de l'événement doit être dans [0, 1].")
        if self.confounder_audit_status not in {"unknown", "verified_scope", "known_confounded"}:
            raise ValueError("Statut d'audit des co-événements inconnu.")


def evidence_from_natural_event(
    event: NaturalOperationalEvent,
    *,
    component_id: str,
    candidate_ids: Sequence[str],
) -> tuple[list[EvidenceItem], dict[str, Any]]:
    """N'accorde une preuve discriminante qu'en l'absence de co-événement pertinent."""

    affected = set(event.affected_asset_ids) & set(candidate_ids)
    discriminating = (
        len(affected) == 1
        and not event.concurrent_event_ids
        and event.reliability >= 0.6
        and event.confounder_audit_status == "verified_scope"
    )
    items: list[EvidenceItem] = []
    if discriminating:
        asset_id = next(iter(affected))
        direction = "supports" if event.signature_change in {"appeared", "disappeared", "changed_as_expected"} else "contradicts"
        items.append(
            EvidenceItem(
                evidence_id=f"{event.event_id}:{component_id}",
                kind="natural_operational_event",
                direction=direction,
                candidate_ids=(asset_id,),
                reliability=event.reliability,
                observed_at=event.start,
                provenance=event.provenance,
                statement=(
                    f"La signature {component_id} a {event.signature_change} pendant "
                    f"l'événement {event.event_id} visant {asset_id}."
                ),
                observed_or_inferred="observed",
                source_class="natural_event",
                anchor_verified=True,
                synthetic=event.synthetic,
            )
        )
    return items, {
        "event_id": event.event_id,
        "discriminating": discriminating,
        "reason": (
            "single_affected_candidate_without_concurrent_event"
            if discriminating
            else "confounded_or_non_discriminating_event"
        ),
        "claim_effect": "compatibility_evidence_only",
    }


def plan_temporary_measurement(
    assessment: AttributionAssessment,
    *,
    ranked_questions: Sequence[dict[str, Any]],
    component: AnonymousElectricalComponent,
    decision: str,
) -> dict[str, Any] | None:
    """Propose une ancre minimale seulement si une question simple ne suffit pas."""

    unresolved = assessment.identifiability in {
        IdentifiabilityStatus.MULTIPLE_COMPATIBLE,
        IdentifiabilityStatus.OBSERVATIONALLY_EQUIVALENT,
        IdentifiabilityStatus.PARTIALLY_IDENTIFIABLE,
        IdentifiabilityStatus.INSUFFICIENT_EVIDENCE,
    }
    if not unresolved:
        return None
    best_question = ranked_questions[0] if ranked_questions else None
    if best_question and best_question["utility"] >= 0.25 and best_question["discriminating"]:
        return None
    occurrences = max(component.occurrence_count, 1)
    repeatability = component.repeatability or 0.0
    required_cycles = 3 if repeatability >= 0.7 else 5
    approximate_days = None
    if component.frequency_per_day and component.frequency_per_day > 0:
        approximate_days = math.ceil(required_cycles / component.frequency_per_day)
    return {
        "status": "last_resort_targeted_measurement",
        "component_id": component.component_id,
        "ambiguity": list(assessment.alternatives),
        "instrument": "temporary_current_clamp_or_mobile_submeter",
        "why_needed": (
            "Les données agrégées et les micro-questions disponibles ne séparent pas "
            "les hypothèses restantes."
        ),
        "minimum_repeated_cycles": required_cycles,
        "approximate_duration_days": approximate_days,
        "duration_basis": (
            "heuristic_repeated_cycle_requirement"
            if approximate_days is not None else "not_justifiable_from_observed_frequency"
        ),
        "short_measurement_may_be_insufficient": occurrences < required_cycles or repeatability < 0.7,
        "decision_enabled": decision,
        "safety_boundary": "Installation par une personne habilitée; aucune instruction de câblage fournie.",
    }


def signature_distance(
    reference: AnonymousElectricalComponent,
    candidate: AnonymousElectricalComponent,
) -> dict[str, Any]:
    """Distance explicable sur les dimensions communes uniquement."""

    dimensions: dict[str, float] = {}
    if reference.amplitude_kw is not None and candidate.amplitude_kw is not None:
        denominator = max(reference.amplitude_kw, candidate.amplitude_kw, 0.5)
        dimensions["amplitude"] = abs(reference.amplitude_kw - candidate.amplitude_kw) / denominator
    for key, left, right in (
        ("start_hour", reference.typical_start_hour, candidate.typical_start_hour),
        ("stop_hour", reference.typical_stop_hour, candidate.typical_stop_hour),
    ):
        similarity = _circular_hour_similarity(left, right)
        if similarity is not None:
            dimensions[key] = 1.0 - similarity
    days_similarity = _set_similarity(reference.operating_days, candidate.operating_days)
    if days_similarity is not None:
        dimensions["operating_days"] = 1.0 - days_similarity
    relation = _categorical_similarity(reference.production_relation, candidate.production_relation)
    if relation is not None:
        dimensions["production_relation"] = 1.0 - relation
    distance = sum(dimensions.values()) / len(dimensions) if dimensions else None
    return {
        "distance": None if distance is None else round(distance, 6),
        "dimensions": {key: round(value, 6) for key, value in dimensions.items()},
        "common_dimensions": len(dimensions),
    }


def reuse_historical_anchor(
    reference: AnonymousElectricalComponent,
    candidate: AnonymousElectricalComponent,
    *,
    anchored_asset_id: str,
    maximum_distance: float = 0.1,
    maximum_dimension_distance: float = 0.25,
) -> dict[str, Any]:
    comparison = signature_distance(reference, candidate)
    distance = comparison["distance"]
    enough = (
        comparison["common_dimensions"] >= 3
        and candidate.occurrence_count >= 3
        and (candidate.repeatability or 0.0) >= 0.65
    )
    worst_dimension = max(comparison["dimensions"].values(), default=None)
    accepted = bool(
        enough
        and distance is not None
        and distance <= maximum_distance
        and worst_dimension is not None
        and worst_dimension <= maximum_dimension_distance
    )
    return {
        "schema_version": "indicia-historical-anchor-reuse-v1",
        "reference_component_id": reference.component_id,
        "candidate_component_id": candidate.component_id,
        "anchored_asset_id": anchored_asset_id if accepted else None,
        "status": "compatible_historical_signature" if accepted else "reuse_refused",
        "comparison": comparison,
        "maximum_distance": maximum_distance,
        "maximum_dimension_distance": maximum_dimension_distance,
        "worst_dimension_distance": worst_dimension,
        "reason": (
            "stable_signature_with_sufficient_common_dimensions"
            if accepted
            else "signature_drift_single_dimension_or_insufficient_support"
        ),
        "claim_limit": (
            "historical_compatibility_not_new_physical_validation"
            if accepted else "no_historical_attribution"
        ),
    }


def build_evidence_finding(
    component: AnonymousElectricalComponent,
    assessment: AttributionAssessment,
    *,
    next_information: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Projection machine-readable avec plafond non modifiable par rédaction."""

    if assessment.component_id != component.component_id:
        raise ValueError("Le finding et l'assessment ne visent pas le même composant.")
    return {
        "schema_version": "indicia-minimal-evidence-finding-v1",
        "finding_id": f"ATTR-{component.component_id}",
        "component": component.to_dict(),
        "observed": list(assessment.observed),
        "inferred": list(assessment.inferred),
        "supporting_evidence": sorted(
            evidence_id for candidate in assessment.candidates
            for evidence_id in candidate.supporting_evidence
        ),
        "contradicting_evidence": sorted(
            evidence_id for candidate in assessment.candidates
            for evidence_id in candidate.contradicting_evidence
        ),
        "alternatives": list(assessment.alternatives),
        "identifiability": assessment.identifiability.value,
        "confidence": assessment.confidence,
        "evidence_level": {
            "code": assessment.evidence_level.name,
            "ordinal": int(assessment.evidence_level),
        },
        "selected_asset_id": assessment.selected_asset_id,
        "posterior_probability": None,
        "claim_limit": assessment.claim_limit,
        "next_information": next_information,
        "forbidden_claims": ["physical_mechanism", "failure_prognosis", "recoverable_saving"],
    }


def validate_evidence_finding(
    finding: dict[str, Any], assessment: AttributionAssessment
) -> None:
    """Refuse toute promotion rédactionnelle au-delà du calcul verrouillé."""

    expected_level = {
        "code": assessment.evidence_level.name,
        "ordinal": int(assessment.evidence_level),
    }
    if finding.get("evidence_level") != expected_level:
        raise ValueError("Le niveau de preuve du finding dépasse ou altère l'assessment calculé.")
    if finding.get("selected_asset_id") != assessment.selected_asset_id:
        raise ValueError("L'actif du finding ne correspond pas à l'assessment calculé.")
    if finding.get("claim_limit") != assessment.claim_limit:
        raise ValueError("Le plafond de revendication a été modifié.")
    if finding.get("posterior_probability") is not None:
        raise ValueError("Aucune probabilité postérieure calibrée n'est disponible.")
    forbidden = set(finding.get("forbidden_claims", []))
    required_forbidden = {"physical_mechanism", "failure_prognosis", "recoverable_saving"}
    if not required_forbidden <= forbidden:
        raise ValueError("Les limites de claim obligatoires ont été retirées.")
    if assessment.evidence_level > EvidenceLevel.ROBUST_ATTRIBUTION:
        raise ValueError("La couche MinimalEvidenceAttribution ne peut dépasser l'attribution robuste.")
