"""Zaman, araç, yaralı/ölü, koordinat dönüşümü ve tekrar testleri."""

import numpy as np
import pandas as pd
import pytest

from conftest import make_row, to_frame
from saferoute.preprocess import casualties, coordinates, duplicates, temporal, vehicles
from saferoute.preprocess.settings import PreprocessConfig
from saferoute.preprocess.standardize import location_consistency, map_uniques, parse_coordinate, standardize

CFG = PreprocessConfig()


def _interim(rows):
    return standardize(to_frame(rows))[0]


# ----------------------------------------------------------------- standardizasyon
def test_parse_coordinate_statuses():
    vals, status = parse_coordinate(pd.Series(["40.7", " -73.9 ", "", None, "abc", "inf", "-inf", "nan"]))
    assert status.tolist() == ["parsed", "parsed", "missing", "missing", "unparseable", "non_finite",
                               "non_finite", "non_finite"]
    assert vals[0] == 40.7 and vals[1] == -73.9 and np.isnan(vals[2:]).all()


def test_map_uniques_matches_direct_parse():
    s = pd.Series(["1", "2", None, "1", "x"])
    out = map_uniques(s, lambda u: pd.to_numeric(u, errors="coerce"))
    assert np.array_equal(out, np.array([1.0, 2.0, np.nan, 1.0, np.nan]), equal_nan=True)


def test_location_consistency_handles_socrata_prefix():
    loc = pd.Series(["\n,  \n(40.5, -73.9)", "(40.5, -73.9)", "(1.0, 2.0)", None])
    r = location_consistency(loc, np.array([40.5, 40.5, 40.5, np.nan]), np.array([-73.9, -73.9, -73.9, np.nan]))
    assert r == {"location_present": 3, "location_unparseable": 0, "compared": 3, "equal": 2, "different": 1}


def test_standardize_preserves_rows_and_counts_bad_numbers():
    df, stats = standardize(to_frame([make_row(collision_id="1", number_of_persons_injured="x"),
                                      make_row(collision_id="2", borough="  queens ")]))
    assert len(df) == 2 and stats["casualty_unparseable"]["number_of_persons_injured"] == 1
    assert pd.isna(df.loc[0, "number_of_persons_injured"])
    assert df.loc[1, "borough_original"] == "QUEENS"
    assert "location" not in df.columns


# ----------------------------------------------------------------- zaman
def test_cyclical_hour_encoding_wraps_midnight():
    s, c = temporal.cyclical(np.array([23 + 59 / 60, 1 / 60, 0.0, 12.0, 6.0]), 24)
    dist = lambda i, j: np.hypot(s[i] - s[j], c[i] - c[j])
    assert dist(0, 1) < 0.01                       # 23:59 ile 00:01 çok yakın
    assert dist(2, 3) == pytest.approx(2.0)         # 00:00 ile 12:00 karşıt
    assert s[4] == pytest.approx(1.0) and c[4] == pytest.approx(0.0, abs=1e-12)
    assert np.allclose(s**2 + c**2, 1.0)


def test_month_encoding_december_close_to_january():
    s, c = temporal.cyclical(np.array([11, 0, 6]), 12)  # (ay-1)
    assert np.hypot(s[0] - s[1], c[0] - c[1]) < np.hypot(s[0] - s[2], c[0] - c[2])


def test_temporal_features_and_midnight_flag():
    rows = [make_row(collision_id=str(i), crash_date="2021-03-06T00:00:00.000", crash_time=t)
            for i, t in enumerate(["0:00", "00:01", "12:00", "23:59", "25:00"])]
    out = temporal.add_temporal_features(_interim(rows), CFG)
    assert out["midnight_suspect_flag"].tolist() == [True, False, False, False, False]
    assert out["time_period"].astype(object).tolist()[:4] == ["night", "night", "afternoon", "evening"]
    assert pd.isna(out["time_period"].iloc[4]) and np.isnan(out["hour_sin"].iloc[4])
    assert out["day_of_week"].iloc[0] == 5 and bool(out["is_weekend"].iloc[0])  # 2021-03-06 Cumartesi
    assert out[["crash_year", "crash_month", "crash_day"]].iloc[0].tolist() == [2021, 3, 6]


def test_minute_heaping_ratio():
    rows = [make_row(collision_id=str(i), crash_time=t) for i, t in
            enumerate(["0:00"] * 6 + ["0:01", "0:02", "1:00", "1:05"])]
    h = temporal.minute_heaping(_interim(rows))
    # 00:00 = 6 kayıt; 0:01..0:59 toplam 2 kayıt -> ortalama 2/59 -> oran 177
    assert h["per_hour"]["0"]["on_the_hour"] == 6 and h["per_hour"]["0"]["ratio"] == pytest.approx(177.0)
    assert h["per_hour"]["1"]["ratio"] == pytest.approx(59.0)


