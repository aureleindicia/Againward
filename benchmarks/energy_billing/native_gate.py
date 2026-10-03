"""Early actual-PDF reader gate; synthetic sources, no hidden answer in input."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import time
from typing import Any

from againward.core.artifact_store import write_json
from againward.documents.sources import inventory_sources
from againward.domains.energy_billing.provider import CodexTransport, ModelBoundary
from againward.domains.energy_billing.reader import read_source, reading_summary, replay_reading
from benchmarking.document_renderers import pdf


def run(model: str, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    source = output / "input"
    source.mkdir()
    pdf(source / "facture.pdf", [
        "Facture ELECTRICITE B2B FRANCE - EXTRAIT DE LIGNE HT",
        "Fournisseur: FOURNISSEUR-DEMO ; Facture: EB-2026-09-001 ; Devise: EUR",
        "PDL / PRM: 01234567890123",
        "Periode: 2026-09-01 inclus au 2026-10-01 exclu",
        "Consommation: 1375 kWh ; montant facture HT de cette ligne: 192.08 EUR",
        "Cet extrait ne contient pas le total TTC, les taxes ni l'abonnement.",
    ])
    pdf(source / "contrat.pdf", [
        "Conditions commerciales acceptees ELECTRICITE B2B FRANCE",
        "Contrat: OFFRE-2026-FIXE ; Fournisseur: FOURNISSEUR-DEMO ; Devise: EUR",
        "PDL / PRM: 01234567890123",
        "Effet: 2026-01-01 inclus au 2027-01-01 exclu",
        "Fourniture consommation: prix fixe 0.120 EUR/kWh HT",
        "Ce prix exclut abonnement, reseau et taxes.",
        "Montant de chaque ligne arrondi au centime EUR le plus proche; demi au dessus.",
    ])
    root = output / "snapshot"
    batch = inventory_sources(source, root)
    transport = CodexTransport(model, evaluation_root=output / "raw")
    boundary = ModelBoundary(transport)
    reads: list[dict[str, Any]] = []
    started = time.perf_counter()
    for document in batch.documents:
        for role in ("PRIMARY", "INDEPENDENT"):
            receipt = read_source(batch, document.source_id, root, model=model, boundary=boundary, role=role)
            reading = replay_reading(batch, root, receipt)
            reads.append({"source_id": document.source_id, "role": role, "receipt_sha256": receipt,
                          "reading": reading_summary(reading)})
            write_json(output / "progress.json", {"readings": reads, "calls": transport.calls})
            print(f"{role}: {len(reading.observations)} bound, {len(reading.quarantine)} quarantined", flush=True)
    result = {"schema_version": "energy-billing-native-gate-v1",
        "engine_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "engine_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()),
        "model": model, "batch": batch.to_dict(), "readings": reads,
        "provider_calls": transport.calls, "diagnostics": boundary.diagnostics,
        "wall_seconds": time.perf_counter() - started,
        "calculation_reached": False, "report_reached": False,
        "gate_a": all(len(row["reading"]["observations"]) > 1 for row in reads),
        "qualification": "Actual synthetic native PDFs; source binding only, not factual/authority approval or E2E."}
    write_json(output / "result.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = run(args.model, args.output)
    raise SystemExit(0 if result["gate_a"] else 1)


if __name__ == "__main__":
    main()
