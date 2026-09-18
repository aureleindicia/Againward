"""Legacy Energy adapter and re-exports of the shared Evidence Plane."""
from againward.evidence.plane import (boundary_ledger, contrast_surface,
    describe_evidence_dataset, relationship_loss_certificate, support_atlas, stable_hash)
from againward.evidence.dataset import LEGACY_SCHEMA as EVIDENCE_DATASET_SCHEMA
from againward.domains.energy.evidence import EnergyEvidenceDataset as EvidenceDataset
