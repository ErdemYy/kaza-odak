"""Faz 8B: önce/sonra ekran görüntülerini yan yana birleştirir ve piksel farkı özetini yazar.

Girdi: reports/phase8b/screenshots/{before,after}/*.png (aynı sahne, aynı kamera — e2e-visual/phase8b.visual.ts).
Çıktı: reports/phase8b/screenshots/karsilastirma/<sahne>.jpg ve fark_ozeti.json.
Fark ölçüsü yalnızca "ne kadar değişti" bilgisidir; "daha iyi" yargısı görsel incelemeyle verilir (GORSEL_KARSILASTIRMA.md).
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageStat

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "reports" / "phase8b" / "screenshots"


def main() -> None:
    out = BASE / "karsilastirma"
    out.mkdir(parents=True, exist_ok=True)
    summary: dict[str, dict[str, float | str]] = {}
    for before in sorted((BASE / "before").glob("*.png")):
        after = BASE / "after" / before.name
        if not after.exists():
            summary[before.stem] = {"durum": "sonra görüntüsü yok"}
            continue
        a, b = Image.open(before).convert("RGB"), Image.open(after).convert("RGB")
        if a.size != b.size:
            b = b.resize(a.size)
        diff = ImageChops.difference(a, b).convert("L")
        changed = sum(diff.histogram()[13:]) / (a.size[0] * a.size[1])  # fark > 12 olan piksellerin payı
        summary[before.stem] = {"degisen_piksel_orani": round(changed, 4), "ortalama_fark": round(ImageStat.Stat(diff).mean[0], 2)}
        gap, label_h = 16, 28
        canvas = Image.new("RGB", (a.size[0] * 2 + gap, a.size[1] + label_h), (11, 17, 32))
        canvas.paste(a, (0, label_h))
        canvas.paste(b, (a.size[0] + gap, label_h))
        draw = ImageDraw.Draw(canvas)
        draw.text((8, 7), "ONCE (Faz 8, fc7c176)", fill=(148, 163, 184))
        draw.text((a.size[0] + gap + 8, 7), "SONRA (Faz 8B)", fill=(56, 189, 248))
        canvas.save(out / f"{before.stem}.jpg", quality=84, optimize=True)  # birleşim yalnız inceleme amaçlı; kaynak PNG'ler ayrı
    (out / "fark_ozeti.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
