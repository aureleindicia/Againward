"""Original synthetic document variations; no scorer truth goes to the model."""
from pathlib import Path

from benchmarking.document_renderers import pdf

from .native_gate import make_sources as thin_sources

SCENARIOS = ('thin', 'decorative', 'competing_tariffs', 'two_pdl')


def make_sources(source: Path, scenario: str) -> None:
    if scenario not in SCENARIOS:
        raise ValueError('Unknown source scenario')
    thin_sources(source)
    if scenario == 'decorative':
        pdf(source / 'annexe.pdf', [
            'NOTE LOGISTIQUE INTERNE',
            'Reunion du service achats le mardi dans la salle principale.',
            'Prevoir les dossiers papier et confirmer la presence des participants.',
        ])
    elif scenario == 'competing_tariffs':
        pdf(source / 'conditions.pdf', [
            'Conditions commerciales acceptees ELECTRICITE B2B FRANCE',
            'Contrat: OFFRE-2026-B ; Fournisseur: FOURNISSEUR-DEMO ; Devise: EUR',
            'PDL / PRM: 01234567890123',
            'Effet: 2026-01-01 inclus au 2027-01-01 exclu',
            'Fourniture consommation: prix fixe 0.145 EUR/kWh HT',
            'Ce prix exclut abonnement, reseau et taxes.',
            'Montant de chaque ligne arrondi au centime EUR le plus proche; demi au dessus.',
        ])
    elif scenario == 'two_pdl':
        pdf(source / 'facture.pdf', [
            'Facture ELECTRICITE B2B FRANCE - EXTRAIT DE LIGNE HT',
            'Fournisseur: FOURNISSEUR-DEMO ; Facture: EB-2026-09-001 ; Devise: EUR',
            'Sites factures : PDL / PRM 01234567890123 et PDL / PRM 98765432109876',
            'Periode: 2026-09-01 inclus au 2026-10-01 exclu',
            'Consommation globale des deux sites: 1375 kWh ; montant HT: 192.08 EUR',
            'La repartition entre les deux sites ne figure pas dans cet extrait.',
            "Cet extrait ne contient pas le total TTC, les taxes ni l'abonnement.",
        ])
