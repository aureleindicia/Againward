import copy
import json
import pytest
from workspace.generate_goal_c_1_fixtures import generate
from report_design import (SCHEMA, validate_report_design, render_designed_report,
    validate_report_delivery_artifacts, record_visual_review, VISUAL_CHECKS)


def block(ref,kind='FINDING',box=None,size=11):
    return {'component':kind,'content_ref':ref,'box':box or [45,80,500,650],
        'font_size':size,'emphasis':'NORMAL'}


def simple_design(model):
    aid=model['decision_cards'][0]['action_ref']
    return {'schema_version':SCHEMA,'selected_findings':model['decision_cards'][0]['claim_refs']['finding_ids'],
        'omitted_actions':{},'pages':[
            {'intent':'EXECUTIVE_SUMMARY','blocks':[block('executive',box=[45,80,500,150]),block(aid+':what_we_found',box=[45,250,500,150]),block(aid+':decision','DECISION',box=[45,420,500,120])]},
            {'intent':'LIMITATION','blocks':[block(aid+':uncertainty','LIMITATION',box=[45,80,500,160]),block('notice','METHODOLOGY',box=[45,600,500,130])]}]}


@pytest.fixture
def report_case(tmp_path):
    case=generate(tmp_path)['C-A'];path=case/'outputs/client_report/CLIENT_REPORT_MODEL.json'
    model=json.loads(path.read_text());model['charts']=[];path.write_text(json.dumps(model))
    return case,model,path,simple_design(model)


def test_agent_composition_changes_geometry_not_semantic_hash(report_case):
    case,m,path,d=report_case;before=validate_report_design(case,m,path,d)
    changed=copy.deepcopy(d);changed['pages'][0]['blocks'][0]['box'][1]+=10;changed['pages'][0]['blocks'][0]['font_size']=12
    after=validate_report_design(case,m,path,changed)
    assert before['semantic_sha256']==after['semantic_sha256']
    result=render_designed_report(case,m,path,changed)
    assert result['page_count']==2 and (case/'outputs/client_report/client_report.pdf').read_bytes().startswith(b'%PDF')


@pytest.mark.parametrize('attack',['free_number','unknown_finding','unknown_ref','verified_saving','hidden_limit','overlap'])
def test_design_cannot_introduce_or_strengthen_claims(report_case,attack):
    case,m,path,d=report_case
    if attack=='free_number':d['pages'][0]['blocks'][0]['text']='12400 euros économisés'
    if attack=='unknown_finding':d['selected_findings']=['F-MISSING']
    if attack=='unknown_ref':d['pages'][0]['blocks'][0]['content_ref']='missing'
    if attack=='verified_saving':m['decision_cards'][0]['economic_impact']['saving_status']='VERIFIED'
    if attack=='hidden_limit':d['pages'][1]['blocks'].pop(0)
    if attack=='overlap':d['pages'][0]['blocks'][1]['box']=d['pages'][0]['blocks'][0]['box']
    with pytest.raises(ValueError):render_designed_report(case,m,path,d)


def test_substantive_content_change_invalidates_human_review(report_case):
    case,m,path,d=report_case;result=render_designed_report(case,m,path,d)
    # A fixture attestation tests binding; it is not a human approval of a real client.
    visual={'reviewer_role':'CODEX','pdf_sha256':result['pdf_sha256'],
        'checks':dict.fromkeys(VISUAL_CHECKS,True),'notes':'Synthetic gate test only.'}
    record_visual_review(case,visual)
    human={'report_semantic_sha256':result['semantic_sha256']}
    assert validate_report_delivery_artifacts(case,human)
    m['executive_summary']['message']='Une vérification reste nécessaire avant de conclure.'
    path.write_text(json.dumps(m));render_designed_report(case,m,path,d)
    with pytest.raises(ValueError,match='substantif'):validate_report_delivery_artifacts(case,human)


def test_chart_pixels_sources_findings_and_method_must_be_reproducible(tmp_path):
    case=generate(tmp_path)['C-A'];path=case/'outputs/client_report/CLIENT_REPORT_MODEL.json'
    m=json.loads(path.read_text());m['charts'][0]['finding_refs']=m['decision_cards'][0]['claim_refs']['finding_ids']
    d=simple_design(m);d['pages'].append({'intent':'EVIDENCE_CHART','blocks':[block('chart:CHART-01','EVIDENCE_CHART')]})
    assert validate_report_design(case,m,path,d)
    m['charts'][0]['method']='SMOOTHED_UNDOCUMENTED'
    with pytest.raises(ValueError,match='graphique'):validate_report_design(case,m,path,d)
    m['charts'][0]['method']='FULL_WINDOW_PIXEL_MEAN_WITH_EXTREMA'
    image=path.parent/m['charts'][0]['relative_path'];image.write_bytes(image.read_bytes()+b'changed')
    with pytest.raises(ValueError,match='reproductible'):validate_report_design(case,m,path,d)


