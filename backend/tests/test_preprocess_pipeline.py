"""Uçtan uca Faz 2 hattı: katmanlar, satır tutarlılığı, ham veri değişmezliği, idempotentlik."""

import json
import os

import pandas as pd
import pytest

from conftest import FakeSession
from phase2_fixtures import pipeline_rows, write_boundaries_snapshot
from saferoute.data.download import download_snapshot, file_sha256
from saferoute.preprocess.features import FEATURE_SETS
from saferoute.preprocess.pipeline import frame_digest, output_paths, run_pipeline
from saferoute.preprocess.report import write_reports

QUIET = {"log": lambda _: None, "sleep": lambda _: None}


@pytest.fixture
def env(tmp_path):
    raw = download_snapshot(snapshot_dir=tmp_path / "raw" / "h9gi-nx95" / "snapshot_20260101T000000Z",
                            page_size=5, session=FakeSession(pipeline_rows()), **QUIET)
    bounds = write_boundaries_snapshot(tmp_path / "raw")
    kw = dict(snapshot_dir=raw, boundaries_dir=bounds, interim_root=tmp_path / "interim",
              processed_root=tmp_path / "processed", phase1_summary=tmp_path / "yok.json", log=lambda _: None)
    return raw, bounds, kw, tmp_path


def _raw_hashes(raw):
    return {p.name: file_sha256(p) for p in sorted(raw.iterdir())}


def test_layers_and_row_counts(env):
    raw, _, kw, tmp = env
    s = run_pipeline(**kw)
    paths = output_paths(raw.name, tmp / "interim", tmp / "processed")
    interim = pd.read_parquet(paths["interim"])
    processed = pd.read_parquet(paths["processed"])
    assert s["rows"]["raw"] == len(interim) == len(processed) == 12
    assert s["rows"]["eligible_for_spatial_clustering"] == 6  # 1,2,3,4,5,12
    for name, spec in FEATURE_SETS.items():
        f = pd.read_parquet(paths[f"feature:{name}"])
        side = json.loads(paths[f"feature:{name}"].with_name(f"{name}.parquet.json").read_text(encoding="utf-8"))
        assert side["rows"] == len(f) and side["lineage"]["raw_snapshot"] == raw.name
        if spec["level"] == "record":
            expected = 5 if name.endswith("no_midnight") else 6   # 12 numaralı kayıt 00:00
            assert len(f) == expected
        else:
            assert f["weight"].sum() == 6 and len(f) == 5      # 1 ve 2 aynı konumda
    assert s["boroughs"]["recovered_by_polygon"] == 1 and s["boroughs"]["conflicts"] == 1
    # İlçesiz kalanlar: 4 (sınırda belirsiz), 5 (poligon dışı, kıyı), 9-11 (geçerli koordinat yok)
    assert s["boroughs"]["still_missing"] == 5
    assert s["boroughs"]["still_missing_by_reason"] == {"no_valid_coordinate": 3, "ambiguous_boundary": 1,
                                                         "outside_polygons": 1}


def test_feature_column_selection(env):
    raw, _, kw, tmp = env
    run_pipeline(**kw)
    paths = output_paths(raw.name, tmp / "interim", tmp / "processed")
    a = pd.read_parquet(paths["feature:A_dbscan_haversine"])
    assert list(a.columns) == ["collision_id", "lat_rad", "lon_rad"]           # [enlem, boylam] sırası
    b = pd.read_parquet(paths["feature:B_kmeans_projected"])
    assert list(b.columns) == ["collision_id", "x_m", "y_m"]
    for name, spec in FEATURE_SETS.items():
        assert "collision_id" not in spec["features"] and "location_id" not in spec["features"]
        assert not any(f.startswith("number_of_") for f in spec["features"])
        assert "borough_final" not in spec["features"]
    assert (b["x_m"].between(100_000, 900_000)).all()                          # metre, UTM aralığı


def test_raw_data_is_immutable(env):
    raw, bounds, kw, _ = env
    before, bbefore = _raw_hashes(raw), _raw_hashes(bounds)
    s = run_pipeline(**kw)
    assert s["raw_unchanged"] is True
    assert _raw_hashes(raw) == before and _raw_hashes(bounds) == bbefore
    assert all(not os.access(p, os.W_OK) for p in raw.glob("part-*.csv"))


def test_pipeline_is_idempotent(env):
    raw, _, kw, tmp = env
    run_pipeline(**kw)
    paths = output_paths(raw.name, tmp / "interim", tmp / "processed")
    mtime = paths["processed"].stat().st_mtime_ns
    digest = frame_digest(pd.read_parquet(paths["processed"]))
    second = run_pipeline(**kw)
    assert second["skipped"] is True and paths["processed"].stat().st_mtime_ns == mtime
    forced = run_pipeline(**kw, force=True)
    assert forced["skipped"] is False
    assert frame_digest(pd.read_parquet(paths["processed"])) == digest


def test_config_change_invalidates_outputs(env):
    from saferoute.preprocess.settings import PreprocessConfig

    _, _, kw, _ = env
    run_pipeline(**kw)
    changed = run_pipeline(**kw, cfg=PreprocessConfig(nearshore_buffer_m=50.0))
    assert changed["skipped"] is False
    assert changed["coordinates"]["status_counts"]["outside_nyc_nearshore"] == 0
    assert changed["rows"]["eligible_for_spatial_clustering"] == 5


def test_reports_are_generated(env):
    raw, _, kw, tmp = env
    s = run_pipeline(**kw)
    paths = output_paths(raw.name, tmp / "interim", tmp / "processed")
    figs = write_reports(s, pd.read_parquet(paths["processed"]), pd.read_parquet(paths["mapping"]),
                         out_dir=tmp / "reports", docs_dir=tmp / "docs")
    assert len(figs) == 8 and all(p.stat().st_size > 0 for p in figs)
    md = (tmp / "reports" / "ON_ISLEME_RAPORU.md").read_text(encoding="utf-8")
    assert "Poligonla kurtarılan: 1" in md
    fs = (tmp / "docs" / "feature_selection_report.md").read_text(encoding="utf-8")
    assert "`collision_id`" in fs and "A_dbscan_haversine.parquet" in fs
    assert (tmp / "reports" / "vehicle_type_mapping.csv").exists()
