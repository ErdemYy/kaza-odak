"""Koordinat dönüşümleri: Haversine için radyan, K-Means için metrik projeksiyon.

DBSCAN / HDBSCAN (scikit-learn, ``metric="haversine"``):
  * Girdi sütun sırası [enlem, boylam], birimi RADYAN olmalıdır.
  * Çıktı uzaklığı birim küre üzerindeki açıdır (radyan); metreye çevirmek için
    yerküre yarıçapıyla çarpılır. Dolayısıyla kullanıcıya metre cinsinden sunulan
    ``eps_m`` modele ``eps_rad = eps_m / R`` olarak verilir (R = 6 371 008,8 m).

K-Means (Öklid uzaklığı):
  * Derece cinsinden enlem/boylam üzerinde Öklid uzaklığı yöne bağlı olarak bozulur
    (NYC'de 1° boylam ≈ 84 km, 1° enlem ≈ 111 km). Bu yüzden koordinatlar UTM 18N
    (EPSG:32618, metre) projeksiyonuna dönüştürülür; NYC bu dilimin içindedir.

Ölçekleme (standartlaştırma) uygulanmaz: radyan ve metre fiziksel olarak anlamlı,
eksenler arası tutarlı birimlerdir; z-skoru gibi ölçekleme mesafeyi bozardı.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from pyproj import CRS, Geod, Transformer

EARTH_RADIUS_M = 6_371_008.8


def to_radians(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """[enlem, boylam] radyan matrisi (scikit-learn haversine sırası)."""
    return np.radians(np.column_stack([np.asarray(lat, dtype="float64"), np.asarray(lon, dtype="float64")]))


def haversine_m(lat1, lon1, lat2, lon2, radius: float = EARTH_RADIUS_M) -> np.ndarray:
    """İki nokta (derece) arasındaki büyük çember uzaklığı, metre."""
    p1, l1, p2, l2 = map(lambda v: np.radians(np.asarray(v, dtype="float64")), (lat1, lon1, lat2, lon2))
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin((l2 - l1) / 2) ** 2
    return 2 * radius * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def meters_to_radians(eps_m: float, radius: float = EARTH_RADIUS_M) -> float:
    if eps_m <= 0:
        raise ValueError("eps_m pozitif olmalıdır")
    return eps_m / radius


def radians_to_meters(eps_rad: float, radius: float = EARTH_RADIUS_M) -> float:
    return eps_rad * radius


def project(lat: np.ndarray, lon: np.ndarray, target_crs: str = "EPSG:32618",
            source_crs: str = "EPSG:4326") -> tuple[np.ndarray, np.ndarray]:
    """Coğrafi koordinatları metrik projeksiyona dönüştürür; (x_m, y_m) döner."""
    transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)  # girdi (boylam, enlem)
    x, y = transformer.transform(np.asarray(lon, dtype="float64"), np.asarray(lat, dtype="float64"))
    return np.asarray(x), np.asarray(y)


def projection_check(lat: np.ndarray, lon: np.ndarray, target_crs: str = "EPSG:32618",
                     sample: int = 20_000, seed: int = 0) -> dict[str, Any]:
    """Projeksiyonun kapsama alanını ve mesafe doğruluğunu ölçer.

    * Tüm noktalar CRS'in kullanım alanı (area of use) içinde mi?
    * Gidiş-dönüş (ileri + ters dönüşüm) hatası.
    * Referans: WGS84 elipsoidi üzerindeki jeodezik mesafe (pyproj ``Geod``). Rastgele
      çiftlerde (a) UTM Öklid mesafesinin ve (b) küresel Haversine mesafesinin bu
      referansa göre göreli hatası AYRI raporlanır: (a) projeksiyonun ölçek faktörü
      hatasını, (b) küre yaklaşımının hatasını ölçer.
    """
    crs = CRS(target_crs)
    aou = crs.area_of_use
    lat = np.asarray(lat, dtype="float64")
    lon = np.asarray(lon, dtype="float64")
    inside = (lon >= aou.west) & (lon <= aou.east) & (lat >= aou.south) & (lat <= aou.north)
    rng = np.random.default_rng(seed)
    n = len(lat)
    if n < 2:
        return {"crs": target_crs, "area_of_use": aou.bounds, "all_inside_area_of_use": bool(inside.all())}
    i = rng.integers(0, n, size=min(sample, n))
    j = rng.integers(0, n, size=min(sample, n))
    x, y = project(lat, lon, target_crs)
    back = Transformer.from_crs(target_crs, "EPSG:4326", always_xy=True)
    lon_b, lat_b = back.transform(x[i], y[i])
    roundtrip = haversine_m(lat[i], lon[i], lat_b, lon_b)
    _, _, geodesic = Geod(ellps="WGS84").inv(lon[i], lat[i], lon[j], lat[j])
    geodesic = np.asarray(geodesic)
    hav = haversine_m(lat[i], lon[i], lat[j], lon[j])
    euc = np.hypot(x[i] - x[j], y[i] - y[j])
    keep = geodesic > 100  # çok kısa çiftlerde göreli hata anlamsız
    rel_proj = (euc[keep] - geodesic[keep]) / geodesic[keep]
    rel_hav = (hav[keep] - geodesic[keep]) / geodesic[keep]
    return {
        "crs": target_crs,
        "crs_name": crs.name,
        "area_of_use": aou.bounds,
        "all_inside_area_of_use": bool(inside.all()),
        "points_outside_area_of_use": int((~inside).sum()),
        "roundtrip_error_m_max": float(roundtrip.max()),
        "pair_sample": int(keep.sum()),
        "reference": "WGS84 elipsoidi jeodezik mesafe (pyproj.Geod)",
        "projection_rel_error_median": float(np.median(np.abs(rel_proj))),
        "projection_rel_error_max": float(np.max(np.abs(rel_proj))),
        "projection_rel_error_mean_signed": float(np.mean(rel_proj)),
        "haversine_rel_error_median": float(np.median(np.abs(rel_hav))),
        "haversine_rel_error_max": float(np.max(np.abs(rel_hav))),
        "seed": seed,
    }
