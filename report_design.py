"""Agent-authored page composition of the existing validated client report model.

No automatic editorial plan. Python resolves content references, checks fidelity,
measures bounds and paints the coordinates chosen by the agent using shared PDF primitives.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

from client_delivery import (_read, _write, _require_text, _pdf_text, _PdfPage, _png_rgb,
    _write_pdf_pages, validate_client_report_model, _resolve_chart_requests)

COMPONENTS = {'COVER','EXECUTIVE_SUMMARY','FINDING','SECONDARY_FINDING','METRIC_CARD',
    'EVIDENCE_CHART','COMPARISON','DECISION','LIMITATION','ECONOMIC_RANGE',
    'INVESTIGATION_VALUE','NEXT_STEP','METHODOLOGY','TECHNICAL_APPENDIX'}
PALETTE = {'ink':(0.10,0.17,0.22),'muted':(0.36,0.41,0.44),
           'accent':(0.09,0.38,0.40),'paper':(1,1,1),'wash':(0.94,0.96,0.96)}
SCHEMA = 'againward-report-design-v1'


def _digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def _safe_chart(case, model_file, chart):
    """Reproduce the chart from its canonical dataset and compare exact pixels/metadata."""
    import tempfile
    import csv
    canonical=_read(case/'derived/canonical_case.json')
    datasets={d['dataset_id']:d for d in canonical['available_datasets']}
    dataset=datasets.get(chart.get('dataset_ref'))
    if dataset is None:raise ValueError('Source graphique absente.')
    source=case/dataset['normalized_file']
    if source.is_symlink() or not source.resolve().is_relative_to(case.resolve()):
        raise ValueError('Source graphique hors dossier.')
    chart_path=model_file.parent/str(chart.get('relative_path',''))
    if (chart_path.is_symlink() or not chart_path.is_file()
            or not chart_path.resolve().is_relative_to(model_file.parent.resolve())):
        raise ValueError('Graphique absent ou hors dossier de rendu.')
    request={'type':chart['type'],'dataset_id':chart['dataset_ref'],
             'title':chart['title'],'purpose':chart['purpose'],'finding_refs':chart.get('finding_refs',[])}
    with tempfile.TemporaryDirectory(dir=case/'scratch') as temp:
        regenerated=_resolve_chart_requests(case,{'chart_requests':[request]},Path(temp))[0]
        expected=Path(temp)/regenerated['relative_path']
        if chart_path.read_bytes()!=expected.read_bytes():
            raise ValueError('Graphique non reproductible depuis les données canoniques.')
    for key in ('type','title','purpose','caption','dataset_ref','axis_x','axis_y','legend','operation_context','operation_encoding','explains','source_refs','finding_refs','method','no_finding_ref'):
        if chart.get(key)!=regenerated.get(key):raise ValueError('Sémantique graphique modifiée.')
    with source.open(encoding='utf-8',newline='') as handle:
        rows=list(csv.DictReader(handle))
    for row in rows:
        value=row.get('energy_kwh') or row.get('power_kw') or row.get('measurement')
        if value is None or not math.isfinite(float(value)):
            raise ValueError('Graphique : aucune suppression silencieuse de valeur invalide.')
    from datetime import datetime
    start=datetime.fromisoformat(rows[0]['timestamp']);end=datetime.fromisoformat(rows[-1]['timestamp'])
    period='Horodatage source : '+start.strftime('%d/%m/%Y %H:%M %z').strip()+' — '+end.strftime('%d/%m/%Y %H:%M %z').strip()
    values=[float(r.get('energy_kwh') or r.get('power_kw') or r.get('measurement')) for r in rows]
    low=min(0.0,min(values));high=max(values)
    if math.isclose(low,high):high+=1.0
    high+=(high-low)*.05
    return {'display_period':period,'plot_range':{'low':low,'high':high},
            'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'image_sha256':hashlib.sha256(chart_path.read_bytes()).hexdigest(),
            'method':'canonical_full_window_pixel_mean_with_min_max_envelope', 'path':str(chart_path)}


def _french_money(display):
    if display.startswith('€'):
        amount,period=display.rsplit('/',1)
        return amount.replace('€','')+' €'+('/an' if period=='an' else ' (ponctuel)')
    return display


def content_catalog(case_directory, model, model_path):
    """Expose authorized fragments, not arbitrary JSON pointers into internal state."""
    from value_map import build_value_map
    case=Path(case_directory);model_file=Path(model_path)
    validate_client_report_model(model,case)
    # Validate numbers against economic inputs even when no portfolio total is selected.
    build_value_map(case,_read(case/'investigation/economic_decision_state.json'))
    catalog={}
    def add(ref,title,lines,kind='TEXT',**extra):
        catalog[ref]={'title':title,'lines':lines,'kind':kind,**extra}
    for field in ('report_title','analysis_period'):
        _require_text(model['metadata'][field],field,allow_numbers=False)
    add('cover',model['metadata']['site_name'],[model['metadata']['report_title'],model['metadata']['analysis_period']])
    add('executive','Ce qu’il faut retenir',[model['executive_summary']['message']])
    add('notice','Cadre de la mission',[model['metadata']['regulatory_notice']])
    add('method','Méthode', [model['technical_appendix']['method']])
    if model['technical_appendix'].get('sources'):
        add('sources','Sources examinées',[s['label'] for s in model['technical_appendix']['sources']],source_refs=[s['source_ref'] for s in model['technical_appendix']['sources']])
    if model['technical_appendix']['limitations']:
        add('limitations','Limites de l’analyse',model['technical_appendix']['limitations'])
    for i,item in enumerate(model['what_we_checked']):
        add(f'checked:{i}','Vérifications réalisées',[item['text']],source_claim=item)
    for i,item in enumerate(model['no_action_items']):
        add(f'no_action:{i}',item['title'],[item['explanation']],source_claim=item['claim'])
    for card in model['decision_cards']:
        aid=card['action_ref'];context={'finding_refs':card['claim_refs']['finding_ids'],
            'decision_ref':card['decision_ref'],'evidence_level':card['evidence_level']}
        for key,title in [('what_we_found',card['headline']),('why_this_matters','Pourquoi cela compte'),
                          ('contextual_rationale','Contexte opérationnel'),('uncertainty','Ce qui reste incertain')]:
            add(f'{aid}:{key}',title,[card[key]],source_claim=card['claims'][key],**context)
        add(f'{aid}:decision','Décision',[card['client_directive'],'Niveau de preuve : '+card['evidence_level']],**context)
        if card.get('operational_constraints'):
            add(f'{aid}:constraints','Contraintes à respecter',[c['description'] for c in card['operational_constraints']],**context)
        if card.get('next_step'):
            labels={'metric':'Mesure suivie','expected_direction':'Évolution attendue','comparison_window':'Période de comparaison',
                'confounders':'À contrôler','minimum_evidence':'Critère de validation','what_it_resolves':'Question à résoudre',
                'decision_that_can_change':'Décision concernée','cost_or_burden':'Effort à prévoir','why_worth_it':'Utilité de la vérification'}
            add(f'{aid}:next_step',card['next_step']['title'],[labels[k]+' : '+str(v) for k,v in card['next_step']['details'].items()],**context)
        econ=card.get('economic_impact')
        if econ and econ.get('annual_net_benefit'):
            add(f'{aid}:economics','Bénéfice annuel net potentiel',[
                _french_money(econ['annual_net_benefit']['display']),
                'Estimation sous hypothèses ; aucune économie réalisée démontrée.',
                'Coût d’intervention : '+(_french_money(econ['intervention_cost']['display']) if econ.get('intervention_cost') else 'inconnu')],
                kind='ECONOMICS',economic_claim=econ,**context)
    for item in model.get('investigation_value',{}).get('items',[]):
        add('value:'+item['value_ref'],'Valeur de l’investigation',item['lines']+[
            'Valeurs distinctes, non additionnées.'],kind='VALUE_MAP',value_ref=item['value_ref'])
    findings=_read(case/'investigation/structured_findings.json')
    for chart in model.get('charts',[]):
        (case/'scratch').mkdir(exist_ok=True)
        if findings['findings'] and not chart.get('finding_refs'):
            raise ValueError('Codex doit relier le graphique aux findings qu’il éclaire.')
        proof=_safe_chart(case,model_file,chart)
        add('chart:'+chart['chart_id'],chart['title'],[chart['caption'],proof['display_period'],chart['axis_y'],chart['legend']],
            kind='CHART',chart=chart,reproducibility=proof,
            finding_refs=chart['finding_refs'],
            no_finding_ref=chart['no_finding_ref'])
    return catalog


def validate_report_design(case_directory, model, model_path, design):
    if not isinstance(design,dict) or set(design)!={'schema_version','pages','selected_findings','omitted_actions'} or design['schema_version']!=SCHEMA:
        raise ValueError('REPORT_DESIGN_MODEL fermé requis ; aucun texte/chiffre libre.')
    catalog=content_catalog(case_directory,model,model_path)
    selected=design['selected_findings'];known={f for c in model['decision_cards'] for f in c['claim_refs']['finding_ids']}
    if not isinstance(selected,list) or len(set(selected))!=len(selected) or set(selected)-known:
        raise ValueError('Finding sélectionné absent des artefacts autorisés.')
    pages=design['pages']
    if not isinstance(pages,list) or not 1<=len(pages)<=12:
        raise ValueError('Composition attendue entre une et douze pages, sans remplissage automatique.')
    used=[];semantics=[]
    for page in pages:
        if not isinstance(page,dict) or set(page)!={'intent','blocks'} or page['intent'] not in COMPONENTS:
            raise ValueError('Intent de page inconnu.')
        if not isinstance(page['blocks'],list) or not page['blocks']:raise ValueError('Page vide refusée.')
        rectangles=[]
        for block in page['blocks']:
            if not isinstance(block,dict) or set(block)-{'component','content_ref','box','font_size','emphasis','heading_ref'} or not {'component','content_ref','box','font_size','emphasis'}<=set(block):
                raise ValueError('Bloc : composition et référence uniquement ; aucun chiffre factuel libre.')
            ref=block['content_ref'];kind=block['component']
            if ref not in catalog or kind not in COMPONENTS:raise ValueError('Référence ou composant de rapport absent.')
            item=catalog[ref]
            heading_ref=block.get('heading_ref')
            if heading_ref is not None:
                heading=model.get('editorial_headings',{}).get(heading_ref)
                if heading is None or item['kind'] in {'ECONOMICS','VALUE_MAP','CHART'} or kind=='DECISION':
                    raise ValueError('Titre éditorial absent ou libellé de preuve économique/graphique non modifiable.')
                item={**item,'title':heading['text'],'heading_claim':heading}
            if (kind=='EVIDENCE_CHART')!=(item['kind']=='CHART'):
                raise ValueError('Un graphique exige sa source et sa méthode reproductibles.')
            if kind in {'METRIC_CARD','ECONOMIC_RANGE'} and item['kind']!='ECONOMICS':
                raise ValueError('Métrique économique sans claim canonique.')
            box=block['box'];size=block['font_size']
            if not isinstance(box,list) or len(box)!=4 or any(type(v) not in {int,float} or not math.isfinite(v) for v in box):
                raise ValueError('Coordonnées de composition invalides.')
            x,y,w,h=box
            if x<40 or y<65 or w<80 or h<30 or x+w>555 or y+h>785:
                raise ValueError('Bloc hors des marges de page.')
            if type(size) not in {int,float} or not 9<=size<=32 or block['emphasis'] not in {'NORMAL','PRIMARY','QUIET'}:
                raise ValueError('Typographie ou emphase invalide.')
            for a,b,c,d in rectangles:
                if x<a+c and x+w>a and y<b+d and y+h>b:
                    raise ValueError('Chevauchement de blocs ; ajuster la composition.')
            rectangles.append(box);used.append(ref)
            semantics.append({'component':kind,'content_ref':ref,'content':item})
    if 'executive' not in used or 'notice' not in used:
        raise ValueError('Message principal et cadre de mission doivent rester visibles.')
    omitted=design['omitted_actions']
    if not isinstance(omitted,dict):raise ValueError('Omissions explicitement justifiées requises.')
    actions={c['action_ref'] for c in model['decision_cards']}
    if set(omitted)-actions:raise ValueError('Action omise inconnue.')
    for card in model['decision_cards']:
        aid=card['action_ref'];visible=any(ref.startswith(aid+':') for ref in used)
        if visible:
            required={aid+':what_we_found',aid+':uncertainty',aid+':decision'}
            if card.get('operational_constraints'):required.add(aid+':constraints')
            if not required<=set(used):raise ValueError('Finding visible sans observation, limite, décision ou contrainte.')
            if set(card['claim_refs']['finding_ids'])-set(selected):raise ValueError('Sélection des findings incohérente.')
            if aid in omitted:raise ValueError('Action simultanément affichée et omise.')
        elif aid not in omitted:
            raise ValueError('Action non affichée : justification éditoriale obligatoire.')
    for reason in omitted.values():_require_text(reason,'Motif éditorial',allow_numbers=False)
    # Bind substantive source changes too, even if a display value happens to stay equal.
    case=Path(case_directory)
    source_hashes={}
    for name in ('investigation/structured_findings.json','investigation/economic_decision_state.json',
                 'derived/canonical_case.json','evidence/dataset_provenance.json',
                 'investigation/investigation.json','investigation/review.json','investigation/questions.json'):
        path=case/name
        if path.is_file():source_hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    # Geometry, font sizes and page breaks are aesthetic; content/selection/order are substantive.
    return {'catalog':catalog,'semantic_sha256':_digest({'content':semantics,'selected_findings':selected,'omitted_actions':omitted,'source_hashes':source_hashes}),
            'used_refs':used}


def _width(text,size):
    # Conservative Helvetica advances prevent overflow without a platform font dependency.
    return sum((.28 if c in "ilI.,:;!'| " else .95 if c in 'MWmw@' else .70)*size for c in text)


def _lines(text,size,width):
    words=text.split();lines=[];line=''
    for word in words:
        if _width(word,size)>width:raise ValueError('Mot trop long pour le bloc ; reformuler ou élargir.')
        candidate=(line+' '+word).strip()
        if line and _width(candidate,size)>width:lines.append(line);line=word
        else:line=candidate
    if line:lines.append(line)
    return lines


def _paint_text(page,text,x,y,size,bold=False,color='ink'):
    r,g,b=PALETTE[color];font='F2' if bold else 'F1'
    encoded=_pdf_text(text).decode('latin-1')
    page.commands.append(f'BT {r} {g} {b} rg /{font} {size} Tf 1 0 0 1 {x:.2f} {842-y:.2f} Tm ({encoded}) Tj ET')


def render_designed_report(case_directory, model, model_path, design, *, output_directory=None):
    from energy_mvp.client_lifecycle import assert_workflow_action_allowed
    assert_workflow_action_allowed(case_directory,'report_generation')
    case=Path(case_directory);target=Path(output_directory) if output_directory else case/'outputs/client_report'
    if not target.resolve().is_relative_to((case/'outputs').resolve()):
        raise ValueError('Rapport final doit rester dans outputs/ du dossier.')
    validated=validate_report_design(case,model,model_path,design)
    pages=[];images=[]
    for index,plan in enumerate(design['pages'],1):
        page=_PdfPage([]);pages.append(page)
        _paint_text(page,'AGAINWARD',40,35,11,True)
        _paint_text(page,'ANALYSE DE PERFORMANCE',352,35,9,color='muted')
        _paint_text(page,str(index),540,813,9,color='muted')
        page.commands.append('0.09 0.38 0.40 RG 1 w 40 795 m 555 795 l S')
        for block in plan['blocks']:
            item=validated['catalog'][block['content_ref']]
            if block.get('heading_ref') is not None:
                item={**item,'title':model['editorial_headings'][block['heading_ref']]['text']}
            x,y,w,h=block['box'];size=block['font_size'];cursor=y
            title_size=min(26,size+7) if block['emphasis']=='PRIMARY' else min(16,size+2)
            for line in _lines(item['title'],title_size,w):
                cursor+=title_size*1.25;_paint_text(page,line,x,cursor,title_size,True)
            cursor+=12
            if item['kind']=='CHART':
                width,height,compressed=_png_rgb(Path(item['reproducibility']['path']))
                image_name=f'DesignImage{len(images)}';images.append((image_name,width,height,compressed))
                draw_w=w;draw_h=draw_w*height/width
                page.commands.append(f'q {draw_w:.2f} 0 0 {draw_h:.2f} {x:.2f} {842-cursor-draw_h:.2f} cm /{image_name} Do Q')
                bounds=item['reproducibility']['plot_range']
                for value,fraction in ((bounds['high'],20/360),(bounds['low'],324/360)):
                    _paint_text(page,f'{value:g}',x,cursor+draw_h*fraction,9,color='muted')
                cursor+=draw_h+12
            for n,text in enumerate(item['lines']):
                text_size=min(28,size+10) if item['kind']=='ECONOMICS' and n==0 else size
                for line in _lines(text,text_size,w):
                    cursor+=text_size*1.35
                    _paint_text(page,line,x,cursor,text_size,bold=item['kind']=='ECONOMICS' and n==0,
                                color='muted' if block['emphasis']=='QUIET' else 'ink')
                cursor+=6
            if cursor>y+h:raise ValueError(f'Bloc {block["content_ref"]} déborde : augmenter sa hauteur ou recomposer la page.')
    target.mkdir(parents=True,exist_ok=True)
    rendered=_write_pdf_pages(pages,images,target/'client_report.pdf',renderer='againward_agent_composition_v1')
    _write(target/'REPORT_DESIGN_MODEL.json',design)
    receipt={**rendered,'semantic_sha256':validated['semantic_sha256'],
        'pdf_sha256':hashlib.sha256((target/'client_report.pdf').read_bytes()).hexdigest(),
        'model_ref':str(Path(model_path).resolve().relative_to(case.resolve())),
        'design_ref':str((target/'REPORT_DESIGN_MODEL.json').resolve().relative_to(case.resolve())),
        'status':'DRAFT_REQUIRES_VISUAL_AND_HUMAN_REVIEW','approved_for_delivery':False}
    _write(target/'CLIENT_REPORT_DELIVERY.json',receipt)
    return receipt


VISUAL_CHECKS = {'no_clipping','no_overflow','no_orphan_headings','readable_captions',
    'readable_charts','balanced_blocks','no_excessive_whitespace','no_overflowing_tables',
    'no_unhelpful_repetition','useful_pagination','readable_density','adequate_contrast',
    'accents_currency_units_correct','consistent_pages','professional_client_ready'}


def record_visual_review(case_directory, review):
    """Record Codex's actual visual inspection, never infer it from PDF existence."""
    case=Path(case_directory);target=case/'outputs/client_report'
    pdf=target/'client_report.pdf'
    if (not isinstance(review,dict) or set(review)!={'reviewer_role','pdf_sha256','checks','notes'}
            or review['reviewer_role']!='CODEX' or set(review['checks'])!=VISUAL_CHECKS
            or any(v is not True for v in review['checks'].values())
            or review['pdf_sha256']!=hashlib.sha256(pdf.read_bytes()).hexdigest()
            or not isinstance(review['notes'],str) or not review['notes'].strip()):
        raise ValueError('Revue visuelle réelle complète requise pour la version exacte du PDF.')
    _write(target/'REPORT_VISUAL_REVIEW.json',review)
    return review


