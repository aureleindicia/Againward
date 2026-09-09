# Architecture de livraison client

Le chemin nominal est décrit dans [FINAL_CLIENT_MISSION.md](FINAL_CLIENT_MISSION.md) et
[REPORT_DESIGN_SYSTEM.md](REPORT_DESIGN_SYSTEM.md).

```text
Findings + Operational Economics + Value Map
→ narratif sourcé Codex → CLIENT_REPORT_MODEL validé
→ REPORT_DESIGN_MODEL composé par Codex
→ rendu local reproductible → inspection de chaque page
→ approbation humaine liée aux claims → gate → client_report.pdf livrable
```

Le modèle client existant reste l’autorité de présentation des claims. Le plan de design ne porte
que références et composition ; il ne crée aucun chiffre, finding ou décision. Le renderer
historique `_render_pages` est réservé à la compatibilité des fixtures : il ne compose plus les
missions réelles. Le sérialiseur PDF et les validations sont réutilisés.

```sh
python deliver_client_report.py /chemin/vers/cas narratif_codex.json --design REPORT_DESIGN_MODEL.json
```

L’agent choisit un document adapté, généralement quelques pages utiles, sans remplissage. Une
modification substantielle exige une nouvelle approbation humaine ; une modification esthétique
conserve le hash sémantique mais exige une nouvelle inspection visuelle. Aucun rapport synthétique
ne vaut preuve client.
