"""EDA çıktılarını üretir: makine-okur ``eda_summary.json`` ve Türkçe ``EDA_RAPORU.md``.

Rapordaki her sayı doğrudan profil sözlüğünden gelir; elle yazılmış istatistik yoktur.
"""

from __future__ import annotations

import json
import os
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from saferoute.data.loader import load_raw, read_manifest
from saferoute.eda import figures, profile as prof
from saferoute.eda.dictionary import render_data_dictionary
from saferoute.perf import StepTimer, peak_memory_mb


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    ts = pd.Timestamp(value)
    return (ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")).to_pydatetime()


def freshness(manifest: dict[str, Any], profile: dict[str, Any], months: int = 6) -> dict[str, Any]:
    """Kaynak güncelliği ve son ayların olası eksik raporlanmasına dair ölçümler."""
    updated = _parse_ts(manifest["source_version"]["rows_updated_at_after"])
    downloaded = _parse_ts(manifest["completed_at"])
    max_date = _parse_ts(profile["temporal"]["crash_date_max"])
    monthly = profile["temporal"]["rows_per_month"]

    recent = []
    for key in list(monthly)[-months:]:
        y, m = key.split("-")
        prev_key = f"{int(y) - 1}-{m}"
        # Kapsamın son ayı, maksimum tarih ay sonuna denk gelmiyorsa kısmidir.
        partial = bool(max_date) and key == max_date.strftime("%Y-%m") and not pd.Timestamp(max_date).is_month_end
        recent.append({
            "month": key,
            "partial_month": partial,
            "rows": monthly[key],
            "same_month_previous_year": monthly.get(prev_key),
            "ratio_to_previous_year": round(monthly[key] / monthly[prev_key], 4) if monthly.get(prev_key) else None,
        })
    return {
        "source_rows_updated_at": updated.isoformat() if updated else None,
        "downloaded_at": downloaded.isoformat() if downloaded else None,
        "max_crash_date": profile["temporal"]["crash_date_max"],
        "days_source_update_to_download": (downloaded - updated).days if updated and downloaded else None,
        "days_max_crash_date_to_source_update": (updated - max_date).days if updated and max_date else None,
        "days_max_crash_date_to_download": (downloaded - max_date).days if downloaded and max_date else None,
        "update_frequency_declared": manifest["source_version"].get("update_frequency"),
        "recent_months": recent,
    }


def run_eda(
    snapshot_dir: Path,
    out_dir: Path,
    log=print,
    dictionary_path: Path | None = None,
) -> dict[str, Any]:
    """Anlık görüntüyü doğrular, profiller, şekilleri çizer ve raporları yazar.

    Bellekte tek bir DataFrame tutulur (Arrow metin sütunları); şekiller için yalnızca
    geçerli koordinatların iki sayısal dizisi ayrıca oluşturulur.
    """
    out_dir = Path(out_dir)
    fig_dir = out_dir / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = read_manifest(snapshot_dir)
    source_types = {c["field_name"]: c["data_type"] for c in manifest["columns"]}
    timer = StepTimer()
    t0 = time.perf_counter()

    with timer.step("load_and_verify"):
        df = load_raw(snapshot_dir, verify=True)
    log(f"Yüklendi: {len(df):,} satır, {df.shape[1]} sütun ({timer.steps[-1]['seconds']} sn)")

    with timer.step("profile"):
        profile = prof.build_profile(df, source_types)
    log(f"Profil çıkarıldı ({timer.steps[-1]['seconds']} sn)")

    with timer.step("figures"):
        mask = prof.coordinate_validity_mask(df)
        lat = prof._numeric(df.loc[mask, "latitude"]).to_numpy()
        lon = prof._numeric(df.loc[mask, "longitude"]).to_numpy()
        paths = figures.render_all(profile, fig_dir, lat, lon)
    del df, lat, lon, mask

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "snapshot": {
            "dir_name": Path(snapshot_dir).name,
            "dataset_id": manifest["dataset_id"],
            "combined_sha256": manifest["combined_sha256"],
            "row_count_manifest": manifest["row_count"],
            "status": manifest["status"],
            "warnings": manifest["warnings"],
        },
        "freshness": freshness(manifest, profile),
        "profile": profile,
        "runtime": {
            "steps": timer.steps,
            "total_seconds": round(time.perf_counter() - t0, 2),
            "peak_memory_mb": peak_memory_mb(),
            "memory_method": "süreç fiziksel bellek tepe değeri (Windows PeakWorkingSetSize / Unix ru_maxrss)",
            "machine": {"platform": platform.platform(), "python": platform.python_version(),
                        "cpu_count": os.cpu_count()},
        },
        "figures": [p.name for p in paths],
    }
    (out_dir / "eda_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    # İzlenebilirlik: ham veri depoya girmez, ama onu tanımlayan manifest rapora eşlik eder.
    (out_dir / "source_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "EDA_RAPORU.md").write_text(render_markdown(summary, manifest), encoding="utf-8")
    if dictionary_path is not None:
        Path(dictionary_path).parent.mkdir(parents=True, exist_ok=True)
        Path(dictionary_path).write_text(render_data_dictionary(profile, Path(snapshot_dir).name), encoding="utf-8")
    log(f"Rapor yazıldı: {out_dir}")
    return summary


def _n(x: Any) -> str:
    """Türkçe binlik ayırıcıyla sayı biçimi."""
    if x is None:
        return "—"
    if isinstance(x, float) and not x.is_integer():
        return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{int(x):,}".replace(",", ".")


def _p(x: float | None) -> str:
    if x is None:
        return "—"
    if 0 < x < 0.005:  # sıfır olmayan küçük oran "%0,00" görünüp yanıltmasın
        return "<%0,01"
    return f"%{x:.2f}".replace(".", ",")


def render_markdown(summary: dict[str, Any], manifest: dict[str, Any]) -> str:
    p = summary["profile"]
    f = summary["freshness"]
    total = p["schema"]["row_count"]
    c = p["coordinates"]
    t = p["temporal"]
    d = p["duplicates"]
    cas = p["casualties"]
    cat = p["categoricals"]
    tf = p["text_fields"]
    lines: list[str] = []
    w = lines.append

    w("# Faz 1 — Otomatik EDA Raporu")
    w("")
    w("> Bu dosya `saferoute eda` komutuyla otomatik üretilmiştir. Tüm sayılar ham anlık görüntüden ölçülmüştür.")
    w("")
    w("## 1. Kaynak ve anlık görüntü")
    w("")
    w("| Alan | Değer |")
    w("|---|---|")
    w(f"| Veri seti | {manifest['dataset_name']} (`{manifest['dataset_id']}`) |")
    w(f"| Kaynak | {manifest['source_page_url']} |")
    w(f"| İndirme yöntemi | {manifest['download_method']['api']}, `{manifest['download_method']['ordering']}`, "
      f"sayfa boyutu {_n(manifest['download_method']['page_size'])} |")
    w(f"| İndirme başlangıç / bitiş (UTC) | {manifest['started_at']} / {manifest['completed_at']} |")
    w(f"| Kaynak `rowsUpdatedAt` | {manifest['source_version']['rows_updated_at_after']} |")
    w(f"| Satır / sütun | {_n(manifest['row_count'])} / {manifest['column_count']} |")
    w(f"| Sunucu sayımı (indirme sonrası) | {_n(manifest['server_stats_after']['row_count'])} |")
    w(f"| Parça sayısı | {len(manifest['parts'])} |")
    w(f"| Birleşik SHA-256 | `{manifest['combined_sha256']}` |")
    w(f"| Durum | {manifest['status']} |")
    w("")
    if manifest["warnings"]:
        w("**Uyarılar:** " + "; ".join(manifest["warnings"]))
        w("")

    w("## 2. Veri güncelliği")
    w("")
    w(f"- Kaynağın son satır güncellemesi: **{f['source_rows_updated_at']}**")
    w(f"- En son kaza tarihi (`crash_date` maks.): **{f['max_crash_date']}**")
    w(f"- Kaynak güncellemesinden indirmeye geçen süre: **{f['days_source_update_to_download']} gün**")
    w(f"- En son kaza tarihinden indirmeye geçen süre: **{f['days_max_crash_date_to_download']} gün**")
    w(f"- Yayıncının beyan ettiği güncelleme sıklığı: {f['update_frequency_declared'] or '—'}")
    w("")
    w("Son ayların bir önceki yılın aynı ayına oranı (raporlama gecikmesi göstergesi olabilir, kanıt değildir):")
    w("")
    w("| Ay | Kayıt | Önceki yıl aynı ay | Oran |")
    w("|---|---:|---:|---:|")
    for r in f["recent_months"]:
        ratio = "—" if r["ratio_to_previous_year"] is None else f"{r['ratio_to_previous_year']:.2f}".replace(".", ",")
        month = f"{r['month']} (kısmi ay)" if r.get("partial_month") else r["month"]
        w(f"| {month} | {_n(r['rows'])} | {_n(r['same_month_previous_year'])} | {ratio} |")
    if any(r.get("partial_month") for r in f["recent_months"]):
        w("")
        w("*Kısmi ay: kapsam ay sonundan önce bittiği için bu ayın oranı önceki yılla karşılaştırılabilir değildir; "
          "düşüklüğün büyük kısmı eksik günlerden kaynaklanır, olası raporlama gecikmesi ayrıca dışlanamaz.*")
    w("")

    w("## 3. Eksik değerler")
    w("")
    w("| Sütun | Boş (null) | Yalnız boşluk | Toplam eksik | Oran |")
    w("|---|---:|---:|---:|---:|")
    for col, v in p["missing_values"].items():
        w(f"| `{col}` | {_n(v['null'])} | {_n(v['blank'])} | {_n(v['missing_total'])} | {_p(v['missing_pct'])} |")
    w("")
    w("![Eksik değerler](figures/missing_values.png)")
    w("")
    w("### Sütun türleri ve benzersiz değerler")
    w("")
    w("Kaynak türü Socrata meta verisinden; ölçülen tür, dolu değerlerin tamamına uyan en dar türdür.")
    w("")
    w("| Sütun | Kaynak türü | Ölçülen tür | Benzersiz (dolu) | Aday kimlik |")
    w("|---|---|---|---:|:---:|")
    for col, o in p["column_overview"].items():
        w(f"| `{col}` | {o['source_type'] or '—'} | {o['inferred_type']} | {_n(o['unique_non_missing'])} | "
          f"{'✓' if o['candidate_identifier'] else ''} |")
    w("")

    w("## 4. Kimlik ve tekrar analizi")
    w("")
    w(f"- `collision_id` eksik: {_n(d['collision_id_missing'])}, tam sayı olmayan: {_n(d['collision_id_non_integer'])}")
    w(f"- Benzersiz `collision_id`: {_n(d['collision_id_unique_values'])} / {_n(total)} satır")
    w(f"- Birden fazla satırda görülen kimlik: {_n(d['duplicated_collision_ids'])} "
      f"(bu kimlikleri taşıyan satır: {_n(d['rows_with_duplicated_collision_id'])})")
    w(f"- Tüm sütunları birebir aynı tekrar satır: {_n(d['exact_duplicate_rows'])}")
    w("")

    w("## 5. Zaman alanları")
    w("")
    w(f"- `crash_date` eksik: {_n(t['crash_date_missing'])}, ayrıştırılamaz: {_n(t['crash_date_unparseable'])}, "
      f"saat bileşeni sıfır olmayan: {_n(t['crash_date_has_nonzero_time_component'])}")
    w(f"- Kapsam: **{t['crash_date_min']} → {t['crash_date_max']}**")
    w(f"- `crash_time` eksik: {_n(t['crash_time_missing'])}, geçersiz: {_n(t['crash_time_invalid'])}")
    w(f"- Tam 00:00 olarak kayıtlı: {_n(t['crash_time_exact_midnight'])} ({_p(t['crash_time_exact_midnight_pct'])}) "
      "— gece yarısı yığılması, varsayılan/bilinmeyen saat girişine işaret edebilir; Faz 2'de incelenecek.")
    w("")
    w("| Yıl | Kayıt |")
    w("|---|---:|")
    for y, n in t["rows_per_year"].items():
        w(f"| {y} | {_n(n)} |")
    w("")
    w("![Yıllık](figures/rows_per_year.png)")
    w("")
    w("![Aylık](figures/rows_per_month.png)")
    w("")
    w("![Saatlik](figures/rows_per_hour.png)")
    w("")
    w("![Haftalık](figures/rows_per_weekday.png)")
    w("")

    w("## 6. Koordinatlar ve coğrafi sınır kontrolü")
    w("")
    bb = c["bbox"]
    w(f"NYC sınırlayıcı kutusu: enlem {bb['min_lat']}–{bb['max_lat']}, boylam {bb['min_lon']}–{bb['max_lon']} "
      "(kaba kontrol; ilçe poligonu doğrulaması Faz 2).")
    w("")
    w("| Sınıf | Kayıt | Oran |")
    w("|---|---:|---:|")
    for k, v in c["classes"].items():
        w(f"| {figures.COORD_CLASS_TR[k]} | {_n(v)} | {_p(c['classes_pct'][k])} |")
    w("")
    w(f"- Geçerli koordinatlı ama ilçe alanı boş: {_n(c['valid_but_borough_missing'])}")
    w(f"- İlçe alanı dolu ama koordinatı kullanılamaz: {_n(c['borough_present_but_coords_unusable'])}")
    w(f"- `location` dolu / lat-lon eksik: {_n(c['location_present_latlon_missing'])}; "
      f"lat-lon dolu / `location` eksik: {_n(c['latlon_present_location_missing'])}")
    w(f"- Geçerli koordinatlarda farklı (lat, lon) çifti: {_n(c['distinct_valid_locations'])}")
    w("")
    w("![Koordinat sınıfları](figures/coordinate_classes.png)")
    w("")
    w("![Yoğunluk](figures/spatial_density_hexbin.png)")
    w("")
    w("*Not: Yoğunluk haritası geçerli koordinatlı kayıtların tamamından (örnekleme olmadan) altıgen hücre "
      "sayımıyla üretilmiştir; ham kayıt sayısını gösterir, kümeleme sonucu veya risk ölçüsü değildir.*")
    w("")

    w("## 7. İlçeler")
    w("")
    w("| İlçe | Kayıt |")
    w("|---|---:|")
    for k, v in p["boroughs"]["counts"].items():
        w(f"| {figures.BOROUGH_TR.get(k, k)} | {_n(v)} |")
    w(f"| *Eksik* | {_n(p['boroughs']['missing'])} ({_p(p['boroughs']['missing_pct'])}) |")
    w(f"| *Beklenmeyen etiket* | {_n(p['boroughs']['unexpected_rows'])} |")
    w("")
    if p["boroughs"]["unexpected_values"]:
        w(f"Beklenmeyen ilçe değerleri: {p['boroughs']['unexpected_values']}")
        w("")
    w("![İlçeler](figures/boroughs.png)")
    w("")
    w("Kaydedilmiş ilçe × koordinat sınıfı (eksik ilçeli kayıtlar atılmaz, ayrı satırda gösterilir):")
    w("")
    w("| İlçe kaydı | Geçerli | Eksik | Sıfır | Kutu dışı | Ayrıştırılamaz |")
    w("|---|---:|---:|---:|---:|---:|")
    names = {"MISSING": "*İlçe eksik*", "UNEXPECTED": "*Beklenmeyen*"}
    for k, v in p["borough_by_coordinate_class"].items():
        w(f"| {names.get(k, figures.BOROUGH_TR.get(k, k))} | {_n(v['valid_in_bbox'])} | {_n(v['missing'])} | "
          f"{_n(v['zero'])} | {_n(v['outside_nyc_bbox'])} | {_n(v['unparseable'])} |")
    w("")
    w("![İlçe-koordinat](figures/borough_coordinate_quality.png)")
    w("")
    w("| Yıl | Geçerli koordinat % | İlçe dolu % |")
    w("|---|---:|---:|")
    for y, q in p["quality_by_year"].items():
        w(f"| {y} | {_p(q['coord_valid_pct'])} | {_p(q['borough_present_pct'])} |")
    w("")
    w("![Kalite](figures/quality_by_year.png)")
    w("")

    w("## 8. Yaralanma ve ölümler")
    w("")
    w("| Sütun | Eksik | Ayrıştırılamaz | Negatif | Toplam | Maks. | >0 olan satır |")
    w("|---|---:|---:|---:|---:|---:|---:|")
    for col, v in cas["columns"].items():
        w(f"| `{col}` | {_n(v['missing'])} | {_n(v['unparseable'])} | {_n(v['negative'])} | "
          f"{_n(v['sum'])} | {_n(v['max'])} | {_n(v['rows_gt_zero'])} |")
    w("")
    for kind, label in (("injured", "Yaralı"), ("killed", "Ölü")):
        k = cas[f"consistency_{kind}"]
        w(f"- {label} tutarlılığı (kişi = yaya + bisikletli + motorlu): karşılaştırılabilir {_n(k['comparable_rows'])}, "
          f"eşit {_n(k['persons_equals_sum'])}, kişi > toplam {_n(k['persons_greater_than_sum'])}, "
          f"kişi < toplam {_n(k['persons_less_than_sum'])}")
    w(f"- En az bir yaralı olan kayıt: {_n(cas['rows_with_any_injury'])}; "
      f"en az bir ölü olan kayıt: {_n(cas['rows_with_any_fatality'])}")
    w("")
    w("![Yaralı ve ölüler](figures/casualties_by_road_user.png)")
    w("")

    w("## 9. Kategorik alanlar")
    w("")
    w(f"- Katkıda bulunan faktör (araç 1) eksik: {_n(cat['contributing_factor_1_missing'])}; "
      f"\"Unspecified\": {_n(cat['contributing_factor_1_unspecified'])} ({_p(cat['contributing_factor_1_unspecified_pct'])})")
    w(f"- 5 faktör sütunundaki farklı değer: {_n(cat['contributing_factor_distinct_all_columns'])}")
    w(f"- Araç türü farklı değer: ham {_n(cat['vehicle_type_distinct_raw'])}, "
      f"büyük harf + kırpma sonrası {_n(cat['vehicle_type_distinct_normalized'])} — Faz 2'de kategori eşlemesi gerekir.")
    w("")
    w("| Dolu araç türü sütunu sayısı | Kayıt |")
    w("|---|---:|")
    for k, v in cat["vehicle_type_codes_present_per_row"].items():
        w(f"| {k} | {_n(v)} |")
    w("")
    w("| Araç türü (araç 1) | Kayıt |")
    w("|---|---:|")
    for k, v in cat["vehicle_type_1_top"].items():
        w(f"| {k} | {_n(v)} |")
    w("")
    w("![Araç türleri](figures/vehicle_types.png)")
    w("")
    w("| Faktör (araç 1) | Kayıt |")
    w("|---|---:|")
    for k, v in cat["contributing_factor_1_top"].items():
        w(f"| {k} | {_n(v)} |")
    w("")
    w("![Faktörler](figures/top_contributing_factors.png)")
    w("")

    w("## 10. Metin alanları")
    w("")
    w(f"- Posta kodu eksik: {_n(tf['zip_code_missing'])}, 5 haneli olmayan: {_n(tf['zip_code_invalid_format'])}")
    for col in ("on_street_name", "off_street_name", "cross_street_name"):
        w(f"- `{col}`: başında/sonunda boşluk olan {_n(tf[col + '_whitespace_padded'])}; farklı değer "
          f"ham {_n(tf[col + '_distinct_raw'])} → normalize {_n(tf[col + '_distinct_stripped_upper'])}")
    w("")

    r = summary["runtime"]
    w("## 11. Çalışma süresi ve bellek")
    w("")
    w("| Adım | Süre (sn) | O ana kadarki bellek tepe değeri (MB) |")
    w("|---|---:|---:|")
    step_tr = {"load_and_verify": "Yükleme + SHA-256 doğrulama", "profile": "Profil", "figures": "Şekiller"}
    for s in r["steps"]:
        w(f"| {step_tr.get(s['step'], s['step'])} | {_n(float(s['seconds']))} | {_n(s['peak_memory_mb_so_far'])} |")
    w("")
    m = r["machine"]
    w(f"Toplam {_n(float(r['total_seconds']))} sn. Bellek ölçüm yöntemi: {r['memory_method']}. "
      f"Ortam: {m['platform']}, Python {m['python']}, {m['cpu_count']} mantıksal çekirdek.")
    w("")
    return "\n".join(lines)
