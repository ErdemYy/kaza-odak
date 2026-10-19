"""EDA şekilleri (PNG). Tüm şekiller yalnızca profil sözlüğündeki ölçülmüş değerlerden çizilir."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

PRIMARY = "#0284C7"
WARNING = "#D97706"
HOTSPOT = "#DC2626"
MUTED = "#64748B"

BOROUGH_TR = {
    "MANHATTAN": "Manhattan",
    "BROOKLYN": "Brooklyn",
    "QUEENS": "Queens",
    "BRONX": "Bronx",
    "STATEN ISLAND": "Staten Island",
}
COORD_CLASS_TR = {
    "missing": "Eksik",
    "unparseable": "Ayrıştırılamaz",
    "zero": "Sıfır (0,0)",
    "outside_nyc_bbox": "NYC kutusu dışı",
    "valid_in_bbox": "Geçerli",
}
WEEKDAY_TR = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]


def _style(ax, title: str, xlabel: str = "", ylabel: str = "") -> None:
    ax.set_title(title, fontsize=12, loc="left", fontweight="bold")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.25)


def _thousands(ax, axis: str = "y") -> None:
    fmt = matplotlib.ticker.FuncFormatter(lambda v, _: f"{int(v):,}".replace(",", "."))
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def _save(fig, path: Path) -> Path:
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def plot_rows_per_year(profile: dict[str, Any], out: Path) -> Path:
    data = profile["temporal"]["rows_per_year"]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(list(data), list(data.values()), color=PRIMARY)
    _style(ax, "Yıllara göre kayıtlı çarpışma sayısı", "Yıl", "Kayıt")
    _thousands(ax)
    ax.tick_params(axis="x", rotation=45)
    return _save(fig, out / "rows_per_year.png")


def plot_rows_per_month(profile: dict[str, Any], out: Path) -> Path:
    data = profile["temporal"]["rows_per_month"]
    keys = list(data)
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(range(len(keys)), list(data.values()), color=PRIMARY, linewidth=1.4)
    ticks = [i for i, k in enumerate(keys) if k.endswith("-01")]
    ax.set_xticks(ticks, [keys[i][:4] for i in ticks], rotation=45)
    _style(ax, "Aylara göre kayıtlı çarpışma sayısı", "Ay", "Kayıt")
    _thousands(ax)
    return _save(fig, out / "rows_per_month.png")


def plot_rows_per_hour(profile: dict[str, Any], out: Path) -> Path:
    data = profile["temporal"]["rows_per_hour"]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar([int(k) for k in data], list(data.values()), color=PRIMARY)
    _style(ax, "Saate göre kayıtlı çarpışma sayısı (crash_time)", "Saat", "Kayıt")
    ax.set_xticks(range(24))
    _thousands(ax)
    return _save(fig, out / "rows_per_hour.png")


def plot_rows_per_weekday(profile: dict[str, Any], out: Path) -> Path:
    data = profile["temporal"]["rows_per_weekday"]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar([WEEKDAY_TR[int(k)] for k in data], list(data.values()), color=PRIMARY)
    _style(ax, "Haftanın gününe göre kayıt sayısı", "", "Kayıt")
    _thousands(ax)
    return _save(fig, out / "rows_per_weekday.png")


def plot_boroughs(profile: dict[str, Any], out: Path) -> Path:
    b = profile["boroughs"]
    labels = [BOROUGH_TR.get(k, k) for k in b["counts"]] + ["Eksik"]
    values = list(b["counts"].values()) + [b["missing"]]
    colors = [PRIMARY] * len(b["counts"]) + [MUTED]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(labels, values, color=colors)
    _style(ax, "İlçe (borough) alanına göre kayıt sayısı", "", "Kayıt")
    _thousands(ax)
    return _save(fig, out / "boroughs.png")


def plot_missing(profile: dict[str, Any], out: Path) -> Path:
    mv = {k: v["missing_pct"] for k, v in profile["missing_values"].items() if v["missing_total"] > 0}
    items = sorted(mv.items(), key=lambda kv: kv[1])
    fig, ax = plt.subplots(figsize=(9, max(3, 0.32 * len(items))))
    ax.barh([k for k, _ in items], [v for _, v in items], color=WARNING)
    _style(ax, "Sütunlara göre eksik değer oranı (%)", "%", "")
    ax.grid(axis="x", alpha=0.25)
    ax.set_xlim(0, 100)
    return _save(fig, out / "missing_values.png")


def plot_coordinate_classes(profile: dict[str, Any], out: Path) -> Path:
    classes = profile["coordinates"]["classes"]
    fig, ax = plt.subplots(figsize=(8, 4))
    colors = [MUTED, WARNING, HOTSPOT, HOTSPOT, PRIMARY]
    ax.bar([COORD_CLASS_TR[k] for k in classes], list(classes.values()), color=colors)
    _style(ax, "Koordinat kalite sınıfları", "", "Kayıt")
    _thousands(ax)
    return _save(fig, out / "coordinate_classes.png")


def plot_quality_by_year(profile: dict[str, Any], out: Path) -> Path:
    q = profile["quality_by_year"]
    years = list(q)
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(years, [q[y]["coord_valid_pct"] for y in years], marker="o", color=PRIMARY, label="Geçerli koordinat")
    ax.plot(years, [q[y]["borough_present_pct"] for y in years], marker="s", color=WARNING, label="İlçe alanı dolu")
    _style(ax, "Yıllara göre alan doluluk oranı (%)", "Yıl", "%")
    ax.set_ylim(0, 100)
    ax.legend(frameon=False)
    ax.tick_params(axis="x", rotation=45)
    return _save(fig, out / "quality_by_year.png")


def plot_top_factors(profile: dict[str, Any], out: Path, top_n: int = 15) -> Path:
    data = list(profile["categoricals"]["contributing_factor_1_top"].items())[:top_n][::-1]
    fig, ax = plt.subplots(figsize=(9, 0.38 * len(data) + 1))
    ax.barh([k for k, _ in data], [v for _, v in data], color=PRIMARY)
    _style(ax, f"En sık {top_n} katkıda bulunan faktör (araç 1)", "Kayıt", "")
    ax.grid(axis="x", alpha=0.25)
    _thousands(ax, "x")
    return _save(fig, out / "top_contributing_factors.png")


def plot_vehicle_types(profile: dict[str, Any], out: Path, top_n: int = 15) -> Path:
    data = list(profile["categoricals"]["vehicle_type_1_top_normalized"].items())[:top_n][::-1]
    fig, ax = plt.subplots(figsize=(9, 0.38 * len(data) + 1))
    ax.barh([k for k, _ in data], [v for _, v in data], color=PRIMARY)
    _style(ax, f"En sık {top_n} araç türü (araç 1, büyük harf + kırpma sonrası)", "Kayıt", "")
    ax.grid(axis="x", alpha=0.25)
    _thousands(ax, "x")
    return _save(fig, out / "vehicle_types.png")


def plot_casualties(profile: dict[str, Any], out: Path) -> Path:
    """Yol kullanıcısı türüne göre yaralı ve ölü toplamları (iki ayrı ölçek, aldatıcı ortak eksen yok)."""
    cols = profile["casualties"]["columns"]
    groups = [("pedestrians", "Yaya"), ("cyclist", "Bisikletli"), ("motorist", "Motorlu araç")]
    injured = [cols[f"number_of_{g}_injured"]["sum"] for g, _ in groups]
    killed = [cols[f"number_of_{g}_killed"]["sum"] for g, _ in groups]
    labels = [t for _, t in groups]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4))
    a1.bar(labels, injured, color=WARNING)
    _style(a1, "Yaralı kişi toplamı", "", "Kişi")
    _thousands(a1)
    a2.bar(labels, killed, color=HOTSPOT)
    _style(a2, "Ölen kişi toplamı", "", "Kişi")
    _thousands(a2)
    return _save(fig, out / "casualties_by_road_user.png")


def plot_borough_coordinate_quality(profile: dict[str, Any], out: Path) -> Path:
    table = profile["borough_by_coordinate_class"]
    rows = list(table)
    labels = [BOROUGH_TR.get(r, {"MISSING": "İlçe eksik", "UNEXPECTED": "Beklenmeyen"}.get(r, r)) for r in rows]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    left = np.zeros(len(rows))
    colors = {"valid_in_bbox": PRIMARY, "missing": MUTED, "zero": HOTSPOT, "outside_nyc_bbox": WARNING,
              "unparseable": "#7C3AED"}
    for cls in ("valid_in_bbox", "missing", "zero", "outside_nyc_bbox", "unparseable"):
        vals = np.array([table[r][cls] for r in rows], dtype=float)
        if vals.sum() == 0:
            continue
        ax.barh(labels, vals, left=left, color=colors[cls], label=COORD_CLASS_TR[cls])
        left += vals
    _style(ax, "Kaydedilmiş ilçeye göre koordinat kalitesi", "Kayıt", "")
    ax.grid(axis="x", alpha=0.25)
    _thousands(ax, "x")
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    return _save(fig, out / "borough_coordinate_quality.png")


def plot_hexbin(lat: np.ndarray, lon: np.ndarray, out: Path) -> Path:
    """Geçerli koordinatların yoğunluk haritası (log ölçek). Kümeleme DEĞİLDİR.

    Örnekleme yapılmaz: geçerli koordinatlı kayıtların tamamı altıgen hücrelere toplanır.
    """
    fig, ax = plt.subplots(figsize=(7.5, 8))
    hb = ax.hexbin(lon, lat, gridsize=220, bins="log", cmap="inferno", mincnt=1)
    ax.set_aspect(1 / np.cos(np.deg2rad(40.7)))
    ax.set_title(f"Geçerli koordinatlı kayıtların mekânsal yoğunluğu\n(tüm {len(lat):,} kayıt, örnekleme yok; log ölçek)"
                 .replace(",", "."), fontsize=12, loc="left", fontweight="bold")
    ax.set_xlabel("Boylam")
    ax.set_ylabel("Enlem")
    fig.colorbar(hb, ax=ax, shrink=0.7, label="Kayıt sayısı (log10)")
    return _save(fig, out / "spatial_density_hexbin.png")


def render_all(profile: dict[str, Any], out: Path, lat: np.ndarray | None = None, lon: np.ndarray | None = None) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    paths = [
        plot_rows_per_year(profile, out),
        plot_rows_per_month(profile, out),
        plot_rows_per_hour(profile, out),
        plot_rows_per_weekday(profile, out),
        plot_boroughs(profile, out),
        plot_missing(profile, out),
        plot_coordinate_classes(profile, out),
        plot_quality_by_year(profile, out),
        plot_top_factors(profile, out),
        plot_vehicle_types(profile, out),
        plot_casualties(profile, out),
        plot_borough_coordinate_quality(profile, out),
    ]
    if lat is not None and lon is not None and len(lat):
        paths.append(plot_hexbin(lat, lon, out))
    return paths
