#!/usr/bin/env python3
"""Render reviewed public Rental research. Standard library only; no network or outreach.
Run from anywhere: python prospecting/build_rental_prospects.py
"""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATE = '2026-09-20'
DIMENSIONS = ['rental_likelihood','economic_potential','document_complexity','size_autonomy','evidence_quality','contact_relevance','personalization','async_suitability']
WEIGHTS = [20,15,15,15,15,5,10,5]
# Reviewed counter-evidence, not automatic lead enrichment.
# Named overrides are intentionally keyed by actual source group keys below.
CAP_BY_NAME = {
 'CANCÉ': 'Contact métier aluminium, payeur potentiellement sous-traitant; priorité après qualification achats.',
 'Boutillet': 'Parc et ateliers propres; le recrutement finance ne prouve pas des locations externes.',
 'Construction Savoyarde': 'Moyens propres possibles; locations externes non corroborées.',
 'CAPOCCI': 'Parc important et outil CAPCONNECT; qualifier les seuls achats externes.',
 'COBAT Constructions': 'Références non datées, formulaire seulement et risque d’homonymie de domaine signalé par l’entreprise.',
 'SCAM TP': 'Moyens propres annoncés et aucune preuve de locations externes.',
 'UEC – Union des Entreprises de Construction': 'Plus de vingt engins possédés; le volume externe doit être établi.',
 'SOPRECO – Groupe Quatre+': 'Références historiques et organisation groupe; locations externes non établies.',
 'KERN Bretagne (anciennement SRB Construction)': 'Réorganisation et changement de marque; entité acheteuse et payeur à qualifier.',
 "CCE – Constructions de la Côte d'Émeraude": 'Intégration de plusieurs métiers et parc propre; volume de location externe inconnu.',
 'Giesper – Travaux Publics': 'Contrôles fournisseurs explicites et parc propre; aucune faiblesse déduite du recrutement.',
 'Entreprises Gilles Moury SA / Groupe Moury Construct': 'Groupe coté et structuré, documents achats et autonomie opérationnelle inconnus.',
 'Entreprise Jérouville SA': 'Parc propre et titulaires matériel/comptabilité issus d’un ancien site.',
 'S.D.C. Builders Limited': 'Organisation importante et structurée; matériel potentiellement payé par sous-traitants.',
 'Quinn (London) Limited': 'Email public prouvé en 2023 seulement; à reconfirmer avant de le prioriser.',
 'Hobson and Porter Limited': 'Références opérationnelles anciennes et location externe non démontrée.',
 'Logan Construction (South East) Ltd': 'Référence principale historique; achats locatifs actuels à qualifier.',
 'Barnes Construction – The Barnes Group Limited': 'Unités homonymes et groupe intégré; achats de location non explicitement documentés.',
}
HIGH_KEEP = {'dub-invest','le-batiment-associe'}

