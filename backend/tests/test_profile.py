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
    # Beş ilçenin tamamı, kayıt olmasa bile 0 ile raporlanır.
    assert b["counts"] == {"MANHATTAN": 2, "BROOKLYN": 1, "QUEENS": 1, "BRONX": 0, "STATEN ISLAND": 0}
    assert b["missing"] == 3
    assert b["unexpected_values"] == [] and b["unexpected_rows"] == 0


def test_unexpected_and_lowercase_borough_labels():
    from conftest import make_row, to_frame

    df = to_frame([make_row(borough="manhattan "), make_row(borough="NEW JERSEY"), make_row(borough=None)])
    b = prof.boroughs(df)
    assert b["counts"]["MANHATTAN"] == 1
    assert b["unexpected_values"] == ["NEW JERSEY"] and b["unexpected_rows"] == 1
    assert b["missing"] == 1


def test_borough_by_coordinate_class_keeps_missing_borough_rows(frame):
    t = prof.borough_by_coordinate_class(frame)
    assert t["MANHATTAN"]["valid_in_bbox"] == 2
    assert t["BROOKLYN"]["missing"] == 1
    assert t["QUEENS"]["outside_nyc_bbox"] == 1
    # İlçesi eksik 3 kayıt: sıfır (r3), ayrıştırılamaz (r5), geçerli (r7)
    assert t["MISSING"] == {"missing": 0, "unparseable": 1, "zero": 1, "outside_nyc_bbox": 0, "valid_in_bbox": 1}
    assert sum(sum(v.values()) for v in t.values()) == len(frame)


def test_column_overview_types_uniques_and_identifiers(frame):
    o = prof.column_overview(frame, {"latitude": "number"})
    assert o["latitude"]["source_type"] == "number"
    assert o["latitude"]["inferred_type"] == "text"          # "abc" değeri var
    assert o["crash_time"]["inferred_type"] == "text"        # "25:00" geçersiz
    assert o["zip_code"]["inferred_type"] == "integer"
    assert o["number_of_persons_killed"]["inferred_type"] == "integer"
    assert o["collision_id"]["inferred_type"] == "float"     # "7.5"
    assert o["vehicle_type_code_5"]["inferred_type"] == "empty"
    assert o["borough"]["missing"] == 3 and o["borough"]["unique_non_missing"] == 3
    # collision_id tekrarlı olduğu için aday kimlik değil
    assert not any(v["candidate_identifier"] for v in o.values())


def test_candidate_identifier_detected():
    from conftest import make_row, to_frame

    df = to_frame([make_row(collision_id=str(i), crash_date="2020-01-01T00:00:00.000") for i in range(3)])
    o = prof.column_overview(df)
    assert o["collision_id"]["candidate_identifier"] is True
    assert o["collision_id"]["inferred_type"] == "integer"
    assert o["crash_date"]["inferred_type"] == "datetime"
    assert o["crash_date"]["candidate_identifier"] is False


def test_infer_type_time():
    import pandas as pd

    assert prof.infer_type(pd.Series(["0:05", "23:59", None])) == "time"


def test_empty_input_produces_zero_profile():
    from conftest import to_frame

    p = prof.build_profile(to_frame([]))
    assert p["schema"]["row_count"] == 0 and p["schema"]["validation"]["is_empty"]
    assert p["missing_values"]["latitude"]["missing_pct"] == 0.0
    assert p["coordinates"]["classes"] == {k: 0 for k in prof.COORD_CLASSES}
    assert p["temporal"]["crash_date_min"] is None
    assert p["boroughs"]["missing"] == 0
    assert p["duplicates"]["exact_duplicate_rows"] == 0
    assert p["quality_by_year"] == {}


def test_missing_column_raises_schema_error(frame):
    from saferoute.data.validate import SchemaError

    with pytest.raises(SchemaError, match="latitude"):
        prof.build_profile(frame.drop(columns=["latitude"]))


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
