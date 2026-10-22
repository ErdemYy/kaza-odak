"""Faz 8 marka varlıkları: üç logo adayı + seçilen logonun tüm varyantları (SVG).

Çalıştırma:  backend/.venv/Scripts/python scripts/phase8_brand.py   (veya fontTools kurulu herhangi bir Python)

Wordmark, Plus Jakarta Sans (OFL) glif yollarından üretilir: SVG yazı tipine bağımlı değildir, <text> veya
dış kaynak içermez. Çıktılar:
  assets/brand/candidates/   üç aday + karşılaştırma sayfası
  assets/brand/              seçilen logo (ana, simge, favicon, kenar çubuğu, açık/koyu, tek renk)
  frontend/public/           favicon.svg + brand/ kopyaları (uygulamada kullanılanlar)
"""
from __future__ import annotations

import shutil
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "deliverables" / "fonts" / "PlusJakartaSans-ExtraBold.ttf"
OUT = ROOT / "assets" / "brand"
CAND = OUT / "candidates"
PUBLIC = ROOT / "frontend" / "public"

# Marka paleti (PROJECT tasarım dili): koyu zemin ve açık zemin için kontrast ayarlı tonlar
DARK = {"route": "#38BDF8", "hot": "#F87171", "halo": "#F59E0B", "bg": "#0B1120", "tile": "#111C30", "grid": "#1E2D49", "text": "#F1F5F9"}
LIGHT = {"route": "#0284C7", "hot": "#DC2626", "halo": "#D97706", "bg": "#FFFFFF", "tile": "#F1F5F9", "grid": "#DCE3EC", "text": "#0B1120"}


def text_path(text: str, size: float, x: float, baseline: float, tracking: float = -0.015) -> tuple[str, float]:
    """Metni glif yollarına çevirir; (path d, genişlik) döndürür. tracking: em cinsinden harf aralığı."""
    font = TTFont(FONT)
    gs = font.getGlyphSet()
    cmap = font.getBestCmap()
    upm = font["head"].unitsPerEm
    s = size / upm
    pen = SVGPathPen(gs)
    cursor = 0.0
    for ch in text:
        g = cmap[ord(ch)]
        tp = TransformPen(pen, (s, 0, 0, -s, x + cursor, baseline))
        gs[g].draw(tp)
        cursor += font["hmtx"][g][0] * s + tracking * size
    return pen.getCommands(), cursor - tracking * size


# ------------------------------------------------------------------ adaylar (48×48 simge)

def cand_a(c: dict, grid: bool = True) -> str:
    """A — Kaçınan rota: kavşak ölçeğindeki sıcak noktadan uzaklaşan, ızgara sokaklarına oturan güvenli rota."""
    g = (f'<path d="M16 6v36M32 6v36M6 16h36M6 32h36" stroke="{c["grid"]}" stroke-width="1.25"/>' if grid else "")
    return (f'{g}<circle cx="16" cy="16" r="6.5" fill="{c["halo"]}" fill-opacity=".22"/>'
            f'<circle cx="16" cy="16" r="3.4" fill="{c["hot"]}"/>'
            f'<path d="M10 37h12a7 7 0 0 0 7-7V18a7 7 0 0 1 7-7h2" fill="none" stroke="{c["route"]}" stroke-width="4.5" stroke-linecap="round"/>'
            f'<circle cx="10" cy="37" r="4.6" fill="{c["route"]}"/>'
            f'<circle cx="38" cy="11" r="4.4" fill="{c["bg"]}" stroke="{c["route"]}" stroke-width="3.2"/>')


def cand_b(c: dict) -> str:
    """B — Ağ altıgeni: altıgen şehir paftası, merkezde sıcak nokta, bağlı analiz düğümleri."""
    return (f'<path d="M24 4.5 41 14.25v19.5L24 43.5 7 33.75v-19.5z" fill="none" stroke="{c["route"]}" stroke-width="3" stroke-linejoin="round"/>'
            f'<path d="M24 24 24 12.5M24 24 14 30M24 24 34 30" stroke="{c["route"]}" stroke-width="2.4" stroke-linecap="round"/>'
            f'<circle cx="24" cy="12.5" r="3" fill="{c["route"]}"/><circle cx="14" cy="30" r="3" fill="{c["route"]}"/><circle cx="34" cy="30" r="3" fill="{c["route"]}"/>'
            f'<circle cx="24" cy="24" r="6" fill="{c["halo"]}" fill-opacity=".22"/><circle cx="24" cy="24" r="3.4" fill="{c["hot"]}"/>')