# ----------------------------------------------------------------- araç
@pytest.mark.parametrize("label,category,rule", [
    ("Sedan", "PASSENGER_CAR", "passenger_car"),
    ("  station wagon/sport utility vehicle ", "SUV", "suv"),
    ("E-Bike", "E_MICROMOBILITY", "e_micromobility"),
    ("BIKE", "BICYCLE", "bicycle"),
    ("DIRT BIKE", "MOTORCYCLE", "motorcycle"),
    ("FDNY TRUCK", "EMERGENCY", "emergency"),
    ("SCHOOL BUS", "BUS", "bus"),
    ("PICK-UP TRUCK", "TRUCK_COMMERCIAL", "truck_commercial"),
    ("REFRIGERATED VAN", "TRUCK_COMMERCIAL", "refrigerated_truck"),
    ("Van", "VAN", "van"),
    ("UNKNOWN", "UNKNOWN", "unknown_tokens"),
    ("UNK", "UNKNOWN", "unknown_tokens"),
    ("OTHER", "OTHER", "other_explicit"),
    ("SCOOTER", "OTHER", "ambiguous_scooter"),
    ("XYZ123", "OTHER", "unmatched"),
])
def test_vehicle_categorize(label, category, rule):
    assert vehicles.categorize(vehicles.normalize_label(label)) == (category, rule)


def test_unknown_vehicle_inputs():
    assert vehicles.categorize(None) == ("UNKNOWN", "missing")
    assert vehicles.normalize_label("   ") is None
    assert vehicles.normalize_label("4  dr   sedan") == "4 DR SEDAN"


def test_mapping_table_and_involves_flags():
    df = _interim([make_row(collision_id="1", vehicle_type_code1="Sedan", vehicle_type_code2="BIKE"),
                   make_row(collision_id="2", vehicle_type_code1="sedan ", vehicle_type_code2="mystery thing"),
                   make_row(collision_id="3")])
    m = vehicles.build_mapping_table(df)
    sedan = m[m["normalized"] == "SEDAN"].iloc[0]
    assert sedan["count"] == 2 and sedan["raw_variants"] == 2  # "Sedan" ve "sedan" -> tek normalize etiket
    assert m.loc[m["normalized"] == "MYSTERY THING", "rule"].item() == "unmatched"
    f = vehicles.add_vehicle_features(df, m)
    assert f["involves_bicycle"].tolist() == [True, False, False]
    assert f["involves_passenger_car"].tolist() == [True, True, False]
    assert f["vehicle_count_reported"].tolist() == [2, 2, 0]
    assert pd.isna(f["vehicle_category_1"].iloc[2])
    s = vehicles.mapping_summary(m, raw_distinct=4)
    assert s["unmatched_labels"] == 1 and s["category_count"] == 3


# ----------------------------------------------------------------- yaralı / ölü
def test_casualty_flags_never_overwrite_raw():
    rows = [
        make_row(collision_id="1", number_of_persons_injured="1", number_of_pedestrians_injured="1"),
        make_row(collision_id="2", number_of_persons_injured="3", number_of_motorist_injured="1"),
        make_row(collision_id="3", number_of_persons_injured="0", number_of_cyclist_injured="2"),
        make_row(collision_id="4", number_of_persons_injured=None, number_of_cyclist_injured="1"),
        make_row(collision_id="5", number_of_persons_injured="-1"),
        make_row(collision_id="6", number_of_persons_killed="1", number_of_pedestrians_killed="1"),
    ]
    df = _interim(rows)
    before = df["number_of_persons_injured"].copy()
    f = casualties.add_casualty_features(df)
    assert f["injury_data_quality_flag"].astype(str).tolist() == [
        "ok", "total_gt_components", "total_lt_components", "total_missing", "negative_value", "ok"]
    assert f["has_reported_injury"].tolist() == [True, True, True, True, False, False]
    assert f["has_reported_fatality"].tolist() == [False] * 5 + [True]
    assert f["fatality_data_quality_flag"].astype(str).iloc[5] == "ok"
    pd.testing.assert_series_equal(df["number_of_persons_injured"], before)


# ----------------------------------------------------------------- koordinat dönüşümleri
def test_haversine_known_distances():
    assert coordinates.haversine_m(0, 0, 1, 0) == pytest.approx(111_195.08, rel=1e-6)   # 1° enlem
    d = coordinates.haversine_m(40.7, -74.0, 40.7, -73.0)
    assert d == pytest.approx(111_195.08 * np.cos(np.radians(40.7)), rel=2e-3)
    assert coordinates.haversine_m(40.7, -74.0, 40.7, -74.0) == 0.0


def test_radian_column_order_matches_sklearn_haversine():
    from sklearn.metrics.pairwise import haversine_distances

    lat, lon = np.array([40.70, 40.80]), np.array([-74.00, -73.90])
    X = coordinates.to_radians(lat, lon)
    assert X[0, 0] == pytest.approx(np.radians(40.70)) and X[0, 1] == pytest.approx(np.radians(-74.00))
    d_sklearn = haversine_distances(X)[0, 1] * coordinates.EARTH_RADIUS_M
    assert d_sklearn == pytest.approx(coordinates.haversine_m(40.70, -74.00, 40.80, -73.90), rel=1e-9)
    # Ters sıra (boylam, enlem) farklı mesafe verir -> sıra hatası yakalanır
    assert haversine_distances(X[:, ::-1])[0, 1] * coordinates.EARTH_RADIUS_M != pytest.approx(d_sklearn, rel=1e-3)


