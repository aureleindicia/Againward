"""Génère un dépôt client synthétique, sans vérité cachée ni diagnostic attendu."""
from __future__ import annotations

import argparse
from pathlib import Path

from openpyxl import Workbook


def generate(target: str | Path) -> Path:
    root = Path(target)
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"Le dossier existe déjà et n'est pas vide: {root}")
    root.mkdir(parents=True, exist_ok=True)

    workbook = Workbook()
    meta = workbook.active
    meta.title = "Notes"
    meta.append(["Export reçu le", "2026-08-30"])
    meta.append(["Remarque", "Les unités sont indiquées dans le nom de la feuille."])
    energy = workbook.create_sheet("Compteur atelier kWh")
    energy.append([])
    energy.append(["Export du portail fournisseur"])
    energy.append([])
    energy.append(["Date", "Conso", "Production"])
    for row in [
        ("01/06/2026 05:00", "3,0", "0"),
        ("01/06/2026 05:30", "3,1", "0"),
        ("01/06/2026 06:00", "1,2", "0"),
        ("01/06/2026 06:30", "1,3", "5"),
        ("01/06/2026 07:00", "1,4", "6"),
        ("01/06/2026 07:00", "1,4", "6"),
        ("01/06/2026 08:00", "1,5", "7"),
        ("TOTAL", "11,5", "18"),
    ]:
        energy.append(row)
    workbook.save(root / "export_compteur_atelier.xlsx")

    (root / "production_approx.csv").write_text(
        "date,production\n2026-06-01,18\n2026-06-02,20\n",
        encoding="utf-8",
    )
    (root / "compteur_secondaire_sans_unite.csv").write_text(
        "timestamp,Energy\n2026-06-01 05:00,42\n2026-06-01 05:30,41\n2026-06-01 06:00,15\n",
        encoding="utf-8",
    )
    (root / "planning_ouverture.txt").write_text(
        "Ouverture habituelle : lundi-vendredi, préparation à partir de 06:30.\n",
        encoding="utf-8",
    )
    (root / "note_tarif.txt").write_text(
        "Facture électricité : prix moyen indicatif 0,19 EUR/kWh.\n",
        encoding="utf-8",
    )
    (root / "logo_photo.txt").write_text("fichier marketing sans donnée opérationnelle\n", encoding="utf-8")
    return root


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", nargs="?", default="examples/goal_a_messy_client_drop")
    args = parser.parse_args()
    print(generate(args.target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