def cand_c(c: dict) -> str:
    """C — İzometrik pafta: perspektifte şehir paftası, üzerinde kırık rota ve sıcak nokta (2,5B, efektsiz)."""
    return (f'<path d="M24 7 43 18 24 29 5 18z" fill="none" stroke="{c["route"]}" stroke-width="2.6" stroke-linejoin="round"/>'
            f'<path d="M5 25.5 24 36.5 43 25.5" fill="none" stroke="{c["route"]}" stroke-opacity=".55" stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round"/>'
            f'<path d="M5 33 24 44 43 33" fill="none" stroke="{c["route"]}" stroke-opacity=".3" stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round"/>'
            f'<path d="M13 18.5 21 14l10 6" fill="none" stroke="{c["route"]}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<circle cx="31" cy="20" r="3.4" fill="{c["hot"]}"/>')


CANDIDATES = {
    "a-kacinan-rota": ("A — Kaçınan rota", cand_a),
    "b-ag-altigeni": ("B — Ağ altıgeni", cand_b),
    "c-izometrik-pafta": ("C — İzometrik pafta", cand_c),
}


def svg(view_w: float, view_h: float, body: str, title: str, w: float | None = None, h: float | None = None) -> str:
    size = f' width="{w}" height="{h}"' if w else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {view_w:g} {view_h:g}"{size} role="img" aria-label="{title}">'
            f"<title>{title}</title>{body}</svg>\n")


def tile(c: dict, inner: str, rx: float = 11) -> str:
    """Uygulama simgesi: koyu/açık zemin karosu içinde simge (favicon, kenar çubuğu)."""
    return f'<rect width="48" height="48" rx="{rx}" fill="{c["tile"]}"/>{inner}'


