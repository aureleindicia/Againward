# Architecture de livraison client

Goal C consomme, sans les réécrire, `structured_findings.json` Goal A et
`economic_decision_state.json` Goal B.

```text
Narratif sélectionné par Codex + états Goal A/B
→ CLIENT_REPORT_MODEL.json validé
→ graphiques explicitement demandés
→ PDF client
```

Codex choisit les sujets, le récit et « pourquoi cela compte ». Python résout
les références, conserve les chiffres Goal B, bloque les renforcements de
claims, produit les graphiques à partir des données normalisées et rend le PDF.
Le renderer ne diagnostique ni ne recommande.

Le rapport cible trois à huit pages. Les artefacts internes conservent les
références, alors que le PDF n'expose ni IDs, chemins locaux, hashes ni traces.

Exécution locale :

```sh
python deliver_client_report.py /chemin/vers/cas narratif_codex.json
```