def read_records(folder):
    records=[]
    for f in sorted((ROOT/folder).glob('batch_*.json')) + list((ROOT/folder).glob('research_records.json')):
        data=json.loads(f.read_text())
        rows=data if isinstance(data,list) else data['prospects']
        for row in rows:
            if row.get('selection_decision','').startswith('REJECTED'):
                continue
            r=deepcopy(row)
            r['research_file']=str(f.relative_to(ROOT))
            r.setdefault('research_date', '2026-09-19')
            r.setdefault('country','France')
            r.setdefault('jurisdiction','France')
            r.setdefault('language','fr')
            r.setdefault('contact_form',None)
            r.setdefault('contact_email',None)
            r.setdefault('contact_name',None)
            r.setdefault('contact_title',None)
            r.setdefault('revenue',None)
            r['initial_ratings']=r['ratings'][:]
            changes=[]
            if r['rental_evidence']=='INFERRED' and r['ratings'][0]>=4 and r['group_key']!='altez':
                r['ratings'][0]=3
                changes.append('Probabilité de location ramenée à 3/5 : activité intensive prouvée, recours externe non corroboré.')
            if r['group_key']=='avenir-deconstruction':
                r['ratings'][1]=4
                changes.append('Potentiel économique ramené à 4/5 : aucune dépense locative connue.')
            if r['company']=='CANCÉ':
                r['ratings'][5]=2
                changes.append('Pertinence de contact ramenée à 2/5 : directeur métier aluminium, pas achats/finance confirmé.')
            if r['confidence']=='HIGH' and r['group_key'] not in HIGH_KEEP:
                r['confidence']='MEDIUM'
                changes.append('Confiance ramenée à MEDIUM : registre et déclarations de l’entreprise ne corroborent pas indépendamment la dépense locative.')
            if r['group_key']=='altez':
                r['rental_evidence']='SUPPLIER_DEPLOYMENT_PAYOR_UNCONFIRMED'
            r['prospect_score']=round(sum(n*w/5 for n,w in zip(r['ratings'],WEIGHTS)),1)
            natural='A' if r['prospect_score']>=80 else 'B' if r['prospect_score']>=65 else 'C' if r['prospect_score']>=55 else 'REJECT'
            assert natural!='REJECT',r['company']
            cap=CAP_BY_NAME.get(r['company'])
            r['tier']='B' if natural=='A' and cap else natural
            r['tier_override_reason']=cap if natural=='A' and cap else None
            if r['tier_override_reason']:changes.append('Classement B malgré score A : '+cap)
            r['source_references']=[dict(id=f'S{i+1}',url=url,supports=claim,consulted_on=r['research_date']) for i,(url,claim) in enumerate(r['sources'])]
            r['confirmed_email']=r['contact_email']
            r['inferred_email_pattern']=None
            r['email_verification']='PUBLICATION_ONLY_NOT_DELIVERABILITY_TESTED'
            assert r['sources'] and 0<=r['contact_source_index']<len(r['sources']),r['company']
            r['contact_source']=r['sources'][r['contact_source_index']][0]
            r['professional_contact_route']=r['contact_email'] or r['contact_form']
            assert r['professional_contact_route'],r['company']
            r['why_it_fits']=f"Activité exécutante : {r['sector']}. Taille documentée : {r['size']}. Les opérations citées justifient de qualifier le volume de locations et les pièces disponibles."
            r['equipment_intensity_evidence']=' '.join(r['facts'])
            r['rental_spend_hypothesis']=r['rental_hypothesis']
            r['email_personalization_note']=' '.join(r['facts'][:3])
            r['likely_pain_angle']='Hypothèse de prospection, non anomalie constatée : '+r['pain']
            r['suggested_opening_angle']=r['opening']
            r['EMAIL_CONTEXT']=' '.join(r['facts'][:2])+f" Matériel/location : {r['equipment']} (recours externe à qualifier). Contact recommandé : {r['target_role']}. Angle hypothétique : {r['pain']}"
            r['research_limitations']=r['limitations']
            r['review']={
                'date':DATE,'question':'Quelle est la meilleure raison de penser que ce prospect pourrait louer très peu de matériel ou être mal adapté ?',
                'strongest_counterargument':' '.join(r['limitations'][:2]),
                'decision':'RETAIN_WITH_QUALIFICATION',
                'changes':changes,
                'size_check':r['size']+' — adéquation qualitative, aucun budget extrapolé.',
                'contact_check':r['target_role']+'; '+r['contact_status']+'; titulaire exact '+('publié, à revalider' if r['contact_name'] else 'non confirmé'),
                'personalization_check':'Faits séparés des hypothèses; sources d’activité/projets et contact listées dans la fiche.',
                'no_problem_asserted':True,
                'group_check':'Une seule entrée sélectionnée pour '+r['group_key']+'; périmètre et autonomie restent ceux décrits dans les limites.',
                'first_qualification':'Confirmer par écrit que cette entité paie des locations externes récurrentes et conserve contrats, factures et traces de retour.'
            }
            reasons=[
                f"{r['rental_evidence']} — {r['rental_hypothesis']}",
                'Échelle indicative : '+r['size']+'. Pas de dépense locative publiée ni de retour sur investissement calculé.',
                'Complexité plausible à partir de : '+' '.join(r['facts'][:2]),
                'Adéquation qualitative taille et groupe; contre-indices : '+r['limitations'][0],
                r['confidence']+' : sources publiques décrites ci-dessous; la confiance porte sur le dossier de ciblage, pas sur des erreurs.',
                r['contact_status']+' vers '+r['target_role']+'; canal publié, délivrabilité non testée.',
                'Faits réutilisables : '+' '.join(r['facts'][:2]),
                'Compatibilité supposée avec un échantillon documentaire par écrit; aucune préférence client connue.'
            ]
            r['score_components']=[dict(factor=k,weight=w,rating=n,points=round(w*n/5,1),reason=reason) for k,w,n,reason in zip(DIMENSIONS,WEIGHTS,r['ratings'],reasons)]
            records.append(r)
    records.sort(key=lambda r:({'A':0,'B':1,'C':2}[r['tier']],-r['prospect_score'],r['company']))
    for rank,r in enumerate(records,1):r['rank']=rank
    return records

