"""Kaza Odak marka varlıkları (SafeRoute 3D → Kaza Odak geçişi).

Faz 8 "Kaçınan rota" simgesi BİREBİR korunur (scripts/phase8_brand.py içindeki cand_a geometrisi yeniden kullanılır);
yalnızca marka kilidinin yazısı ("Kaza" + vurgulu "Odak") ve erişilebilir başlıklar değişir. Yazı Plus Jakarta Sans
ExtraBold glif yollarına çevrilir: SVG'de <text>, yazı tipi bağımlılığı veya dış kaynak yoktur.

Çalıştırma:  backend/.venv/Scripts/python scripts/kaza_odak_brand.py   (fontTools gerekir)
Çıktılar: assets/brand/kaza-odak-*.svg, assets/brand/favicon.svg, frontend/public/favicon.svg, frontend/public/brand/
Faz 8'in saferoute-*.svg dosyaları assets/brand altında tarihsel sürüm olarak kalır.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from phase8_brand import DARK, LIGHT, OUT, PUBLIC, cand_a, svg, text_path, tile, write  # noqa: E402

NAME = "Kaza Odak"
SUBTITLE = "Makine Öğrenmesi ile Trafik Kazalarının Mekânsal Analizi ve 3D Görselleştirilmesi"


def lockup(c: dict, mark: str, with_bg: bool) -> tuple[str, float]:
    """Simge + "Kaza" (metin rengi) + "Odak" (rota rengi). Faz 8 kilidiyle aynı taban çizgisi ve punto."""
    d1, w1 = text_path("Kaza", 25, 60, 32.5)
    d2, w2 = text_path("Odak", 25, 60 + w1 + 7, 32.5)
    width = 60 + w1 + 7 + w2 + 2
    bg = f'<rect width="{width + 24:.1f}" height="72" x="-12" y="-12" fill="{c["bg"]}"/>' if with_bg else ""
    body = f'{bg}<g>{mark}</g><path d="{d1}" fill="{c["text"]}"/><path d="{d2}" fill="{c["route"]}"/>'
    return body, width


def main() -> None:
    mark_dark, mark_light = cand_a(DARK), cand_a(LIGHT)
    mark_small = cand_a(DARK, grid=False)
    mono_c = {"route": "currentColor", "hot": "currentColor", "halo": "currentColor", "bg": "none", "grid": "none", "tile": "none", "text": "currentColor"}
    mark_mono = ('<circle cx="16" cy="16" r="6.3" fill="none" stroke="currentColor" stroke-width="1.5"/>'
                 '<circle cx="16" cy="16" r="3.2" fill="currentColor"/>'
                 '<path d="M10 37h12a7 7 0 0 0 7-7V18a7 7 0 0 1 7-7h2" fill="none" stroke="currentColor" stroke-width="4.5" stroke-linecap="round"/>'
                 '<circle cx="10" cy="37" r="4.6" fill="currentColor"/>'
                 '<circle cx="38" cy="11" r="4.4" fill="none" stroke="currentColor" stroke-width="3.2"/>')

    files: dict[str, str] = {
        "kaza-odak-mark.svg": svg(48, 48, mark_dark, f"{NAME} simgesi"),
        "kaza-odak-mark-light.svg": svg(48, 48, mark_light, f"{NAME} simgesi (açık zemin)"),
        "kaza-odak-mark-mono.svg": svg(48, 48, mark_mono, f"{NAME} simgesi (tek renk)"),
        "kaza-odak-app-icon.svg": svg(48, 48, tile(DARK, mark_dark), f"{NAME} uygulama simgesi"),
        "favicon.svg": svg(48, 48, tile(DARK, mark_small, rx=12), NAME),
    }
    body, wd = lockup(DARK, mark_dark, with_bg=False)
    files["kaza-odak-logo.svg"] = svg(wd, 48, body, NAME)
    body, wd = lockup(DARK, mark_dark, with_bg=True)
    files["kaza-odak-logo-on-dark.svg"] = svg(wd + 24, 72, f'<g transform="translate(12 12)">{body}</g>', f"{NAME} (koyu zemin)")
    body, wd = lockup(LIGHT, mark_light, with_bg=True)
    files["kaza-odak-logo-on-light.svg"] = svg(wd + 24, 72, f'<g transform="translate(12 12)">{body}</g>', f"{NAME} (açık zemin)")
    body, wd = lockup(mono_c, mark_mono, with_bg=False)
    files["kaza-odak-logo-mono.svg"] = svg(wd, 48, body, f"{NAME} (tek renk)")

    for name, content in files.items():
        write(OUT / name, content)
    write(PUBLIC / "favicon.svg", files["favicon.svg"])
    for name in ("kaza-odak-logo.svg", "kaza-odak-mark.svg", "kaza-odak-app-icon.svg", "kaza-odak-logo-on-light.svg", "kaza-odak-logo-mono.svg"):
        write(PUBLIC / "brand" / name, files[name])
    for name, content in sorted(files.items()):
        print(f"{name:32s} {len(content.encode()):6d} B")


if __name__ == "__main__":
    main()
