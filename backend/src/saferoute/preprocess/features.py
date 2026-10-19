"""Öznitelik seçimi kayıt defteri ve algoritmalara özel öznitelik matrisleri.

Her sütun için: anlam, tür, uygulanan dönüşüm, A/B/C/D modellerine dahil olup olmadığı,
dahil edilmeme nedeni, filtre ve yorum kullanımı burada TEK yerde tanımlanır; rapor ve
öznitelik dosyaları bu tanımdan üretilir.

Modeller:
  A  Spatial DBSCAN       [lat_rad, lon_rad], metric=haversine, eps metre -> radyan
  B  Spatial K-Means      [x_m, y_m] (EPSG:32618), Öklid
  C  HDBSCAN              [lat_rad, lon_rad], metric=haversine (alternatif: [x_m, y_m])
  D  Uzay-zaman (deneysel) [x_m, y_m] + zaman eksenleri; ayrı eşikli komşuluk (ST-DBSCAN)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from saferoute.eda.profile import CASUALTY_COLUMNS, FACTOR_COLUMNS, VEHICLE_COLUMNS


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    meaning: str
    origin: str          # "raw" | "engineered"
    transform: str
    models: str          # "A,B,C,D" alt kümesi veya "—"
    exclusion_reason: str
    filter_use: str
    interpretation_use: str


_NO = "—"
_SPECS: list[FeatureSpec] = [
    FeatureSpec("collision_id", "Kaza kimliği", "raw", "Int64'e çevrildi", _NO,
                "Kimlik; mekânsal/zamansal bilgi taşımaz, modele girerse anlamsız mesafe üretir",
                "Hayır", "Kayıtları kümelere ve ham veriye bağlama"),
    FeatureSpec("crash_date", "Kaza tarihi", "raw", "datetime64'e ayrıştırıldı", _NO,
                "Ham tarih doğrudan girmez; türetilmiş eksenler (days_since_epoch) D'de kullanılır",
                "Tarih aralığı", "Zamansal profil"),
    FeatureSpec("crash_time", "Kaza saati (metin)", "raw", "Kırpıldı; saat/dakika ayrıştırıldı", _NO,
                "Metin; türetilmiş döngüsel saat D'de kullanılır", "Saat aralığı", "Zamansal profil"),
    FeatureSpec("borough_original", "Kayıtta bildirilen ilçe", "raw", "Kırpma + büyük harf", _NO,
                "Konumun türevi (çift temsil) ve %30 eksik; modele eklenirse coğrafyayı ikinci kez kodlar",
                "İlçe seçimi (borough_final üzerinden)", "Kaynak karşılaştırması"),
    FeatureSpec("zip_code", "Posta kodu", "raw", "Kırpma", _NO,
                "Konumun kaba türevi, %30 eksik", "İsteğe bağlı", "Betimleme"),
    FeatureSpec("latitude", "Enlem (WGS84, derece)", "raw", "float64; geçersizlik sınıflandırıldı", "A,B,C,D (dönüştürülmüş)",
                "Ham derece doğrudan girmez: A/C'de radyan, B/D'de metre", "Hayır", "Harita, küme merkezi"),
    FeatureSpec("longitude", "Boylam (WGS84, derece)", "raw", "float64; geçersizlik sınıflandırıldı", "A,B,C,D (dönüştürülmüş)",
                "Ham derece doğrudan girmez: A/C'de radyan, B/D'de metre", "Hayır", "Harita, küme merkezi"),
    FeatureSpec("location", "'(enlem, boylam)' metni", "raw", "Tutarlılığı ölçüldü, interim'e taşınmadı", _NO,
                "latitude/longitude ile birebir aynı bilgi (ölçülen fark 0)", "Hayır", "Hayır"),
    *[FeatureSpec(c, "Sokak/cadde adı", "raw", "Kırpma, boşluk tekleme, büyük harf", _NO,
                  "Yüksek kardinaliteli serbest metin; konumu metinle tekrarlar",
                  "Hayır", "Kümeleri okunur adlarla etiketleme")
      for c in ("on_street_name", "off_street_name", "cross_street_name")],
    *[FeatureSpec(c, "Yaralı/ölü sayısı", "raw", "Int32; üzerine yazılmadı, bayraklandı", _NO,
                  "Sonuç değişkeni: kümeleri betimlemek için korunur; üyeliği belirlerse soru 'şiddet ağırlıklı "
                  "yoğunluk'a döner ve değerlendirme döngüsel olur", "Yaralanmalı/ölümlü kaza filtresi",
                  "Küme şiddet profili")
      for c in CASUALTY_COLUMNS],
    *[FeatureSpec(c, "Katkıda bulunan faktör", "raw", "Kırpma, boşluk tekleme", _NO,
                  "Polis yorumu, %33 'Unspecified'; kategorik ve mekânsal soruya ait değil",
                  "Faktöre göre alt küme", "Küme faktör profili")
      for c in FACTOR_COLUMNS],
    *[FeatureSpec(c, "Araç türü (ham)", "raw", "Normalize edildi, üst kategoriye eşlendi", _NO,
                  "2.000+ dağınık etiket; mekânsal soruya ait değil", "vehicle_category_* / involves_* üzerinden",
                  "Küme araç profili")
      for c in VEHICLE_COLUMNS],
    # --- Türetilmiş ---
    FeatureSpec("lat_rad", "Enlem, radyan", "engineered", "radians(latitude)", "A,C",
                _NO, "Hayır", "Hayır"),
    FeatureSpec("lon_rad", "Boylam, radyan", "engineered", "radians(longitude)", "A,C",
                _NO, "Hayır", "Hayır"),
    FeatureSpec("x_m", "UTM 18N doğu koordinatı (m)", "engineered", "EPSG:4326 -> EPSG:32618", "B,D",
                _NO, "Hayır", "Hayır"),
    FeatureSpec("y_m", "UTM 18N kuzey koordinatı (m)", "engineered", "EPSG:4326 -> EPSG:32618", "B,D",
                _NO, "Hayır", "Hayır"),
    FeatureSpec("location_id", "Benzersiz konum kimliği", "engineered", "Sıralı benzersiz (enlem, boylam)", _NO,
                "Kimlik; ağırlıklı temsilde anahtar", "Hayır", "Tekrar analizi"),
    FeatureSpec("coordinate_quality_status", "Koordinat kalite durumu", "engineered",
                "Öncelikli dışlayıcı sınıflama + resmî poligon", _NO, "Kalite alanı", "Uygunluk seçimi", "Kalite raporu"),
    FeatureSpec("is_valid_geographic_record", "Geçerli coğrafi kayıt", "engineered", "Durumdan türetildi", _NO,
                "Bayrak", "Evet", "Kalite raporu"),
    FeatureSpec("eligible_for_spatial_clustering", "Kümelemeye uygun", "engineered", "Durum + geçerli tarih", _NO,
                "Bayrak; öznitelik matrislerinin satır seçimi", "Evet", "Hayır"),
    FeatureSpec("borough_inferred", "Poligondan çıkarılan ilçe", "engineered", "Point-in-polygon (covered_by)", _NO,
                "Konumun türevi", "Evet", "Bildirilen ilçeyle karşılaştırma"),
    FeatureSpec("borough_final", "Nihai ilçe", "engineered", "Bildirilen; yoksa poligon", _NO,
                "Konumun türevi", "İlçe seçimi", "İlçe özetleri"),
    FeatureSpec("borough_source", "Nihai ilçenin kaynağı", "engineered", "original / inferred_polygon / none", _NO,
                "Kaynak alanı", "Evet", "İzlenebilirlik"),
    FeatureSpec("borough_conflict_flag", "Bildirilen ≠ çıkarılan ilçe", "engineered", "Karşılaştırma", _NO,
                "Kalite bayrağı", "Evet", "Çelişki raporu"),
    FeatureSpec("location_reported_borough_count", "Aynı koordinattaki farklı bildirilmiş ilçe sayısı", "engineered",
                "location_id bazında nunique(borough_original)", _NO, "Kalite ölçüsü", "Hayır", "Geokodlama kalitesi"),
    FeatureSpec("geocode_fallback_suspect_flag", "Yedek geokodlama noktası şüphesi", "engineered",
                ">= 3 farklı bildirilmiş ilçe aynı koordinatta", _NO,
                "Kalite bayrağı; kayıt silinmez, Faz 3 duyarlılık analizinde kullanılır", "Evet", "Duyarlılık analizi"),
    FeatureSpec("crash_year", "Yıl", "engineered", "crash_date.year", _NO, "Filtre", "Yıl aralığı", "Zamansal profil"),
    FeatureSpec("crash_month", "Ay", "engineered", "crash_date.month", _NO,
                "Doğrusal ay modelde kullanılmaz (Aralık–Ocak süreksizliği)", "Ay", "Mevsimsellik"),
    FeatureSpec("crash_day", "Ayın günü", "engineered", "crash_date.day", _NO, "Filtre", "Evet", "Hayır"),
    FeatureSpec("crash_hour", "Saat", "engineered", "crash_time ayrıştırma", _NO,
                "Doğrusal saat modelde kullanılmaz (23–00 süreksizliği)", "Saat aralığı", "Saat profili"),
    FeatureSpec("crash_minute", "Dakika", "engineered", "crash_time ayrıştırma", _NO, "Ayrıntı", "Hayır", "00:00 analizi"),
    FeatureSpec("day_of_week", "Haftanın günü (0=Pzt)", "engineered", "crash_date.dayofweek", _NO,
                "Doğrusal kodlama kullanılmaz", "Gün", "Haftalık profil"),
    FeatureSpec("is_weekend", "Hafta sonu", "engineered", "day_of_week >= 5", _NO, "Filtre", "Evet", "Profil"),
    FeatureSpec("time_period", "Gün dilimi", "engineered", "00–06 gece, 06–12 sabah, 12–18 öğleden sonra, 18–24 akşam", _NO,
                "Kaba kategori; filtre", "Evet", "Profil"),
    FeatureSpec("hour_sin", "Saat (sin)", "engineered", "sin(2π·(saat+dk/60)/24)", "D", _NO, "Hayır", "Hayır"),
    FeatureSpec("hour_cos", "Saat (cos)", "engineered", "cos(2π·(saat+dk/60)/24)", "D", _NO, "Hayır", "Hayır"),
    FeatureSpec("month_sin", "Ay (sin)", "engineered", "sin(2π·(ay−1)/12)", _NO,
                "D'nin ilk sürümünde mevsim ekseni kullanılmaz (kapsam: konum + gün + saat)", "Hayır", "Mevsimsellik"),
    FeatureSpec("month_cos", "Ay (cos)", "engineered", "cos(2π·(ay−1)/12)", _NO,
                "Aynı gerekçe", "Hayır", "Mevsimsellik"),
    FeatureSpec("dow_sin", "Haftanın günü (sin)", "engineered", "sin(2π·gün/7)", "D", _NO, "Hayır", "Hayır"),
    FeatureSpec("dow_cos", "Haftanın günü (cos)", "engineered", "cos(2π·gün/7)", "D", _NO, "Hayır", "Hayır"),
    FeatureSpec("days_since_epoch", "1970'ten itibaren gün", "engineered", "crash_date − 1970-01-01", "D", _NO,
                "Hayır", "Hayır"),
    FeatureSpec("midnight_suspect_flag", "Kesin 00:00 saat (şüpheli)", "engineered", "saat=0 ve dakika=0", _NO,
                "Bayrak; D duyarlılık setinde dışlama ölçütü", "Evet", "Duyarlılık analizi"),
    FeatureSpec("injury_data_quality_flag", "Yaralı alanı tutarlılığı", "engineered", "Toplam vs alt alanlar", _NO,
                "Kalite bayrağı", "Evet", "Profil güvenilirliği"),
    FeatureSpec("fatality_data_quality_flag", "Ölü alanı tutarlılığı", "engineered", "Toplam vs alt alanlar", _NO,
                "Kalite bayrağı", "Evet", "Profil güvenilirliği"),
    FeatureSpec("has_reported_injury", "En az bir yaralı bildirilmiş", "engineered", "toplam>0 veya alt alan>0", _NO,
                "Sonuç değişkeni", "Evet", "Küme şiddet profili"),
    FeatureSpec("has_reported_fatality", "En az bir ölü bildirilmiş", "engineered", "toplam>0 veya alt alan>0", _NO,
                "Sonuç değişkeni", "Evet", "Küme şiddet profili"),
    FeatureSpec("vehicle_category_1..5", "Araç üst kategorisi", "engineered", "Kural tabanlı eşleme", _NO,
                "Kategorik; mekânsal soruya ait değil", "Evet", "Araç profili"),
    FeatureSpec("involves_<kategori>", "Kazada kategori var mı", "engineered", "vehicle_category_* üzerinden", _NO,
                "Filtre", "Evet (ör. bisiklet içeren kazalar)", "Araç profili"),
]
FEATURE_SPECS = {s.name: s for s in _SPECS}

FEATURE_SETS: dict[str, dict[str, Any]] = {
    "A_dbscan_haversine": {
        "model": "DBSCAN (A)", "level": "record", "key": "collision_id", "features": ["lat_rad", "lon_rad"],
        "metric": "haversine (scikit-learn: [enlem, boylam] radyan)", "units": "radyan; eps_rad = eps_m / 6371008.8",
    },
    "A_dbscan_haversine_weighted": {
        "model": "DBSCAN (A, ağırlıklı)", "level": "unique_location", "key": "location_id",
        "features": ["lat_rad", "lon_rad"], "weight": "weight",
        "metric": "haversine; fit(X, sample_weight=weight)", "units": "radyan",
    },
    "B_kmeans_projected": {
        "model": "K-Means (B)", "level": "record", "key": "collision_id", "features": ["x_m", "y_m"],
        "metric": "Öklid (EPSG:32618 metre)", "units": "metre",
    },
    "B_kmeans_projected_weighted": {
        "model": "K-Means (B, ağırlıklı)", "level": "unique_location", "key": "location_id",
        "features": ["x_m", "y_m"], "weight": "weight", "metric": "Öklid; fit(X, sample_weight=weight)",
        "units": "metre",
    },
    "C_hdbscan_haversine": {
        "model": "HDBSCAN (C)", "level": "record", "key": "collision_id", "features": ["lat_rad", "lon_rad"],
        "metric": "haversine (alternatif: x_m/y_m Öklid)", "units": "radyan",
        "note": "scikit-learn HDBSCAN sample_weight desteklemez; kayıt düzeyi kullanılmalı",
    },
    "D_spatiotemporal_experimental": {
        "model": "Uzay-zaman (D, deneysel)", "level": "record", "key": "collision_id",
        "features": ["x_m", "y_m", "days_since_epoch", "hour_sin", "hour_cos", "dow_sin", "dow_cos"],
        "extra_columns": ["midnight_suspect_flag"],
        "metric": "Ayrı eşikli komşuluk: mesafe_m <= eps_s VE |Δgün| <= eps_t (VE isteğe bağlı döngüsel saat farkı <= eps_h)",
        "units": "metre, gün, birim çember",
    },
    "D_spatiotemporal_experimental_no_midnight": {
        "model": "Uzay-zaman (D, duyarlılık: 00:00 hariç)", "level": "record", "key": "collision_id",
        "features": ["x_m", "y_m", "days_since_epoch", "hour_sin", "hour_cos", "dow_sin", "dow_cos"],
        "metric": "D ile aynı", "units": "metre, gün, birim çember", "row_filter": "midnight_suspect_flag == False",
    },
}


def build_feature_sets(processed: pd.DataFrame, locations: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """İşlenmiş katmandan her model için öznitelik matrislerini üretir (yalnızca uygun satırlar)."""
    elig = processed[processed["eligible_for_spatial_clustering"]]
    out: dict[str, pd.DataFrame] = {}
    for name, spec in FEATURE_SETS.items():
        cols = [spec["key"], *spec["features"], *([spec["weight"]] if "weight" in spec else []),
                *spec.get("extra_columns", [])]
        if spec["level"] == "unique_location":
            frame = locations[cols]
        else:
            frame = elig
            if spec.get("row_filter") == "midnight_suspect_flag == False":
                frame = frame[~frame["midnight_suspect_flag"]]
            frame = frame[cols]
        out[name] = frame.reset_index(drop=True)
    return out


def feature_selection_table(processed: pd.DataFrame, raw_missing_pct: dict[str, float]) -> pd.DataFrame:
    """Rapor tablosu: her öznitelik için 9 alan; eksik oranı ölçülür."""
    n = len(processed)
    rows = []
    for spec in _SPECS:
        if spec.name in raw_missing_pct:
            missing = raw_missing_pct[spec.name]
            dtype = "string (ham)"
            if spec.name in processed.columns:
                dtype = str(processed[spec.name].dtype)
        elif spec.name in processed.columns:
            missing = round(100.0 * processed[spec.name].isna().sum() / n, 4) if n else 0.0
            dtype = str(processed[spec.name].dtype)
        else:
            family = [c for c in processed.columns if c.startswith(spec.name.split("_<")[0].split("_1..")[0])]
            missing = round(100.0 * processed[family].isna().all(axis=1).sum() / n, 4) if family and n else None
            dtype = str(processed[family[0]].dtype) if family else "—"
        rows.append({
            "Öznitelik": spec.name, "Anlam": spec.meaning, "Köken": spec.origin, "Veri türü": dtype,
            "Eksik %": missing, "Dönüşüm": spec.transform, "Modeller": spec.models,
            "Dahil edilmeme nedeni": spec.exclusion_reason, "Filtre kullanımı": spec.filter_use,
            "Yorum kullanımı": spec.interpretation_use,
        })
    return pd.DataFrame(rows)


def feature_set_summary(sets: dict[str, pd.DataFrame]) -> dict[str, Any]:
    out = {}
    for name, frame in sets.items():
        spec = FEATURE_SETS[name]
        feats = frame[spec["features"]]
        out[name] = {
            **{k: v for k, v in spec.items() if k != "extra_columns"},
            "rows": int(len(frame)),
            "weight_sum": int(frame[spec["weight"]].sum()) if "weight" in spec else None,
            "any_nan": bool(feats.isna().any().any()),
            "all_finite": bool(np.isfinite(feats.to_numpy(dtype="float64")).all()),
            "ranges": {c: [float(feats[c].min()), float(feats[c].max())] for c in spec["features"]} if len(frame) else {},
        }
    return out