def test_eps_meter_radian_conversion():
    assert coordinates.meters_to_radians(100) == pytest.approx(100 / 6_371_008.8)
    assert coordinates.radians_to_meters(coordinates.meters_to_radians(250)) == pytest.approx(250)
    with pytest.raises(ValueError):
        coordinates.meters_to_radians(0)


def test_projection_produces_meters_and_preserves_distances():
    x, y = coordinates.project(np.array([0.0]), np.array([-75.0]))
    assert x[0] == pytest.approx(500_000.0) and y[0] == pytest.approx(0.0, abs=1e-6)  # UTM 18N merkez meridyeni
    lat, lon = np.array([40.70, 40.71]), np.array([-74.00, -74.00])
    px, py = coordinates.project(lat, lon)
    euclid = np.hypot(px[1] - px[0], py[1] - py[0])
    assert euclid == pytest.approx(coordinates.haversine_m(40.70, -74.0, 40.71, -74.0), rel=5e-3)
    chk = coordinates.projection_check(np.array([40.6, 40.7, 40.8]), np.array([-74.1, -73.9, -73.8]))
    assert chk["all_inside_area_of_use"] and chk["roundtrip_error_m_max"] < 1e-3
    assert not coordinates.projection_check(np.array([40.7, 40.7]), np.array([-80.0, -74.0]))["all_inside_area_of_use"]


# ----------------------------------------------------------------- tekrarlar
def _dup_frame():
    lat = np.array([40.71, 40.71, 40.71, 40.72, np.nan])
    lon = np.array([-73.99, -73.99, -73.99, -73.98, np.nan])
    df = pd.DataFrame({"collision_id": [1, 2, 3, 4, 5], "latitude": lat, "longitude": lon,
                       "borough_final": ["MANHATTAN", "MANHATTAN", None, "BROOKLYN", None],
                       "borough_original": ["MANHATTAN", "BRONX", "QUEENS", "BROOKLYN", None],
                       "on_street_name": ["A", "A", "B", "C", None], "off_street_name": [None] * 5,
                       "crash_year": [2016] * 5})
    df["location_id"] = duplicates.assign_location_ids(lat, lon, ~np.isnan(lat))
    return df


def test_duplicate_coordinates_are_preserved_with_weights():
    df = _dup_frame()
    assert df["location_id"].tolist() == [0, 0, 0, 1, -1]
    loc = duplicates.location_table(df)
    assert loc["weight"].tolist() == [3, 1] and loc["weight"].sum() == 4
    assert len(df) == 5                                   # kayıtlar silinmez
    r = duplicates.repetition_analysis(df, loc, top_n=1, min_samples_grid=(2, 3))
    assert r["unique_locations"] == 2 and r["records_at_repeated_locations"] == 3
    assert r["self_core_locations_by_min_samples"]["3"] == {"locations": 1, "records": 3}


def test_geocode_fallback_flag():
    flags, stats = duplicates.geocode_fallback_flags(_dup_frame())
    assert flags["geocode_fallback_suspect_flag"].tolist() == [True, True, True, False, False]
    assert stats["locations"] == 1 and stats["records"] == 3


def test_weighted_unique_dbscan_equals_record_level():
    """Benzersiz konum + sample_weight, kayıt düzeyi DBSCAN ile aynı kümeleri vermeli."""
    from sklearn.cluster import DBSCAN

    rng = np.random.default_rng(0)
    centers = np.array([[40.70, -73.99], [40.75, -73.95]])
    pts = np.vstack([c + rng.normal(0, 0.0005, size=(40, 2)) for c in centers])
    pts = np.round(pts, 4)                                # tekrarlı koordinatlar oluşturur
    pts = np.vstack([pts, pts[:15], [[40.80, -73.90]]])   # açık tekrarlar + gürültü
    X = coordinates.to_radians(pts[:, 0], pts[:, 1])
    eps = coordinates.meters_to_radians(60)
    full = DBSCAN(eps=eps, min_samples=5, metric="haversine", algorithm="ball_tree").fit(X).labels_
    uniq, inv, w = np.unique(X, axis=0, return_inverse=True, return_counts=True)
    weighted = DBSCAN(eps=eps, min_samples=5, metric="haversine", algorithm="ball_tree").fit(
        uniq, sample_weight=w).labels_[inv.ravel()]
    assert len(np.unique(X, axis=0)) < len(X)
    assert np.array_equal(full == -1, weighted == -1)
    # Küme etiketleri yeniden numaralanabilir; bölümleme aynı olmalı
    pairs = set(zip(full[full >= 0], weighted[weighted >= 0]))
    assert len(pairs) == len(set(full[full >= 0])) == len(set(weighted[weighted >= 0]))
