"""Reproduit ce lot éditorial gelé avec les outils de prospection existants.

Aucune recherche, notation ou recommandation nouvelle n'est faite par ce script.
Les appréciations et accroches ont été rédigées dans research_judgments.json.
"""
from __future__ import annotations
import csv
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from prospecting.prepare import prepare, _normalise
from prospecting.score import score, calculate_score, WEIGHTS

DATE = "2026-09-10"
BANDS = {
    1: "P1 — preuves async opérationnelles convergentes et fit métier",
    2: "P2 — fit métier et échanges écrits plausibles ; valider le transfert",
    3: "P3 — enrichir avant proposition : async faible ou périmètre métier incertain",
}
COMMON_UNKNOWN = [
    "Export compteur, fréquence, unité, couverture et périmètre : UNKNOWN",
    "Facture, tarif, budget de pilote, gisement récupérable : UNKNOWN",
    "Accord du sponsor pour collaboration principalement écrite : UNKNOWN",
]


def dump(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def band(p):
    # Filtre de qualification explicite : l'async ne rachète pas un fit métier incertain.
    if p["utility_status"] != "STRONG_CANDIDATE" or p.get("commercial_hold"):
        return 3
    return 1 if p["ratings"][7] >= 4 else 2 if p["ratings"][7] >= 3 else 3


def dimension_rationales(p):
    return [
        "Potentiel fondé sur le procédé, pas une facture : " + p["site"],
        "Hypothèse à tester, aucun écart constaté : " + p["utility_hypothesis"],
        "Mesures énergie UNKNOWN. " + ("Traces opérationnelles explicitement documentées ; aucun export énergie garanti." if p["ratings"][2] == 3 else "Organisation numérique ou procédé seulement ; aucun export énergie garanti."),
        "Matérialité supposée à partir du périmètre : " + p["size"] + ". Coût et gain inconnus ; pas de ROI établi.",
        "Fonction ciblable : " + p["target_role"] + ". Limites : " + p["limitations"],
        "Inconnue : la note 2 est une appréciation prudente, pas preuve d'absence d'expertise." if p["ratings"][5] == 2 else "Efforts énergie/environnement visibles ; ne pas présumer absence d'expertise interne.",
        "Fit technique conditionnel : " + p["utility_hypothesis"] + " Statut : " + p["utility_status"],
        p["async_signal"] + " Transfert à un fournisseur externe : " + p["async_transfer_confidence"] + "; accord non obtenu.",
    ]


def main():
    research = json.loads((HERE / "research_judgments.json").read_text(encoding="utf-8"))
    items = research["prospects"]
    if len(items) != 50 or len({p["name"] for p in items}) != 50:
        raise ValueError("Le lot doit contenir 50 entreprises distinctes")
    raw, assessments, inventory = [], [], []
    for p in items:
        if "France" in p["country"] or p["paid_pilot_qualification"] != "NOT_QUALIFIED":
            raise ValueError("Pays ou claim de qualification invalide")
        sources = []
        for i, source in enumerate(p["sources"], 1):
            s = dict(source, source_id=f'{p["prospect_id"]}-S{i}')
            sources.append(s)
            inventory.append(dict(s, prospect_id=p["prospect_id"], company=p["name"]))
        ids = [s["source_id"] for s in sources]
        if not sources or not p["personalization"]["hook_source_indices"]:
            raise ValueError("Source manquante")
        hooks = [ids[i] for i in p["personalization"]["hook_source_indices"]]
        p["source_ids"] = ids
        p["personalization"]["hook_source_refs"] = hooks
        raw.append({
            "prospect_id": p["prospect_id"], "entity_key": _normalise(p["name"]),
            "name": p["name"], "sector": p["sector"], "discovered_at": DATE,
            "prequalification_status": "CANDIDATE" if p["utility_status"] == "STRONG_CANDIDATE" else "UNCERTAIN",
            "country": p["country"],
            "facts": [{"field": f"public_observation_{i}", "value": s["claim"], "source_id": s["source_id"], "observed_at": DATE, "confidence": s["confidence"]} for i,s in enumerate(sources,1)],
            "inferences": [{"statement": p["utility_hypothesis"], "basis_source_ids": ids, "confidence": p["utility_confidence"]}],
            "sources": sources, "missing_information": COMMON_UNKNOWN,
            "negative_signals": [{"kind": "qualification_limit", "detail": p["limitations"], "source_id": ids[0]}],
            "related_entities": [],
        })
        dims = {key: {"rating": rating, "rationale": rationale} for key,rating,rationale in zip(WEIGHTS,p["ratings"],dimension_rationales(p))}
        exact, rounded = calculate_score(dims)
        expected = "PRIORITY_A" if rounded >=72 else "PRIORITY_B" if rounded >=65 else "PRIORITY_C"
        assessments.append({
            "prospect_id": p["prospect_id"], "dimensions": dims, "eligibility_gate": None,
            "expected_priority": expected, "score_confidence": p["utility_confidence"],
            "positive_signals": [p["site"],p["async_signal"]], "negative_signals": [p["limitations"]],
            "uncertainties": COMMON_UNKNOWN,
            "minimal_qualification": {"ask": p["personalization"]["qualification_question_fr"], "why": "Valider l'utilité avant tout pilote, sans supposer ni anomalie ni économie.", "client_effort": "Réponse écrite de faisabilité ; aucun export demandé avant accord."},
            "judgment": BANDS[band(p)] + ". " + (p.get("commercial_hold") or p["limitations"]),
            "source_ids_used": ids,
        })
        p.update(score_exact=exact, score_display=rounded, legacy_priority=expected, commercial_band=band(p))
    dump("prospects_raw.json", {"schema_version":1,"researched_at":DATE,"prospects":raw})
    dump("scoring_assessments.json", {"schema_version":1,"scored_at":DATE,"prospects":assessments})
    prepare(HERE / "prospects_raw.json", ROOT / "prospecting/data/opposition.json", HERE)
    prepared = json.loads((HERE / "candidates_pre_scoring.json").read_text(encoding="utf-8"))
    # Une opposition locale doit bloquer la publication du lot classé, jamais être ignorée.
    rejected = json.loads((HERE / "rejected_prequalification.json").read_text(encoding="utf-8"))
    if rejected.get("prospects"):
        raise ValueError("Exclusions locales détectées : revoir le lot avant tout classement")
    score(HERE / "prospects_raw.json", HERE / "scoring_assessments.json", HERE / "scoring_results.json")
    items.sort(key=lambda p:(p["commercial_band"],-p["score_display"],p["name"]))
    for i,p in enumerate(items,1):
        p["commercial_rank"] = i
    counts = Counter(p["commercial_band"] for p in items)
    dump("commercial_prioritization.json", {"date":DATE,"ordering":"filtre métier/périmètre, bande async, score existant, nom ; rangs proches non significatifs", "counts":counts,"contacting_performed":False,"prospects":items})
    dump("source_inventory.json", {"reviewed_at":DATE,"sources":inventory,"note":"Date de consultation distincte de publication. Extrait indexé n'est pas lecture intégrale ; reprises d'annonces non indépendantes."})
    emails = []
    for p in items:
        emails.append({"prospect_id":p["prospect_id"],"name":p["name"],"rank":p["commercial_rank"],"target_function":p["target_role"],**p["personalization"],"value_angle_fr":p["utility_hypothesis"],"critical_limit":p["limitations"],"async_proposal_fr":"Je peux d'abord vous envoyer une courte liste de questions par email, à traiter à votre rythme. Ce mode de travail vous conviendrait-il ?", "avoid_claims":["Anomalie déjà détectée chez vous", "Économies ou ROI garantis", "Vous utilisez Slack, donc vous acceptez nos prestations async", "Votre ERP contient nécessairement une courbe énergétique"],"source_urls":[p["sources"][i]["url"] for i in p["personalization"]["hook_source_indices"]]})
    dump("email_personalization.json", {"status":"PREPARATION_ONLY_NOT_SENT","language_note":"Informations et accroches en français pour rédaction ultérieure ; anglais proposé à confirmer, pas email final validé.","prospects":emails})
    fields = ["commercial_rank","name","country","sector","size","score_display","legacy_priority","commercial_band","utility_status","async_rating","async_fact_confidence","async_transfer_confidence","site","utility_hypothesis","async_signal","limitations","target_role","hook_fr","qualification_question_fr","sources"]
    with (HERE / "prospects_50.csv").open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=fields,lineterminator="\n")
        writer.writeheader()
        for p in items:
            row={key:p.get(key,"") for key in fields}
            row.update(async_rating=p["ratings"][7],hook_fr=p["personalization"]["hook_fr"],qualification_question_fr=p["personalization"]["qualification_question_fr"],sources=" | ".join(s["url"] for s in p["sources"]))
            writer.writerow(row)
    report=["# 50 entreprises hors France : priorité à l'utilité industrielle et au travail écrit", "", f"Recherche du {DATE}. **{counts[1]} P1, {counts[2]} P2, {counts[3]} P3.** Ce sont des dossiers de prospection, pas 50 pilotes qualifiés.", "", "Le score /100 reprend les huit dimensions et pondérations existantes. La bande commerciale ajoute un filtre métier et async explicite ; elle prime sur le score. Aucun score n'est une probabilité de trouver une anomalie, de vendre ou d'économiser.", "", "P1 : preuves écrites opérationnelles convergentes + fit métier. P2 : métier plausible et échanges techniques/portails ou usage écrit documenté ; accord du sponsor à vérifier. P3 : réserve à enrichir, y compris excellent métier sans signal async suffisant. Les positions proches à l'intérieur d'une bande ne sont pas significatives.", "", "**Utilité :** hypothèse de travail, jamais diagnostic public. Toutes les disponibilités de mesures énergie, économies et acceptations d'un pilote restent UNKNOWN. L'effectif manquant n'est pas remplacé par le nombre de profils LinkedIn. Pour les torréfacteurs, l'électricité seule peut manquer l'énergie thermique. Pour le froid, charge nécessaire et charge évitable restent distinctes.", "", "Voir [audit de la recherche](RESEARCH_REVIEW.md), [personnalisation des emails](EMAIL_PERSONALIZATION.md), [CSV](prospects_50.csv) et [inventaire des sources](source_inventory.json). Les données détaillées séparent faits, inférences et notes dans les contrats existants.", "", "| Rang | Entreprise / pays | Score existant | Async /5 | Bande |", "|---|---|---:|---:|---|"]
    for p in items:
        report.append(f'| {p["commercial_rank"]} | [{p["name"]}](#{p["prospect_id"].lower()}) — {p["country"]} | {p["score_display"]}/100 | {p["ratings"][7]} | P{p["commercial_band"]} |')
    for p in items:
        report += ["",f'<a id="{p["prospect_id"].lower()}"></a>', f'## {p["commercial_rank"]}. {p["name"]} — {p["country"]}', "", f'**{p["sector"]}. Taille :** {p["size"]}.', "", f'**Score : {p["score_display"]}/100** (exact {p["score_exact"]}, {p["legacy_priority"]}) ; **P{p["commercial_band"]}**, async **{p["ratings"][7]}/5**. Confiance signal async : {p["async_fact_confidence"]} ; transfert à la relation Againward : {p["async_transfer_confidence"]}.', "", f'**Pourquoi le métier peut convenir :** {p["site"]} **Utilité à vérifier :** {p["utility_hypothesis"]}', "", f'**Preuves async et portée :** {p["async_signal"]}', "", f'**Meilleure objection :** {p["limitations"]} ' + (p.get("commercial_hold") or ""), "", f'**Fonction à cibler :** {p["target_role"]}. Fonction proposée, titulaire non vérifié.', "", f'**Question décisive :** {p["personalization"]["qualification_question_fr"]}', "", "**Sources et faits retenus :**", ""]
        for s in p["sources"]:
            report.append(f'- [{s["title"]}]({s["url"]}) — {s["claim"]} Publication : {s["published_at"] or "date inconnue"} ; consulté {DATE} ; {s["access_status"]}.')
    (HERE / "PROSPECTS_50.md").write_text("\n".join(line.rstrip() for line in report)+"\n",encoding="utf-8")
    note=["# Personnalisation : 50 accroches factuelles, aucun email envoyé", "", "Ces notes servent à rédiger, pas à envoyer automatiquement. Revalider le fait public au moment du contact. Ne pas traiter une annonce passée comme recrutement ouvert aujourd'hui. Ne pas citer Slack/Indeed pour donner une impression de surveillance des salariés. Les accroches portent sur la production ; les signaux async servent au choix du canal.", "", "Avant envoi : opposition locale à recontrôler et choix du destinataire professionnel à valider. Aucun nom privé ni adresse devinée. Proposer une courte qualification écrite, sans exiger immédiatement un fichier client. Ne jamais promettre un fonctionnement sans aucun appel ni un gain chiffré.", ""]
    for p in emails:
        note += [f'## {p["rank"]}. {p["name"]}', "", f'**Fonction :** {p["target_function"]}.', "", f'**Accroche factuelle proposée :** {p["hook_fr"]}', "", "**Source de l'accroche :** " + ", ".join(f'[vérifier le fait]({url})' for url in p["source_urls"]), "", f'**Lien utile avec Againward :** {p["value_angle_fr"]}', "", f'**Question écrite :** {p["qualification_question_fr"]}', "", f'**Réserve à respecter :** {p["critical_limit"]}', ""]
    note += ["## Proposition de mode de travail", "", "Je peux d'abord vous envoyer une courte liste de questions par email, à traiter à votre rythme. Ce mode de travail vous conviendrait-il ?", "", "Cette proposition reste à accepter par le prospect. Elle ne prouve ni accès aux données ni acceptation d'un pilote payant."]
    (HERE / "EMAIL_PERSONALIZATION.md").write_text("\n".join(note)+"\n",encoding="utf-8")
    print(json.dumps({"prospects":len(items),"bands":counts,"source_records":len(inventory),"contacting_performed":False}))

if __name__ == "__main__":
    main()