def validate_report_delivery_artifacts(case_directory, human_review):
    case=Path(case_directory);target=case/'outputs/client_report'
    receipt=_read(target/'CLIENT_REPORT_DELIVERY.json')
    if receipt.get('renderer')!='againward_agent_composition_v1':
        raise ValueError('Le livrable nominal exige une composition éditoriale Codex.')
    model_path=case/str(receipt.get('model_ref',''))
    design_path=case/str(receipt.get('design_ref',''))
    for path in (model_path,design_path):
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(target.resolve()):
            raise ValueError('Modèle ou plan absent/hors des artefacts autorisés.')
    checked=validate_report_design(case,_read(model_path),model_path,_read(design_path))
    if receipt.get('semantic_sha256')!=checked['semantic_sha256'] or human_review.get('report_semantic_sha256')!=checked['semantic_sha256']:
        raise ValueError('Contenu substantif changé ou non approuvé : nouvelle revue humaine requise.')
    pdf=target/'client_report.pdf'
    if not pdf.is_file() or hashlib.sha256(pdf.read_bytes()).hexdigest()!=receipt.get('pdf_sha256'):
        raise ValueError('PDF final absent ou modifié après validation.')
    # The receipt is not an authority for PDF bytes: replay the approved composition.
    import tempfile
    with tempfile.TemporaryDirectory(dir=case/'outputs') as temporary:
        replay=render_designed_report(case,_read(model_path),model_path,_read(design_path),output_directory=temporary)
        if replay['pdf_sha256']!=receipt['pdf_sha256']:
            raise ValueError('PDF non reproductible depuis la composition et les claims autorisés.')
    visual=_read(target/'REPORT_VISUAL_REVIEW.json')
    if (visual.get('pdf_sha256')!=receipt['pdf_sha256'] or visual.get('reviewer_role')!='CODEX'
            or set(visual.get('checks',{}))!=VISUAL_CHECKS or any(v is not True for v in visual['checks'].values())):
        raise ValueError('Inspection visuelle absente ou périmée.')
    return {'semantic_sha256':checked['semantic_sha256'],'pdf_sha256':receipt['pdf_sha256']}
