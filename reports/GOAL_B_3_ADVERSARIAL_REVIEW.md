# Goal B.3 — revue adversariale

## Attaques testées

1. `DOCUMENT_EXTRACTED` avec `ART-DOES-NOT-EXIST` : rejeté.
2. Contrainte `EXPLICIT` avec source fictive : rejetée.
3. Finding Goal A réel mais statut modifié : rejeté.
4. Finding Goal A réel mais confiance modifiée : rejeté.
5. Calcul valide qui référence un input dont la source ultime est fictive :
   rejeté avant persistance.
6. Contrainte issue de plusieurs sources : acceptée seulement si chaque source
   existe dans le cas.

## Risques résiduels

- La résolution prouve l'existence et la traçabilité d'une source, pas que le
  contenu d'un document client est matériellement exact.
- Une contrainte peut rester une mauvaise interprétation de Codex; B.3 évite
  la source inventée mais ne remplace pas l'investigation ni la revue métier.
- Une hypothèse de scénario est traçable, pas transformée en fait client.

## Conclusion

La chaîne ne peut plus être cohérente seulement à l'intérieur de Goal B tout
en se terminant sur un identifiant fictif. Aucun hardcoding B-A→B-O, aucune
heuristique physique et aucun choix de recommandation n'ont été ajoutés.
