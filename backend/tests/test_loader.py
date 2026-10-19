import os
import stat

import pandas as pd
import pytest

from conftest import FakeSession, make_row
from saferoute.data.download import download_snapshot
from saferoute.data.loader import IntegrityError, latest_snapshot, load_raw, verify_snapshot

QUIET = {"log": lambda _: None, "sleep": lambda _: None}


def _snapshot(tmp_path, rows, name="snapshot_20260101T000000Z"):
    target = tmp_path / "h9gi-nx95" / name
    return download_snapshot(snapshot_dir=target, page_size=3, session=FakeSession(rows), **QUIET)


def test_load_raw_roundtrip_keeps_text_and_nulls(tmp_path, rows):
    snap = _snapshot(tmp_path, rows)
    df = load_raw(snap)
    assert len(df) == 7 and df.shape[1] == 29
    assert df.loc[0, "latitude"] == "40.7208537"
    assert pd.isna(df.loc[1, "latitude"])          # boş alan -> null
    assert df.loc[4, "borough"] == "   "            # yalnız boşluk korunur (null'a çevrilmez)


def test_na_like_strings_are_preserved_as_data(tmp_path):
    rows = [make_row(collision_id="1", on_street_name="NA", off_street_name="NULL", borough="N/A")]
    df = load_raw(_snapshot(tmp_path, rows))
    assert df.loc[0, "on_street_name"] == "NA"
    assert df.loc[0, "off_street_name"] == "NULL"
    assert df.loc[0, "borough"] == "N/A"


def test_multiline_quoted_values_count_as_one_row(tmp_path):
    rows = [make_row(collision_id="1", on_street_name="LINE1\nLINE2"), make_row(collision_id="2")]
    snap = _snapshot(tmp_path, rows)
    df = load_raw(snap)
    assert len(df) == 2
    assert df.loc[0, "on_street_name"] == "LINE1\nLINE2"


def test_tampering_is_detected(tmp_path, rows):
    snap = _snapshot(tmp_path, rows)
    part = snap / "part-00000.csv"
    os.chmod(part, stat.S_IWRITE | stat.S_IREAD)
    part.write_bytes(part.read_bytes().replace(b"MANHATTAN", b"MANHATTAX"))
    with pytest.raises(IntegrityError):
        verify_snapshot(snap)
    with pytest.raises(IntegrityError):
        load_raw(snap)


def test_latest_snapshot_picks_newest_completed(tmp_path, rows):
    _snapshot(tmp_path, rows, "snapshot_20260101T000000Z")
    newest = _snapshot(tmp_path, rows, "snapshot_20260201T000000Z")
    (tmp_path / "h9gi-nx95" / "snapshot_20260301T000000Z").mkdir()  # tamamlanmamış
    assert latest_snapshot(tmp_path) == newest


def test_latest_snapshot_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        latest_snapshot(tmp_path)