def test_receipt_cannot_launder_an_arbitrary_pdf(report_case):
    import hashlib
    case,m,path,d=report_case;result=render_designed_report(case,m,path,d)
    pdf=case/'outputs/client_report/client_report.pdf';pdf.write_bytes(pdf.read_bytes()+b'Unauthorized content')
    receipt_path=case/'outputs/client_report/CLIENT_REPORT_DELIVERY.json'
    receipt=json.loads(receipt_path.read_text());receipt['pdf_sha256']=hashlib.sha256(pdf.read_bytes()).hexdigest()
    receipt_path.write_text(json.dumps(receipt))
    record_visual_review(case,{'reviewer_role':'CODEX','pdf_sha256':receipt['pdf_sha256'],
        'checks':dict.fromkeys(VISUAL_CHECKS,True),'notes':'Synthetic forged attestation for an adversarial test.'})
    with pytest.raises(ValueError,match='non reproductible'):
        validate_report_delivery_artifacts(case,{'report_semantic_sha256':result['semantic_sha256']})


def test_display_reduction_preserves_a_short_peak(tmp_path):
    from client_delivery import _write_operation_context_chart, _png_rgb
    import zlib
    path=tmp_path/'peak.png';values=[10.0]*2000;values[999]=1000.0
    _write_operation_context_chart(values,None,path,title='Pic à préserver')
    width,height,data=_png_rgb(path);pixels=zlib.decompress(data)
    # The min/max envelope still reaches the upper portion of the full-scale plot.
    blue=bytes((31,119,180))
    assert any(pixels[(y*width+x)*3:(y*width+x)*3+3]==blue for y in range(20,60) for x in range(52,width-18))


def test_existing_delivery_gate_accepts_only_current_semantic_and_visual_review(report_case):
    from tests.test_case_lifecycle import _hypothesis, _review
    from energy_mvp.case_lifecycle import evaluate_delivery_gate
    case,m,path,d=report_case;root=case/'investigation'
    (root/'investigation.json').write_text(json.dumps({'ground_truth_used':False,'hypotheses':[{**_hypothesis('A_CONSERVER_AVEC_RESERVES',request=False), 'terminal_status':'non_identifiable','why_no_further_request':'Limite explicitement non identifiable dans ce test de gate.'}]}))
    (root/'review.json').write_text(json.dumps(_review()))
    (root/'report.md').write_text('# Synthèse de test\n')
    (root/'trace.json').write_text(json.dumps({'entries':[]}))
    result=render_designed_report(case,m,path,d)
    human={'status':'approved','approved_for_delivery':True,'reviewer_role':'TEST_HUMAN',
        'reviewed_at_utc':'2026-09-09T00:00:00+00:00','report_semantic_sha256':result['semantic_sha256']}
    (root/'human_review.json').write_text(json.dumps(human))
    assert not evaluate_delivery_gate(case)['ready_for_delivery']
    record_visual_review(case,{'reviewer_role':'CODEX','pdf_sha256':result['pdf_sha256'],
        'checks':dict.fromkeys(VISUAL_CHECKS,True),'notes':'Test attestation only; visual inspection is not inferred.'})
    gate=evaluate_delivery_gate(case)
    assert gate['ready_for_delivery'], gate['blocking_reasons']
    styled=copy.deepcopy(d);styled['pages'][0]['blocks'][0]['font_size']=12
    styled_result=render_designed_report(case,m,path,styled)
    assert styled_result['semantic_sha256']==human['report_semantic_sha256']
    record_visual_review(case,{'reviewer_role':'CODEX','pdf_sha256':styled_result['pdf_sha256'],
        'checks':dict.fromkeys(VISUAL_CHECKS,True),'notes':'Synthetic aesthetic rerender review.'})
    assert evaluate_delivery_gate(case)['ready_for_delivery']
    m['executive_summary']['message']='Le résultat doit être réexaminé.';path.write_text(json.dumps(m))
    assert not evaluate_delivery_gate(case)['ready_for_delivery']
    receipt=json.loads((case/'outputs/client_report/CLIENT_REPORT_DELIVERY.json').read_text())
    assert receipt['approved_for_delivery'] is False
    assert receipt['status']=='BLOCKED_BY_DELIVERY_GATE'
    render_designed_report(case,m,path,d)
    assert not evaluate_delivery_gate(case)['ready_for_delivery']


def test_editorial_heading_is_sourced_and_substantive(report_case):
    case,m,path,d=report_case
    before=validate_report_design(case,m,path,d)['semantic_sha256']
    m['editorial_headings']={'main':{'claim_type':'EDITORIAL_HEADING',
        'text':'Un écart à vérifier sur le terrain',
        'finding_refs':m['decision_cards'][0]['claim_refs']['finding_ids']}}
    d['pages'][0]['blocks'][1]['heading_ref']='main'
    after=validate_report_design(case,m,path,d)['semantic_sha256']
    assert before != after
    m['editorial_headings']['main']['text']='12400 euros économisés'
    with pytest.raises(ValueError):validate_report_design(case,m,path,d)
