import numpy as np
import pandas as pd
import pytest
from shapely.geometry import MultiPolygon, Polygon, box

from conftest import to_frame
from phase2_fixtures import pipeline_rows, synthetic_boroughs
from saferoute.preprocess.boundaries import (
    BoundaryValidationError,
    CRSMismatchError,
    assert_geographic_nyc,
    ensure_same_crs,
    validate_boundaries,
)
from saferoute.preprocess.geo import COORD_STATUSES, classify_coordinates
from saferoute.preprocess.settings import PreprocessConfig
from saferoute.preprocess.standardize import standardize


@pytest.fixture
def classified():
    interim, _ = standardize(to_frame(pipeline_rows()))
    out, stats = classify_coordinates(interim, synthetic_boroughs(), PreprocessConfig())
    return interim, out.set_index(interim["collision_id"].astype(int)), stats


def test_every_status_is_assigned_exactly_once(classified):
    _, out, _ = classified
    assert set(out["coordinate_quality_status"].cat.categories) == set(COORD_STATUSES)
    expected = {1: "valid_in_boundary", 2: "valid_in_boundary", 3: "valid_in_boundary", 4: "boundary_ambiguous",
                5: "outside_nyc_nearshore", 6: "outside_nyc_far", 7: "zero", 8: "missing", 9: "invalid_range",
                10: "unparseable", 11: "non_finite", 12: "valid_in_boundary"}
    assert out["coordinate_quality_status"].astype(str).to_dict() == expected


def test_boundary_point_handling(classified):
    _, out, stats = classified
    # Ortak kenar: iki ilçeyle kesişir -> belirsiz, ilçe ATANMAZ
    assert out.loc[4, "borough_inferred"] is pd.NA or pd.isna(out.loc[4, "borough_inferred"])
    assert out.loc[4, "borough_inference_status"] == "ambiguous_boundary"
    # Dış kenar: tek ilçe (covered_by) -> geçerli, sınır çizgisi bayrağı
    assert out.loc[12, "borough_inferred"] == "MANHATTAN" and bool(out.loc[12, "on_boundary_line"])
    pc = stats["predicate_comparison_unique_points"]
    assert pc["intersects_or_covered_by_any"] > pc["contains_strict_interior_any"]
    assert pc["multiple_boroughs"] == 1


def test_missing_zero_and_invalid_are_not_geographic(classified):
    _, out, _ = classified
    for cid in (7, 8, 9, 10, 11, 6):
        assert not out.loc[cid, "is_valid_geographic_record"]
        assert not out.loc[cid, "eligible_for_spatial_clustering"]
        assert out.loc[cid, "exclusion_reason"] != "none"
    assert out.loc[7, "exclusion_reason"] == "zero"


def test_outside_points_are_never_assigned_a_borough(classified):
    _, out, _ = classified
    for cid in (5, 6):
        assert pd.isna(out.loc[cid, "borough_inferred"])
        assert out.loc[cid, "borough_inference_status"] == "outside_polygons"
    assert 100 < out.loc[5, "distance_outside_nyc_m"] < 125     # ~111 m
    assert out.loc[6, "distance_outside_nyc_m"] > 5000
    assert out.loc[6, "borough_final"] == "BROOKLYN"             # bildirilen korunur
    assert out.loc[5, "borough_source"] == "none"


def test_nearshore_eligibility_is_configurable():
    interim, _ = standardize(to_frame(pipeline_rows()))
    out, _ = classify_coordinates(interim, synthetic_boroughs(), PreprocessConfig(clustering_include_nearshore=False))
    row = out.set_index(interim["collision_id"].astype(int)).loc[5]
    assert row["is_valid_geographic_record"] and not row["eligible_for_spatial_clustering"]


def test_borough_inference_recovery_and_conflict(classified):
    _, out, _ = classified
    assert out.loc[2, "borough_inferred"] == "MANHATTAN"
    assert out.loc[2, "borough_final"] == "MANHATTAN" and out.loc[2, "borough_source"] == "inferred_polygon"
    # Çelişki: bildirilen QUEENS, poligon BROOKLYN -> sessizce düzeltilmez
    assert bool(out.loc[3, "borough_conflict_flag"])
    assert out.loc[3, "borough_final"] == "QUEENS" and out.loc[3, "borough_source"] == "original"
    assert not out["borough_conflict_flag"].drop(index=3).any()


def test_input_frame_is_not_mutated():
    interim, _ = standardize(to_frame(pipeline_rows()))
    before = interim.copy()
    classify_coordinates(interim, synthetic_boroughs(), PreprocessConfig())
    pd.testing.assert_frame_equal(interim, before)


def test_incorrect_crs_is_detected():
    gdf = synthetic_boroughs()
    with pytest.raises(CRSMismatchError, match="Beklenen CRS"):
        assert_geographic_nyc(gdf.to_crs("EPSG:2263"))
    with pytest.raises(CRSMismatchError, match="tanımsız"):
        assert_geographic_nyc(gdf.set_crs(None, allow_override=True))
    # Metre/fit değerleri yanlışlıkla EPSG:4326 etiketlenmişse kapsam kontrolü yakalar
    mislabeled = gdf.to_crs("EPSG:2263").set_crs("EPSG:4326", allow_override=True)
    with pytest.raises(CRSMismatchError, match="NYC derece aralığında değil"):
        assert_geographic_nyc(mislabeled)
    with pytest.raises(CRSMismatchError, match="uyuşmazlığı"):
        ensure_same_crs(gdf, gdf.to_crs("EPSG:32618"))


def test_validate_boundaries_rejects_bad_inputs():
    gdf = synthetic_boroughs()
    assert validate_boundaries(gdf)["borough_count"] == 5
    with pytest.raises(BoundaryValidationError, match="ilçe kodları"):
        validate_boundaries(gdf.iloc[:4])
    bowtie = MultiPolygon([Polygon([(-74.0, 40.70), (-73.98, 40.72), (-73.98, 40.70), (-74.0, 40.72)])])
    broken = gdf.copy()
    broken.loc[0, "geometry"] = bowtie
    with pytest.raises(BoundaryValidationError, match="Geçersiz geometri"):
        validate_boundaries(broken)
    lines = gdf.copy()
    lines["geometry"] = lines.geometry.boundary
    with pytest.raises(BoundaryValidationError, match="geometri türleri"):
        validate_boundaries(lines)
