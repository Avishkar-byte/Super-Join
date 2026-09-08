"""Date parsing and interval tests."""

import pytest
from app.canonical.dates import parse_date_interval, are_intervals_disjoint


def test_fy24_parsing():
    res = parse_date_interval("FY24")
    assert res["start"] == "2023-04-01"
    assert res["end"] == "2024-03-31"
    assert res["fy_convention_assumed"] is True


def test_fy_range_parsing():
    res = parse_date_interval("FY2023-24")
    assert res["start"] == "2023-04-01"
    assert res["end"] == "2024-03-31"


def test_year_ended_march_31():
    res = parse_date_interval("year ended March 31, 2024")
    assert res["start"] == "2023-04-01"
    assert res["end"] == "2024-03-31"


def test_quarter_parsing():
    res = parse_date_interval("Q3 FY24")
    assert res["start"] == "2023-10-01"
    assert res["end"] == "2023-12-31"


def test_point_in_time():
    res = parse_date_interval("as at 31.03.2024")
    assert res["start"] == "2024-03-31"
    assert res["end"] == "2024-03-31"
    assert res["fy_convention_assumed"] is False


def test_disjoint_intervals():
    int_a = parse_date_interval("FY23")
    int_b = parse_date_interval("FY24")
    assert are_intervals_disjoint(int_a, int_b) is True
