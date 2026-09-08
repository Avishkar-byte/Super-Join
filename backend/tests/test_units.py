"""Unit conversion tests for parse_quantity."""

import pytest
from app.canonical.units import parse_quantity


def test_indian_numbering_crore():
    res = parse_quantity("Rs. 1,234.5 crore")
    assert res["value"] == 12345000000.0
    assert res["unit"] == "INR"


def test_indian_numbering_lakh():
    res = parse_quantity("15 lakh")
    assert res["value"] == 1500000.0
    assert res["unit"] == "count"


def test_western_numbering_million():
    res = parse_quantity("USD 2.3 million")
    assert res["value"] == 2300000.0
    assert res["unit"] == "USD"


def test_percentage():
    res = parse_quantity("12.5%")
    assert res["value"] == 12.5
    assert res["unit"] == "percent"


def test_short_crore():
    res = parse_quantity("1.5 crore")
    assert res["value"] == 15000000.0