def lockup(c: dict, mark: str, with_bg: bool) -> tuple[str, float]:
    d1, w1 = text_path("SafeRoute", 25, 60, 32.5)
    d2, w2 = text_path("3D", 25, 60 + w1 + 6, 32.5)
    width = 60 + w1 + 6 + w2 + 2
    bg = f'<rect width="{width + 24:.1f}" height="72" x="-12" y="-12" fill="{c["bg"]}"/>' if with_bg else ""
    body = (f"{bg}<g>{mark}</g>"
            f'<path d="{d1}" fill="{c["text"]}"/><path d="{d2}" fill="{c["route"]}"/>')
    return body, width


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    # 1) Adaylar: koyu zemin, 4 boyutta + tek renk; karşılaştırma sayfası (Playwright ile görüntülenir)
    cells = []
    for key, (label, fn) in CANDIDATES.items():
        dark = fn(DARK)
        mono = fn({k: "#F1F5F9" for k in DARK} | {"bg": DARK["bg"], "grid": "#F1F5F926", "tile": DARK["tile"]})
        write(CAND / f"{key}.svg", svg(48, 48, dark, f"SafeRoute 3D aday {label}"))
        sizes = "".join(f'<div class="s"><svg viewBox="0 0 48 48" width="{px}" height="{px}">{tile(DARK, dark)}</svg><span>{px}px</span></div>'
                        for px in (128, 48, 32, 16))
        light = f'<div class="s light"><svg viewBox="0 0 48 48" width="48" height="48">{tile(LIGHT, fn(LIGHT))}</svg><span>açık</span></div>'
        monos = f'<div class="s"><svg viewBox="0 0 48 48" width="48" height="48">{mono}</svg><span>tek renk</span></div>'
        cells.append(f'<section><h2>{label}</h2><div class="row">{sizes}{light}{monos}</div></section>')
    write(CAND / "karsilastirma.html", (
        "<!doctype html><html lang='tr'><meta charset='utf-8'><title>Logo adayları</title><style>"
        "body{margin:0;padding:24px;background:#0B1120;color:#F1F5F9;font:14px Manrope,system-ui,sans-serif}"
        "section{margin-bottom:22px}h2{font-size:15px;margin:0 0 10px}.row{display:flex;gap:22px;align-items:flex-end}"
        ".s{display:flex;flex-direction:column;align-items:center;gap:6px;color:#94A3B8;font-size:12px}"
        ".light{background:#fff;padding:8px;border-radius:8px;color:#475569}</style>" + "".join(cells) + "</html>\n"))

    # 2) Seçilen logo (A) — varyantlar
    mark_dark, mark_light = cand_a(DARK), cand_a(LIGHT)
    mark_small = cand_a(DARK, grid=False)  # ≤ 32 px: ince ızgara çizgileri kaldırılır (piksel gürültüsü)
    mono_c = {"route": "currentColor", "hot": "currentColor", "halo": "currentColor", "bg": "none", "grid": "none", "tile": "none", "text": "currentColor"}
    mark_mono = (f'<circle cx="16" cy="16" r="6.3" fill="none" stroke="currentColor" stroke-width="1.5"/>'
                 f'<circle cx="16" cy="16" r="3.2" fill="currentColor"/>'
                 f'<path d="M10 37h12a7 7 0 0 0 7-7V18a7 7 0 0 1 7-7h2" fill="none" stroke="currentColor" stroke-width="4.5" stroke-linecap="round"/>'
                 f'<circle cx="10" cy="37" r="4.6" fill="currentColor"/>'
                 f'<circle cx="38" cy="11" r="4.4" fill="none" stroke="currentColor" stroke-width="3.2"/>')

    files: dict[str, str] = {}
    files["saferoute-mark.svg"] = svg(48, 48, mark_dark, "SafeRoute 3D simgesi")
    files["saferoute-mark-light.svg"] = svg(48, 48, mark_light, "SafeRoute 3D simgesi (açık zemin)")
    files["saferoute-mark-mono.svg"] = svg(48, 48, mark_mono, "SafeRoute 3D simgesi (tek renk)")
    files["saferoute-app-icon.svg"] = svg(48, 48, tile(DARK, mark_dark), "SafeRoute 3D uygulama simgesi")
    files["saferoute-sidebar.svg"] = svg(48, 48, tile(DARK, mark_small, rx=12), "SafeRoute 3D")
    files["favicon.svg"] = svg(48, 48, tile(DARK, mark_small, rx=12), "SafeRoute 3D")
    body, wd = lockup(DARK, mark_dark, with_bg=False)
    files["saferoute-logo.svg"] = svg(wd, 48, body, "SafeRoute 3D")
    body, wd = lockup(DARK, mark_dark, with_bg=True)
    files["saferoute-logo-on-dark.svg"] = svg(wd + 24, 72, f'<g transform="translate(12 12)">{body}</g>', "SafeRoute 3D (koyu zemin)")
    body, wd = lockup(LIGHT, mark_light, with_bg=True)
    files["saferoute-logo-on-light.svg"] = svg(wd + 24, 72, f'<g transform="translate(12 12)">{body}</g>', "SafeRoute 3D (açık zemin)")
    body, wd = lockup(mono_c, mark_mono, with_bg=False)
    files["saferoute-logo-mono.svg"] = svg(wd, 48, body, "SafeRoute 3D (tek renk)")

    for name, content in files.items():
        write(OUT / name, content)
    # Uygulamada kullanılanlar
    write(PUBLIC / "favicon.svg", files["favicon.svg"])
    for name in ("saferoute-logo.svg", "saferoute-mark.svg", "saferoute-app-icon.svg", "saferoute-logo-on-light.svg", "saferoute-logo-mono.svg"):
        write(PUBLIC / "brand" / name, files[name])
    shutil.copyfile(ROOT / "deliverables" / "fonts" / "OFL-PlusJakartaSans.txt", OUT / "OFL-PlusJakartaSans.txt")
    for name, content in sorted(files.items()):
        print(f"{name:34s} {len(content.encode()):6d} B")


if __name__ == "__main__":
    main()