def stats(rows,rejected):
    c=Counter(r['contact_status'] for r in rows)
    return dict(researched_documented=len(rows)+len(rejected),rejected=len(rejected),selected=len(rows),by_tier=dict(Counter(r['tier'] for r in rows)),confirmed_direct_professional_email=c['CONFIRMED'],role_email=c['ROLE_ADDRESS'],generic_email=c['GENERIC'],role_or_generic_email=c['ROLE_ADDRESS']+c['GENERIC'],contact_form_only=c['CONTACT_FORM_ONLY'],inferred_patterns=c['INFERRED_PATTERN'],by_country=dict(Counter(r['country'] for r in rows)),by_confidence=dict(Counter(r['confidence'] for r in rows)))

def summary_table(s):
    labels={'researched_documented':'Dossiers documentés examinés','rejected':'Rejetés','selected':'Sélectionnés','confirmed_direct_professional_email':'Emails professionnels nominatifs publiés','role_email':'Emails de fonction','generic_email':'Emails génériques','contact_form_only':'Formulaire uniquement','inferred_patterns':'Emails devinés'}
    return '\n'.join(['| Indicateur | Nombre |','|---|---:|']+[f'| {v} | {s[k]} |' for k,v in labels.items()])+f"\n\nTiers : {', '.join(f'{k} : {v}' for k,v in s['by_tier'].items())}. Pays : {', '.join(f'{k} : {v}' for k,v in s['by_country'].items())}. Confiance : {', '.join(f'{k} : {v}' for k,v in s['by_confidence'].items())}.\n"

def render(rows,s,folder,method):
    intl='international' in folder
    title='50 prospects hors France' if intl else '50 prospects France'
    out=[f'# AGAINWARD Rental — {title}\n',f'Recherche des 19–20 septembre 2026; revue finale le {DATE}. **Aucun contact effectué.**\n',method, '\n## Résultat de la sélection\n',summary_table(s),
         '\nLes volumes examinés comptent les dossiers conservés et les rejets consignés dans [REJECTED.json](../REJECTED.json), pas tous les résultats de recherche aperçus. Les effectifs mélangent parfois unité légale, groupe, ETP et déclarations : le périmètre est précisé dans chaque fiche. « Confirmé » signifie publié, jamais délivrabilité testée. Une adresse nominative peut être moins pertinente qu’une adresse finance.\n',
         '\n## Ordre de première qualification\n',
         'Les dix premières lignes sont à qualifier avant un élargissement. A = contacter/qualifier d’abord, B = bon prospect avec réserves, C = plausible avec preuves plus faibles. Un A ne signifie pas location ni anomalie confirmée.\n',
         '| Rang | Entreprise | Score /100 | Tier | Contact |\n|---:|---|---:|:---:|---|']
    for r in rows[:10]:out.append(f"| {r['rank']} | {r['company']} | {r['prospect_score']} | {r['tier']} | {r['contact_status']} |")
    out += ['\n## Cadre juridique et limites communes\n',
            'Lire la [comparaison des juridictions](../rental_international_50/JURISDICTIONS.md). '+('Les sociétés britanniques et les adresses impersonnelles de personnes morales belges ont des règles distinctes; la sélection ne constitue pas une autorisation générale d’envoi.' if intl else 'La pertinence professionnelle, l’information et le respect de l’opposition restent déterminants pour la prospection nominative.'),
            '\nLa location externe est généralement inférée. Parc propre, sous-traitance, achat centralisé et responsabilité de paiement peuvent invalider l’opportunité. Aucun taux d’erreur, montant récupérable ou déficit de contrôle n’est allégué. Les registres consultés ne sont pas un audit de solvabilité. Références anciennes explicitement conservées comme exemples de capacités, pas comme chantiers en cours.\n',
            '\nSignaux récurrents : plusieurs implantations; équipes de montage mobiles; opérations par phases en site occupé; gros œuvre/terrassement; administration achats identifiable; traces publiques de fournisseurs ou de gestion des locations. Contre-signaux : parc propre étendu et équipe de contrôle déjà structurée.\n',
            '\n## Fiches détaillées\n']
    for r in rows:
        contact=r['professional_contact_route']
        out += [f"\n### {r['rank']}. {r['company']} — {r['prospect_score']}/100 — {r['tier']}\n",
                f"**Site :** [{r['website']}]({r['website']}) · **Pays / localisation :** {r['country']} — {r['location']}\n",
                f"**Secteur :** {r['sector']} · **Taille :** {r['size']} · **CA :** {r['revenue'] or 'non retenu faute de donnée suffisamment comparable et vérifiée'}\n",
                f"**Pourquoi cette cible :** {r['why_it_fits']}\n",
                '**Faits utiles / personnalisation :**\n']
        out.extend('- '+fact for fact in r['facts'])
        out += [f"\n**Équipements concernés :** {r['equipment']}\n",
                f"**Location — {r['rental_evidence']} :** {r['rental_hypothesis']}\n",
                f"**Fonction cible :** {r['target_role']}. **Personne publiée :** {r['contact_name'] or 'non trouvée pour cette fonction'}{(' — '+r['contact_title']) if r['contact_title'] else ''}.\n",
                f"**Route :** {contact} · **Statut :** {r['contact_status']} · [Source du contact]({r['contact_source']}). Aucun modèle d’email inféré.\n",
                f"**Angle de difficulté, hypothétique :** {r['pain']}\n",
                f"**Ouverture suggérée, sans rédiger l’email :** {r['opening']}\n",
                f"**EMAIL_CONTEXT :** {r['EMAIL_CONTEXT']}\n",
                f"**Confiance :** {r['confidence']} · **Recherche :** {r['research_date']} · **Revue :** {DATE}.\n",
                '**Limites et meilleure objection :**\n']
        out.extend('- '+lim for lim in r['limitations'])
        if r['review']['changes']:
            out.append('\n**Arbitrage de revue :** '+' '.join(r['review']['changes'])+'\n')
        out += ['\n**Score détaillé** (location, potentiel, complexité, taille, preuves, contact, personnalisation, asynchrone) : '+', '.join(str(n)+'/5' for n in r['ratings'])+'. Justifications par dimension dans le JSON.\n','**Sources et affirmations étayées :**\n']
        out.extend(f'- [{claim}]({url})' for url,claim in r['sources'])
    (ROOT/folder/'PROSPECTS_50.md').write_text('\n'.join(out)+'\n')


