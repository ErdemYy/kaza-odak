import hashlib
import os

import pytest

from conftest import FakeSession, read_manifest
from saferoute.data.download import DownloadError, download_snapshot

QUIET = {"log": lambda _: None, "sleep": lambda _: None}


def test_full_download_writes_parts_manifest_and_checksums(tmp_path, rows):
    snap = download_snapshot(snapshot_dir=tmp_path / "s", page_size=3, session=FakeSession(rows), **QUIET)
    m = read_manifest(snap)

    assert m["row_count"] == 7
    assert m["column_count"] == 29
    assert [p["rows"] for p in m["parts"]] == [3, 3, 1]
    assert m["status"] == "complete" and m["warnings"] == []
    assert not (snap / "_progress.json").exists()
    assert not list(snap.glob("*.partial"))

    combined = hashlib.sha256()
    for p in m["parts"]:
        data = (snap / p["file"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == p["sha256"]
        combined.update(data)
    assert combined.hexdigest() == m["combined_sha256"]


def test_raw_files_are_read_only(tmp_path, rows):
    snap = download_snapshot(snapshot_dir=tmp_path / "s", page_size=3, session=FakeSession(rows), **QUIET)
    for path in [*snap.glob("part-*.csv"), snap / "manifest.json"]:
        assert not os.access(path, os.W_OK)


def test_pagination_is_stable_and_handles_exact_multiple(tmp_path, rows):
    session = FakeSession(rows[:6])
    snap = download_snapshot(snapshot_dir=tmp_path / "s", page_size=3, session=session, **QUIET)
    assert [p["rows"] for p in read_manifest(snap)["parts"]] == [3, 3]
    assert [c["$offset"] for c in session.csv_calls] == [0, 3, 6]
    assert all(c["$order"] == ":id" for c in session.csv_calls)


def test_transient_failures_are_retried_with_backoff(tmp_path, rows):
    waits = []
    session = FakeSession(rows, failures=[503, "conn", "truncate"])
    snap = download_snapshot(snapshot_dir=tmp_path / "s", page_size=10, session=session,
                             backoff=1.0, sleep=waits.append, log=lambda _: None)
    m = read_manifest(snap)
    assert m["row_count"] == 7
    assert m["parts"][0]["attempts"] == 4
    assert waits == [1.0, 2.0, 4.0]


def test_exhausted_retries_leave_resumable_state(tmp_path, rows):
    snap_dir = tmp_path / "s"
    # İlk sayfa başarılı, ikinci sayfa üç denemenin üçünde de 503.
    failing = FakeSession(rows, failures=[None, 503, 503, 503])
    with pytest.raises(DownloadError, match="3 denemede"):
        download_snapshot(snapshot_dir=snap_dir, page_size=3, session=failing, max_retries=3, **QUIET)

    assert (snap_dir / "_progress.json").exists()
    assert not (snap_dir / "manifest.json").exists()
    assert not list(snap_dir.glob("*.partial"))
    assert sorted(p.name for p in snap_dir.glob("part-*.csv")) == ["part-00000.csv"]

    healthy = FakeSession(rows)
    download_snapshot(snapshot_dir=snap_dir, page_size=3, session=healthy, **QUIET)
    assert read_manifest(snap_dir)["row_count"] == 7
    assert [c["$offset"] for c in healthy.csv_calls] == [3, 6]


def test_client_error_is_not_retried(tmp_path, rows):
    session = FakeSession(rows, failures=[404])
    with pytest.raises(DownloadError, match="yeniden denenemeyen"):
        download_snapshot(snapshot_dir=tmp_path / "s", page_size=3, session=session, **QUIET)
    assert len(session.csv_calls) == 1


def test_schema_change_is_rejected(tmp_path, rows):
    from conftest import FIELDS

    session = FakeSession(rows, csv_fields=list(reversed(FIELDS)))
    with pytest.raises(DownloadError, match="şema"):
        download_snapshot(snapshot_dir=tmp_path / "s", page_size=3, session=session, **QUIET)
    assert not list((tmp_path / "s").glob("*.csv*"))


def test_row_count_mismatch_is_disclosed(tmp_path, rows):
    snap = download_snapshot(snapshot_dir=tmp_path / "s", page_size=3,
                             session=FakeSession(rows, server_count=99), **QUIET)
    m = read_manifest(snap)
    assert m["status"] == "complete_with_warnings"
    assert any("uyuşmuyor" in w for w in m["warnings"])


def test_completed_snapshot_is_never_overwritten(tmp_path, rows):
    snap = download_snapshot(snapshot_dir=tmp_path / "s", page_size=3, session=FakeSession(rows), **QUIET)
    with pytest.raises(DownloadError, match="değiştirilmez"):
        download_snapshot(snapshot_dir=snap, page_size=3, session=FakeSession(rows), **QUIET)


def test_invalid_page_size():
    with pytest.raises(ValueError):
        download_snapshot(page_size=0, session=FakeSession([]), **QUIET)
