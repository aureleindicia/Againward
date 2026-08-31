# Architecture INDICIA après Stage 4

## Chemin nominal

```text
source CSV/XLSX locale
  -> io.load_data
       -> noyau physique typé et normalisé
       -> ContextualFieldStore colonnaire, brut + typé, lié à source_row
  -> analyses et candidats legacy conservés
  -> EvidenceDataset immuable et hashé
       -> Evidence Card v2 compacte + certificat de perte relationnelle
       <-> boucle Codex bornée
            - hypothèses concurrentes
            - requêtes typées
            - surfaces de contraste/support/frontière
            - récupération de lignes par handle
            - contre-explications
            - constat lié aux preuves ou abstention
  -> review adversariale
  -> revue humaine
  -> rapport client simple inchangé
```

Le chemin nominal de `prepare_investigation()` est désormais `preferred`. Le pipeline
déterministe continue à produire les mêmes indicateurs et signaux candidats, mais l’interface
probatoire interactive est l’interface autoritative pour les nouveaux tests choisis par Codex.

## Noyau canonique et magasin contextuel

Le noyau `Reading` garde la responsabilité exclusive des grandeurs physiques : timestamp,
énergie en kWh, puissance en kW, durée, production, état de production, température, tarif et
horloge locale. Les règles d’unité et les refus d’ambiguïté ne changent pas.

`ContextualFieldStore` conserve toute colonne non sélectionnée comme canonique. Sa sérialisation
`schema_version: 2` est colonnaire :

- `fields` décrit clé interne stable, nom original, nom normalisé, index source, type prudent,
  complétude, cardinalité et troncatures ;
- `source_rows` relie chaque valeur à sa ligne source CSV/XLSX ;
- `raw_columns` conserve la représentation source JSON-compatible lorsque possible ;
- `typed_columns` contient la coercition prudente utilisable par les outils ;
- `maximum_fields` et `maximum_value_characters` rendent les limites explicites.

Les types sont `boolean`, `number`, `datetime`, `string`, `mixed` ou `empty`. Un identifiant
numérique à zéros initiaux reste textuel. Une colonne partiellement numérique devient `mixed` au
lieu de transformer silencieusement ses erreurs. Les noms vides et dupliqués restent distincts
grâce à l’index source (`aux_0004_...`). Une largeur supérieure à la limite est refusée, jamais
silencieusement abandonnée. Une valeur trop longue est tronquée avec compteur et avertissement.

Le format v2 peut relire le format transitoire v1 par compatibilité. Les valeurs auxiliaires
participent à la signature de doublon : deux lignes égales physiquement mais différentes sur le
contexte sont conflictuelles. Le mode de rollback désactive cette conservation pour reproduire la
sémantique legacy.

## Snapshot probatoire

`EvidenceDataset` est un snapshot local JSON hashé. Il contient :

- lignes physiques normalisées et contexte auxiliaire typé ;
- champs absents omis par ligne mais décrits dans le catalogue global ;
- contexte auxiliaire brut sous forme colonnaire ;
- `source_row`, hash de source et hash du dataset ;
- nature de mesure, convention de timestamp et fuseau du site.

Le hash est recalculé à la lecture. Une modification du contenu invalide le snapshot. Les valeurs
physiques brutes pré-normalisation ne sont pas conservées dans ce snapshot : la provenance pointe
vers la source, tandis que les calculs utilisent uniquement la normalisation auditée.

## Evidence Plane

Les quatre primitives de production sont génériques et portent toujours `decision: null`.

### Contrast Surface

Mesure les différences robustes, distances catégorielles et changements de missingness entre deux
groupes choisis par l’agent. L’inversion gauche/droite inverse correctement les effets signés. Le
classement est exploratoire, sans test causal ni correction de multiplicité.

### Support Atlas

Compte les contrôles disponibles pour chaque cible sous les dimensions et tolérances déclarées par
l’agent. Il expose support complet, séquentiel, isolé et leave-one-out. Les champs outcome interdits
sont rejetés. Les paires sont parcourues en flux et jamais matérialisées en cube ; tout travail
quadratique au-delà du budget est refusé.

### Boundary Ledger

Classe des frontières candidates dans un ordre déclaré et décrit quels champs ou taux de présence
changent autour de chacune. Une grille grossière bornée garde toujours la fenêtre déclarée, est
raffinée localement puis applique une suppression de voisins afin de conserver plusieurs changements
distincts. Le résultat impose
les alternatives saison, régime, export, compteur et outlier ; une frontière n’est jamais qualifiée
d’anormale par le code.

