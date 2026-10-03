"""Source variations are original facts, separate from post-run financial truth."""
import pytest
from pypdf import PdfReader

from benchmarks.energy_billing.frontier_cases import SCENARIOS, make_sources
from benchmarks.energy_billing.investigator_gate import run


@pytest.mark.parametrize('scenario', SCENARIOS)
def test_frontier_case_native_originals_keep_scope_and_no_oracle(tmp_path, scenario):
    source = tmp_path / 'input'
    make_sources(source, scenario)
    texts = {p.name: '\n'.join(page.extract_text() for page in PdfReader(p).pages) for p in source.glob('*.pdf')}
    assert len(texts) == (3 if scenario in {'decorative', 'competing_tariffs'} else 2)
    assert all('expected_cents' not in t and '27.08' not in t and '165.00' not in t for t in texts.values())
    if scenario == 'decorative':
        assert 'NOTE LOGISTIQUE' in texts['annexe.pdf'] and 'kWh' not in texts['annexe.pdf']
    elif scenario == 'competing_tariffs':
        assert '0.145 EUR/kWh' in texts['conditions.pdf'] and '0.120 EUR/kWh' in texts['contrat.pdf']
        assert 'commerciales acceptees' in texts['conditions.pdf']
        assert 'remplace' not in texts['conditions.pdf']
    elif scenario == 'two_pdl':
        assert '98765432109876' in texts['facture.pdf'] and '01234567890123' in texts['facture.pdf']
        assert 'globale des deux sites' in texts['facture.pdf']


def test_frontier_gate_does_not_change_sources_during_continuation(tmp_path):
    with pytest.raises(ValueError, match='preserved continuation'):
        run('UNUSED', tmp_path / 'output', scenario='decorative', continue_from=tmp_path / 'prior')
    assert not (tmp_path / 'output').exists()
