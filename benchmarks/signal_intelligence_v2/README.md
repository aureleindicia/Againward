# Signal Intelligence Benchmark V2

Infrastructure privée et reproductible pour tester la désagrégation électrique,
l'intelligence énergétique et le pronostic maintenance à partir d'un point de mesure
central.

Les cas et runs sont exclus de Git. La spécification complète se trouve dans
`docs/SIGNAL_INTELLIGENCE_BENCHMARK_V2.md`; les résultats publics minimaux dans
`reports/SIGNAL_INTELLIGENCE_BENCHMARK_V2_RESULTS.json`.

```bash
python run_signal_intelligence_benchmark.py --help
```

Contrôles disponibles : baseline nulle pré-enregistrée et baseline déterministe
`detection-and-motif-v2`. Cette dernière ne revendique ni attribution d'actif, ni
mécanisme physique, ni pronostic.
