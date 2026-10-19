import pandas as pd
import pytest

from conftest import FIELDS, to_frame
from saferoute.data.validate import (
    EXPECTED_COLUMNS,
    SchemaError,
    borough_status,
    check_schema,
    null_percentage,
    parse_crash_date,
    parse_crash_time,
    require_columns,
)


def test_expected_columns_match_test_schema():
    assert list(EXPECTED_COLUMNS) == FIELDS


def test_schema_ok():
    r = check_schema(to_frame([]))
    assert r.is_valid and r.is_empty and r.order_matches
    assert r.missing_columns == [] and r.unexpected_columns == []


def test_missing_and_unexpected_columns_are_reported():
    df = to_frame([]).drop(columns=["latitude", "borough"]).assign(extra=pd.Series(dtype="string"))
    r = check_schema(df)
    assert r.missing_columns == ["borough", "latitude"]
    assert r.unexpected_columns == ["extra"]
    assert not r.is_valid and not r.order_matches
    with pytest.raises(SchemaError, match="borough, latitude"):
        require_columns(df)


def test_reordered_columns_are_valid_but_flagged():
    df = to_frame([])[list(reversed(FIELDS))]
    r = require_columns(df)
    assert r.is_valid and not r.order_matches


@pytest.mark.parametrize("missing,total,expected", [(0, 0, 0.0), (1, 3, 33.3333), (3, 3, 100.0), (0, 10, 0.0)])
def test_null_percentage(missing, total, expected):
    assert null_percentage(missing, total) == pytest.approx(expected)


@pytest.mark.parametrize("missing,total", [(-1, 3), (4, 3), (0, -1)])
def test_null_percentage_rejects_invalid_counts(missing, total):
    with pytest.raises(ValueError):
        null_percentage(missing, total)


def test_parse_crash_date():
    s = pd.Series(["2020-01-31T00:00:00.000", " 2021-02-28T00:00:00.000 ", "2021-02-30T00:00:00.000",
                   "31/01/2020", "", None])
    parsed = parse_crash_date(s)
    assert parsed.iloc[0] == pd.Timestamp("2020-01-31")
    assert parsed.iloc[1] == pd.Timestamp("2021-02-28")   # baştaki/sondaki boşluk tolere edilir
    assert parsed.iloc[2:].isna().all()                    # var olmayan tarih, farklı biçim, boş


def test_parse_crash_time():
    s = pd.Series(["0:00", "09:05", "23:59", "24:00", "12:60", "1230", "", None])
    t = parse_crash_time(s)
    assert t["valid"].tolist() == [True, True, True, False, False, False, False, False]
    assert t["hour"].iloc[1] == 9 and t["minute"].iloc[1] == 5
    assert t["hour"].iloc[3:].isna().all()


def test_borough_status():
    s = pd.Series(["BROOKLYN", "staten island", " QUEENS ", "NEW JERSEY", "", "   ", None])
    assert borough_status(s).tolist() == ["valid", "valid", "valid", "unexpected", "missing", "missing", "missing"]