### Relationship Loss Certificate

Compte les relations pairwise possibles, résumées et omises sans matérialiser la matrice complète.
Il déclare explicitement que profils marginaux, relations d’ordre, relations d’ordre supérieur et
topologie des lignes manquantes ne sont pas équivalents. Un handle rend la récupération exécutable.

## Protocole exécutable

`EvidenceQuery` n’accepte que six opérations :

- `describe_schema` ;
- `raw_slice` ;
- `contrast_surface` ;
- `relationship_loss_certificate` ;
- `support_atlas` ;
- `boundary_ledger`.

Les clés et arguments inconnus sont refusés. Aucun code, expression, import ou callback n’est
accepté. Une `EvidenceQuerySession` persistée impose par défaut : 16 tentatives, 600 lignes
retournées, 400 000 octets de contexte, 2 000 000 comparaisons de paires et 80 handles. Une
requête sémantiquement identique est rejetée même avec un nouvel identifiant. Les rejets sont
conservés dans la session et la trace du dossier.

Chaque réponse fournit hashes de source/dataset/requête/réponse, usage de ressources, certificat
de perte, provenance et handles. Un handle contient un sélecteur typé (`all`, `equals`,
`source_rows`, `ordered_window`), pas du code. `raw_slice` est la seule opération qui renvoie des
lignes et reste limitée à 200 par appel.

La commande opérationnelle est :

```sh
python query_evidence.py DOSSIER REQUEST.json
```

Les réponses immuables sont écrites dans `evidence_queries/`; l’état de session et `trace.json`
sont mis à jour atomiquement.

## Boucle agentique et constats

`investigation_state.json` décrit désormais une boucle : hypothèses concurrentes, demande bornée,
inspection des handles, test de la meilleure alternative, nouvelle requête seulement si elle peut
changer la décision, constat ou abstention, puis review.

Python choisit seulement les appartenances de groupes demandées, calcule les statistiques, applique
les bornes et vérifie les références. Codex choisit le sens des champs, les contrastes, les
tolérances, les alternatives, la suite des appels, le niveau de confiance et la conclusion.

`agent_findings.json` peut conclure `CONFIRME`, `A_CONSERVER_AVEC_RESERVES`,
`INSUFFISAMMENT_ETAYE`, `REJETE` ou `ABSTAIN`. Une conclusion conservée exige query IDs, handles
existants et alternative testée. Une abstention exige le manque de preuve précis. Le verrou de
livraison valide ce registre lorsqu’un dossier Evidence Plane est présent, sans juger la pertinence
métier à la place de la review.

## Legacy et migration

`energy_mvp.signals.detect_candidate_events` reste inchangé dans son rôle : preuve/candidat/fallback.
Ses événements sont inclus dans l’Evidence Card sous `candidate evidence only`. H01, H02 et H05
restent des régressions de recherche, composables par requêtes génériques si Codex en a besoin ; ils
ne deviennent pas des règles produit. La candidate H03 rejetée reste une preuve négative gelée.

Trois modes coexistent :

- `preferred` : Evidence Plane nominal + artefacts legacy ;
- `shadow` : même chemin, plus comparaison structurelle legacy/nouveau ;
- `legacy` : pas de snapshot ni session, conservation auxiliaire désactivée, artefacts historiques
  inchangés.

Le rapport Markdown/HTML client n’a reçu aucune dépendance vers l’Evidence Plane. La complexité
reste interne ; les affirmations client passent toujours par investigation, review et revue humaine.

## Confidentialité et ressources

Tout reste local. Le snapshot peut contenir des colonnes opérationnelles sensibles : il demeure
dans le workspace ignoré par Git et ne doit pas être envoyé automatiquement. Le moteur n’ajoute ni
télémétrie, ni upload, ni dépendance réseau.

Le stockage contextuel colonnaire a été retenu après mesure. Le probe local réel couvre 10 000,
100 000 et 500 000 lignes. À 500 000 lignes, le snapshot atteint environ 142 Mo et le pic Python
tracé environ 862 Mo. Grâce à la fenêtre fixe, le Boundary Ledger borné prend environ 0,52 s, mais
l’ingestion prend environ 121 s et la construction/sérialisation du snapshot 56 s. Ce palier est
donc supporté comme capacité batch bornée, pas recommandé comme préparation interactive fréquente
sur Android. Les résultats exacts sont dans `PERFORMANCE_PROBE.json`.
