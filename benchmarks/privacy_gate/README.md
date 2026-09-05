# Benchmark privacy gate

Ce probe synthétique mesure le post-check PASS sur 10 000, 100 000 et 500 000 lignes. Il vérifie la
couverture, le scan résiduel, le hash, la promotion et la suppression temporaire ; il ne mesure pas
la qualité sémantique de Codex et ne contient aucune donnée client.

```sh
python benchmarks/privacy_gate/benchmark.py
```

`RESULTS.json` est réécrit avec l'environnement et les mesures réelles. Le RSS est celui du
processus entier et donc un majorant dépendant de l'ordre des tailles.
