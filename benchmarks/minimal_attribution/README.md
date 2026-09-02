# Benchmark MinimalEvidenceAttribution

Ce benchmark évalue la progression d'une signature agrégée vers une attribution prudente.
Il ne teste ni détection brute, ni mécanisme physique, ni pronostic.

## Reproduction complète

```bash
python run_minimal_attribution_benchmark.py \
  --output workspace/minimal_attribution_benchmark_final \
  --seeds 101 202 303 404 505 9101 9203 9307 9409 9511 \
  --report-json reports/MINIMAL_EVIDENCE_ATTRIBUTION_RND_RESULTS.json \
  --report-md reports/MINIMAL_EVIDENCE_ATTRIBUTION_RND_REPORT.md \
  --examples-json examples/minimal_attribution_decisions.json
```

Les cas, vérités, réponses et locks sont générés dans `workspace/` et ignorés par Git.
Seuls le protocole, les tests, les schémas et les résultats consolidés reproductibles sont
versionnés.

## Protocole aveugle

1. Générer `public_cases.json` et `private_truth.json` séparés.
2. Produire toutes les réponses en ne passant que les cas publics au moteur.
3. Écrire un lock SHA-256 par couple méthode/stratégie.
4. Charger ensuite la vérité et scorer les réponses verrouillées.

Ce protocole évite la lecture directe de la vérité au moment de répondre. Le générateur est
néanmoins public et les scénarios sont synthétiques : il s'agit d'un benchmark de régression
et de falsification, pas d'une validation indépendante sur site.

## Scénarios obligatoires

Les vingt familles sont : actif simple, actifs distincts, presque identiques, équivalents,
actif absent, faux candidat plausible, information fausse, information contradictoire,
dérive, simultanéité, signature faible, événement discriminant/non discriminant,
question utile/inutile, mesure résolutive/trop courte, historique insuffisant, données
bruitées/manquantes et conclusion `unknown`.

Chaque famille est instanciée sur dix seeds. Les cinq premières sont DEVELOPMENT et les cinq
dernières HOLDOUT. Le HOLDOUT change le bruit, pas la structure du scénario.

## Métriques

- précision parmi les actifs nommés ;
- taux de fausses attributions et couverture ;
- refus correct et abstention sur cas attribuables ;
- perte asymétrique (`false attribution=5`, abstention inutile `=1`) ;
- rang réciproque, top-1 et top-3 ;
- exactitude du statut d'identifiabilité ;
- choix de micro-question, information gain, réduction d'incertitude et interactions ;
- décision par niveau de confiance, sans interprétation probabiliste ;
- événement naturel, mesure temporaire et réutilisation historique.

Un test de corruption du registre utilise une pénalité encore plus sévère (`10` contre `1`).
Les taux de corruption simulés ne représentent pas leur fréquence réelle.

## Artefacts versionnés

- [résultats JSON](../../reports/MINIMAL_EVIDENCE_ATTRIBUTION_RND_RESULTS.json) ;
- [rapport R&D](../../reports/MINIMAL_EVIDENCE_ATTRIBUTION_RND_REPORT.md) ;
- [architecture](../../docs/MINIMAL_EVIDENCE_ATTRIBUTION.md) ;
- [exemples synthétiques](../../examples/minimal_attribution_decisions.json).

