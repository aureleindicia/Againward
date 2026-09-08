import copy
import pytest
from tests.test_value_map import case_packet, save, time_record
from pilot_learning import build_pilot_learning_review,render_pilot_learning_review,export_authorized_pilot_metrics,aggregate_pilot_metrics


def test_review_keeps_unknown_and_can_use_investigation_without_monetizing(case_packet):
    case,packet=case_packet;save(case,packet,time_record())
    review=build_pilot_learning_review(case,{'investigation_value_ref':'V1'})
    assert review['metrics']['client_hours_potentially_avoided']==8
    assert review['metrics']['useful_finding'] is None
    assert review['metrics']['economic_value_eur_per_year'] is None
    assert 'UNKNOWN' in render_pilot_learning_review(review)


def test_export_requires_authorization_and_drops_client_content(case_packet):
    case,p=case_packet;save(case,p,time_record());review=build_pilot_learning_review(case,{})
    with pytest.raises(ValueError):export_authorized_pilot_metrics(review,authorization={},pilot_id='PILOT-1234567890abcdef')
    export=export_authorized_pilot_metrics(review,authorization={'authorized':True,'deidentification_reviewed':True,'authorization_ref':'client-local-consent','reviewer':'human-local-name'},pilot_id='PILOT-1234567890abcdef')
    assert 'human-local-name' not in str(export) and 'client-local-consent' not in str(export) and 'GBE' not in str(export)
    result=aggregate_pilot_metrics([export]);assert result['commercial_conclusion'] is None
    assert result['metrics']['useful_finding']=={'known':0,'unknown':1,'percent':None}
    with pytest.raises(ValueError):aggregate_pilot_metrics([export,export])


def test_aggregation_cannot_promote_missing_or_unverified_findings(case_packet):
    case,p=case_packet;save(case,p,time_record())
    review=build_pilot_learning_review(case,{'useful_negative_conclusion':{'value':True,'source_refs':['GBE-V']}})
    export=export_authorized_pilot_metrics(review,authorization={'authorized':True,'deidentification_reviewed':True,'authorization_ref':'consent','reviewer':'reviewer'},pilot_id='PILOT-1234567890abcdef')
    assert aggregate_pilot_metrics([export])['metrics']['useful_negative_conclusion']['percent']==100
    assert aggregate_pilot_metrics([export])['field_verified_findings_percent'] is None
    bad=copy.deepcopy(export);bad['metrics']['findings_field_verified']=10
    with pytest.raises(ValueError):aggregate_pilot_metrics([bad])


def test_export_rejects_free_client_text_in_basis(case_packet):
    case,p=case_packet;save(case,p,time_record())
    review=build_pilot_learning_review(case,{})
    review['provenance']['energy_basis']='Confidential client identity'
    with pytest.raises(ValueError,match='vocabulaire fermé'):
        export_authorized_pilot_metrics(review,authorization={'authorized':True,'deidentification_reviewed':True,
            'authorization_ref':'consent','reviewer':'reviewer'},pilot_id='PILOT-1234567890abcdef')
