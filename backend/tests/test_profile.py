"""EDA profil fonksiyonları: conftest.sample_rows() içindeki bilinen kusurların birebir sayılması."""

import json

import pytest

from saferoute.eda import profile as prof


def test_schema(frame):
    s = prof.schema_summary(frame)
    assert s["row_count"] == 7 and s["column_count"] == 29


def test_missing_values_separates_null_and_blank(frame):
    mv = prof.missing_values(frame)
    assert mv["borough"] == {"null": 2, "blank": 1, "missing_total": 3, "missing_pct": pytest.approx(42.8571)}
    assert mv["collision_id"]["missing_total"] == 0


def test_duplicates(frame):
    d = prof.duplicates(frame)
    assert d["collision_id_missing"] == 0
    assert d["collision_id_non_integer"] == 1          # "7.5"
    assert d["collision_id_unique_values"] == 5
    assert d["duplicated_collision_ids"] == 2          # "1" ve "3"
    assert d["rows_with_duplicated_collision_id"] == 4
    assert d["exact_duplicate_rows"] == 1              # r6 == r1


def test_temporal(frame):
    t = prof.temporal(frame)
    assert t["crash_date_missing"] == 0
    assert t["crash_date_unparseable"] == 1
    assert (t["crash_date_min"], t["crash_date_max"]) == ("2020-01-01", "2022-03-04")
    assert t["crash_date_has_nonzero_time_component"] == 0
    assert t["rows_per_year"] == {"2020": 3, "2021": 2, "2022": 1}
    assert t["crash_time_missing"] == 1
    assert t["crash_time_invalid"] == 1                # "25:00"
    assert t["crash_time_exact_midnight"] == 1         # "0:00"
    assert t["rows_per_hour"] == {"0": 1, "7": 1, "10": 2, "23": 1}


def test_coordinate_classes_are_exclusive_and_exhaustive(frame):
    c = prof.coordinates(frame)
    assert c["classes"] == {"missing": 1, "unparseable": 1, "zero": 1, "outside_nyc_bbox": 1, "valid_in_bbox": 3}
    assert sum(c["classes"].values()) == len(frame)
    assert c["valid_but_borough_missing"] == 1
    assert c["borough_present_but_coords_unusable"] == 2
    assert c["location_present_latlon_missing"] == 1
    assert c["latlon_present_location_missing"] == 4
    assert c["distinct_valid_locations"] == 2
    assert prof.coordinate_validity_mask(frame).tolist() == [True, False, False, False, False, True, True]


def test_boroughs(frame):
    b = prof.boroughs(frame)
    assert b["counts"] == {"MANHATTAN": 2, "BROOKLYN": 1, "QUEENS": 1}
    assert b["missing"] == 3
    assert b["unexpected_values"] == []


def test_quality_by_year(frame):
    q = prof.by_year_quality(frame)
    assert q["2020"]["rows"] == 3
    assert q["2020"]["coord_valid_pct"] == pytest.approx(66.6667)
    assert q["2021"]["borough_present_pct"] == 50.0
    assert q["2022"] == {"rows": 1, "coord_valid_pct": 100.0, "borough_present_pct": 0.0}


def test_casualties(frame):
    c = prof.casualties(frame)
    inj = c["columns"]["number_of_persons_injured"]
    assert inj["unparseable"] == 1 and inj["sum"] == 4 and inj["rows_gt_zero"] == 3
    assert c["columns"]["number_of_cyclist_injured"]["negative"] == 1
    assert c["consistency_injured"] == {
        "comparable_rows": 6, "persons_equals_sum": 4, "persons_greater_than_sum": 2, "persons_less_than_sum": 0,
    }
    assert c["consistency_killed"]["persons_equals_sum"] == 7
    assert c["rows_with_any_injury"] == 3
    assert c["rows_with_any_fatality"] == 1
    assert c["rows_with_injury_or_fatality"] == 4


def test_categoricals(frame):
    c = prof.categoricals(frame)
    assert c["contributing_factor_1_top"] == {"Driver Inattention/Distraction": 2, "Unspecified": 1}
    assert c["contributing_factor_1_missing"] == 4
    assert c["contributing_factor_1_unspecified"] == 1
    assert c["vehicle_type_distinct_raw"] == 4
    assert c["vehicle_type_distinct_normalized"] == 3
    assert c["vehicle_type_codes_present_per_row"] == {"0": 3, "1": 2, "2": 2}


def test_text_fields(frame):
    t = prof.text_fields(frame)
    assert t["zip_code_missing"] == 4 and t["zip_code_invalid_format"] == 1
    assert t["on_street_name_whitespace_padded"] == 1
    assert t["on_street_name_distinct_raw"] == 2


def test_profile_does_not_mutate_and_is_json_serialisable(frame):
    before = frame.copy()
    result = prof.build_profile(frame)
    assert frame.equals(before)
    json.dumps(result)
