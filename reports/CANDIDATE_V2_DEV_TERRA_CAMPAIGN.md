# CANDIDATE_V2_DEV_TERRA — manifeste de campagne

## Statut

Préparée pour exécution. Cette campagne remplace, sans l'écraser, la campagne
Sol interrompue et non scorée.

## Version évaluée

- tag Candidate V2 : `expert-benchmark-candidate-v2`
- commit analytique : `7acc43fc00007af87c459fd60cc89d972515c59a`
- empreinte moteur Candidate V2 (42 fichiers) :
  `dd2211e2ea0ad26b49c6ec8399dc362282b8be633ae9a3a244908c8bdac53cdd`
- oracle : `semantic-v3-blind-fallback`
- protocole : Physical Expertise Benchmark, sans lecture manuelle de ground
  truth ni de payload follow-up privé

## Participants

- campagne : `CANDIDATE_V2_DEV_TERRA`
- modèle de chaque participant : `gpt-5.6-terra`
- effort de raisonnement de chaque participant : `high`
- sessions : 17 nouvelles sessions, une par cas, sans reprise de session Sol

Les cas valides prévus sont : `b42`, `c08`, `d31`, `e55`, `f63`, `g14`, `h27`,
`j90`, `k22`, `l48`, `m76`, `n05`, `p39`, `q81`, `r24`, `s67` et `t12`.

`a17` est exclu des agrégats et de l'exécution avec le statut
`EXCLUDED_PENDING_CASE_VALIDATION`.

## Séparation de la campagne Sol

Les trois runs scellés Sol restent intacts à
`/data/data/com.termux/files/usr/tmp/energy-dev-candidate-v2-7acc43f`. Ils sont
une archive/sanity-check non scorée uniquement. Aucun artefact, conclusion,
coût ou résultat Sol ne sera injecté dans les 17 runs Terra, leurs agrégats ou
leurs rapports.

## Intégrité

Aucune modification analytique, de prompt participant, de modèle, d'effort de
raisonnement, d'oracle ou de protocole n'est autorisée entre les 17 cas Terra.
Les éventuelles revues aveugles sont des sessions distinctes et ne voient que
la demande, un identifiant oracle neutre et une description abstraite, jamais
un payload privé ni une ground truth.
