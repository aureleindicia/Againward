# France electricity billing — initial official-source research

Retrieved/reviewed 2026-10-03. Research informs the envelope; it is not yet an
encoded tax-rule registry. URLs and applicability notes below are insufficient
for a deterministic historical rule: byte snapshot/hash, applicable legal
version and tests are mandatory before activation.

| Authority | Finding relevant to V1 | Boundary |
|---|---|---|
| [Energy-info PRO: supplier change](https://www.energie-info.fr/pro/fiche_pratique/je-souhaite-changer-de-fournisseur-delectricite-ou-de-gaz-naturel/) | PDL/PRM is available on electricity invoices; contract conditions include price evolution and commitment. | Invoice identifiers are normally accessible; signed offers/amendments still need client discovery. |
| [Energy-info: comparing offers](https://www.energie-info.fr/fiche_pratique/comment-comparer-les-offres-delectricite-et-de-gaz-naturel/) | Market prices follow contracts, including fixed or indexed offers. | Public tariff tables cannot replace a customer's market contract. |
| [CRE network access](https://www.cre.fr/electricite/reseaux-delectricite/tarif-dacces.html) | Network charge structure includes differentiated periods and network parameters. Page updated 2026-07-29. | Fixed supply-price verification does not independently validate TURPE. |
| [CRE final TURPE 7 HTA-BT decision, 2025-03-13](https://www.cre.fr/fileadmin/Documents/Deliberations/2025/250313_2025-78_Post-CSE_TURPE_7_HTA-BT.pdf) | Final decision is preferable to February's project/consultation. | Historical network rules require exact version and connection/option facts. |
| [DGFiP 2026 electricity excise notice](https://www.impots.gouv.fr/sites/default/files/formulaires/2040-tic-sd/2026/2040-tic-sd_5322.pdf) | Distinguishes dates, fiscal categories, power and economic/non-economic activity. Reports 2026-02–07 rates separately from 2026-08–2027-01. | Company name or generic PME label alone does not prove fiscal category; minor/reduced/exempt regimes need attestation and separate rules. |
| [BOFiP dated 2025-12-24 excise rescript](https://bofip.impots.gouv.fr/bofip/14903-PGP.html/identifiant%3DBOI-RES-EAT-000240-20251224) | Transitional 2026 reasoning and ZNI component. | It precedes later 2026 law/rate changes; cannot be the sole October rate authority. |
| [BOFiP dated 2026-08-26 VAT transition](https://bofip.impots.gouv.fr/bofip/14705-PGP.html/identifiant%3DBOI-RES-TVA-000209-20260826) | Replacement of reduced VAT applies to subscriptions for periods beginning from 2025-08-01. | Invoice issue date alone is not the relevant period test. Exact transition/proration treatment must be read before implementing. |
| [Bercy VAT summary, 2025-12-11](https://www.economie.gouv.fr/particuliers/impots-et-fiscalite/gerer-mes-autres-impots-et-taxes/tva-quels-sont-les-taux-de-votre-quotidien) | Notes removal of reduced energy-subscription VAT from 2025-08-01. | Summary corroboration, not sufficient detailed historical billing rule. |

Counterexample found: DGCCRF's `prix-tarifs-et-suivi` and opening-market FAQ
dated 2023 still describe older subscription VAT and local-tax arrangements.
Official origin alone does not establish current or period-specific validity.
Never scrape a current summary and apply it to all historical invoices.

Commercial data-access hypothesis: invoices likely provide supplier/PDL/period,
but complete contract, amendments, actual index history and issued credits must
be measured during pilot discovery. No real-client preparation-time or pricing
willingness measurements exist yet. Initial partial HT supply-line verification
keeps tax/network authority separate and explicitly limits the conclusion.
