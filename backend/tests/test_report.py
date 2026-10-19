import json

from conftest import FakeSession
from saferoute.cli import main
from saferoute.data.download import download_snapshot
from saferoute.eda.report import freshness, run_eda

QUIET = {"log": lambda _: None, "sleep": lambda _: None}


def test_run_eda_end_to_end(tmp_path, rows):
    snap = download_snapshot(snapshot_dir=tmp_path / "raw" / "s", page_size=3, session=FakeSession(rows), **QUIET)
    out = tmp_path / "report"
    dictionary = tmp_path / "docs" / "data_dictionary.md"
    summary = run_eda(snap, out, log=lambda _: None, dictionary_path=dictionary)

    dd = dictionary.read_text(encoding="utf-8")
    assert "| `latitude` | Enlem (WGS84) | text → text | 1 | %14,29 |" in dd
    assert "E — Kimlik / model dışı" in dd
    assert [s["step"] for s in summary["runtime"]["steps"]] == ["load_and_verify", "profile", "figures"]
    for name in ("vehicle_types.png", "casualties_by_road_user.png", "borough_coordinate_quality.png"):
        assert name in summary["figures"]

    stored = json.loads((out / "eda_summary.json").read_text(encoding="utf-8"))
    assert stored["profile"]["schema"]["row_count"] == 7
    assert stored["snapshot"]["combined_sha256"] == summary["snapshot"]["combined_sha256"]
    copied = json.loads((out / "source_manifest.json").read_text(encoding="utf-8"))
    assert copied["combined_sha256"] == summary["snapshot"]["combined_sha256"]
    md = (out / "EDA_RAPORU.md").read_text(encoding="utf-8")
    assert "Faz 1" in md and "| Geçerli | 3 |" in md
    for name in summary["figures"]:
        assert (out / "figures" / name).stat().st_size > 0
    assert "spatial_density_hexbin.png" in summary["figures"]


def test_freshness_measures_lags_and_recent_months():
    manifest = {
        "completed_at": "2026-10-19T00:00:00+00:00",
        "source_version": {"rows_updated_at_after": "2026-06-15T23:05:47+00:00", "update_frequency": "Daily"},
    }
    profile = {"temporal": {"crash_date_max": "2026-06-11",
                            "rows_per_month": {"2025-05": 100, "2025-06": 80, "2026-05": 90, "2026-06": 20}}}
    f = freshness(manifest, profile, months=2)
    assert f["days_source_update_to_download"] == 125
    assert f["days_max_crash_date_to_source_update"] == 4
    assert f["recent_months"][1] == {"month": "2026-06", "partial_month": True, "rows": 20,
                                     "same_month_previous_year": 80, "ratio_to_previous_year": 0.25}
    assert f["recent_months"][0]["partial_month"] is False


def test_cli_verify(tmp_path, rows, capsys):
    snap = download_snapshot(snapshot_dir=tmp_path / "s", page_size=3, session=FakeSession(rows), **QUIET)
    assert main(["verify", str(snap)]) == 0
    assert "7 satır" in capsys.readouterr().out
