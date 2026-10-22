"""Faz 8 işlevsel test envanteri: reports/phase8/interaction_results.json → Markdown tablo (stdout).

Çalıştırma: backend/.venv/Scripts/python scripts/phase8_inventory.py [sonuç.json]
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def cell(s: str) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ").strip()


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "reports" / "phase8" / "interaction_results.json"
    d = json.loads(src.read_text(encoding="utf-8"))
    recs = d["records"]
    by_screen = Counter(r["screen"] for r in recs)
    ok = Counter(r["screen"] for r in recs if r["result"] == "geçti")
    print(f"Kaynak: `{src.relative_to(ROOT).as_posix()}` · üretim {d['generated_at']}\n")
    print(f"**Toplam {d['total']} etkileşim · {d['passed']} geçti · {d['failed']} başarısız**\n")
    print("| Ekran | Etkileşim | Geçti | Başarısız |\n|---|---:|---:|---:|")
    for s, n in sorted(by_screen.items()):
        print(f"| {s} | {n} | {ok[s]} | {n - ok[s]} |")
    print("\n| Kimlik | Ekran | Bileşen | Beklenen davranış | Gerçek davranış (ölçülen) | Sonuç | Neden (başarısızsa) |")
    print("|---|---|---|---|---|---|---|")
    for r in recs:
        mark = "✅ geçti" if r["result"] == "geçti" else "❌ başarısız"
        print(f"| {r['id']} | {cell(r['screen'])} | {cell(r['component'])} | {cell(r['expected'])} | {cell(r['actual'])} | {mark} | {cell(r.get('cause', ''))} |")


if __name__ == "__main__":
    main()
