"""Removing a quoted ISO currency annotation never chooses or changes an amount."""
import pytest

from againward.documents.model_protocol import normalize_row


@pytest.mark.parametrize("field", ["net_amount", "unit_rate", "rate", "allocated_amount"])
@pytest.mark.parametrize("value,quote,expected", [
    ("78.25 GBP", "Total net 78.25 GBP.", "78.25"),
    ("EUR 31.20", "Daily rate EUR 31.20 per item.", "31.20"),
])
def test_exact_money_annotation_keeps_the_numeric_value(field, value, quote, expected):
    row = {"semantic_type": field, "value": value, "raw_observed_value": quote}
    normalized = normalize_row(row, visual=False, rental=True)
    assert normalized["value"] == expected
    assert normalized["raw_observed_value"] == quote
    assert normalized["value_type"] == "DECIMAL"
    assert normalize_row(normalized, visual=False, rental=True) == normalized


@pytest.mark.parametrize("value,quote", [
    ("78.25 USD", "Total net 78.25 GBP."),
    ("78.25 GBP", "Total net 87.25 GBP."),
    ("78.25 GBP", "Fee 78.25 GBP, other fee 78.25 GBP."),
    ("78.25 XYZ", "Total 78.25 XYZ."),
    ("1,234 EUR", "Total 1,234 EUR."),
    ("78.25 GBP or 80.00 GBP", "78.25 GBP or 80.00 GBP"),
    ("$78.25", "$78.25"),
    ("78.25 EUR", "No amount printed"),
])
def test_ambiguous_or_contradictory_annotation_is_not_repaired(value, quote):
    row = {"semantic_type": "net_amount", "value": value, "raw_observed_value": quote}
    assert normalize_row(row, visual=False, rental=True)["value"] == value


def test_quantity_and_currency_are_not_treated_as_monetary_amounts():
    for field in ("quantity", "currency", "discount_fraction"):
        row = {"semantic_type": field, "value": "12.00 EUR", "raw_observed_value": "12.00 EUR"}
        assert normalize_row(row, visual=False, rental=True)["value"] == "12.00 EUR"


def test_visual_annotation_preserves_the_original_transcription():
    row = {"semantic_type": "net_amount", "value": "31.20 EUR", "visible_text": "Net 31.20 EUR", "page": 1}
    normalized = normalize_row(row, visual=True, rental=True)
    assert normalized["value"] == "31.20"
    assert normalized["visible_text"] == row["visible_text"]