def main():
    rejected=json.loads((ROOT/'REJECTED.json').read_text())
    method=(ROOT/'rental_france_50/METHODOLOGY.md').read_text().replace('# Méthode fixée avant sélection — Rental France','## Méthodologie')
    method=method.replace('## Cible','### Cible').replace('## Preuves','### Preuves').replace('## Score','### Score').replace('## Approche','### Approche').replace('## Contrôle','### Contrôle')
    all_rows=[];all_stats={}
    for folder in ['rental_france_50','rental_international_50']:
        rows=read_records(folder)
        assert len(rows)==50,(folder,len(rows))
        fr=folder=='rental_france_50'
        rejects=[r for r in rejected if (r['country']=='France')==fr]
        s=stats(rows,rejects)
        payload=dict(schema_version='againward.rental.osint.v1',research_date=DATE,status='REVIEWED_RESEARCH_NOT_CONTACTED',outreach_authorized=False,methodology='../rental_france_50/METHODOLOGY.md',jurisdictions='../rental_international_50/JURISDICTIONS.md',score_weights=dict(zip(DIMENSIONS,WEIGHTS)),summary=s,top_10=[r['company'] for r in rows[:10]],prospects=rows)
        (ROOT/folder/'PROSPECTS_50.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
        render(rows,s,folder,method)
        all_rows+=rows;all_stats[folder]=s
    assert len({r['group_key'] for r in all_rows})==100,'Duplicate groups'
    assert not ({r['company'] for r in rejected}&{r['company'] for r in all_rows})
    for r in all_rows:
        assert len(r['facts']) in (2,3,4),r['company']
        assert len(r['ratings'])==8 and all(0<=n<=5 for n in r['ratings'])
        assert r['confidence']!='LOW' or r['tier']!='A'
        assert r['contact_status'] in {'CONFIRMED','ROLE_ADDRESS','GENERIC','CONTACT_FORM_ONLY'}
        assert (r['contact_email'] is None)==(r['contact_status']=='CONTACT_FORM_ONLY'),r['company']
        assert all(url.startswith('https://') or url.startswith('http://') for url,_ in r['sources'])
        assert '@' in r['contact_email'] if r['contact_email'] else r['contact_form'].startswith('https://')
        assert all(r.get(k) for k in ['EMAIL_CONTEXT','why_it_fits','likely_pain_angle','research_limitations','contact_source'])
    reviews={r['company']:r['review'] for r in all_rows}
    (ROOT/'RENTAL_FINAL_REVIEW.json').write_text(json.dumps(dict(date=DATE,reviewed=100,group_duplicates=0,records=reviews),ensure_ascii=False,indent=2)+'\n')
    total=stats(all_rows,rejected)
    (ROOT/'RENTAL_SUMMARY.json').write_text(json.dumps(dict(date=DATE,total=total,datasets=all_stats),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(total,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
