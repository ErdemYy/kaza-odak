// Kaza Odak marka simgesi (Faz 8 "Kaçınan rota" geometrisi, değişmedi). Kaynak: scripts/phase8_brand.py (cand_a) →
// scripts/kaza_odak_brand.py → assets/brand/kaza-odak-*.svg (aynı geometri).
// Kavram: kavşak ölçeğindeki kaza yoğunlaşmasından (kırmızı nokta) uzaklaşan, şehir ızgarasına oturan güvenli rota.
// ≤ 32 px'te ince ızgara çizgileri çizilmez (küçük boyutta piksel gürültüsü olur).
import { APP_NAME } from "../../lib/brand";

const C = { route: "#38BDF8", hot: "#F87171", halo: "#F59E0B", tile: "#111C30", grid: "#1E2D49", bg: "#0B1120" };

export function LogoMark({ size = 30, tile = true, grid = size > 32, title }: { size?: number; tile?: boolean; grid?: boolean; title?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" className="shrink-0" data-testid="brand-mark"
      role={title ? "img" : undefined} aria-label={title} aria-hidden={title ? undefined : true}>
      {tile && <rect width="48" height="48" rx="12" fill={C.tile} />}
      {grid && <path d="M16 6v36M32 6v36M6 16h36M6 32h36" stroke={C.grid} strokeWidth="1.25" />}
      <circle cx="16" cy="16" r="6.5" fill={C.halo} fillOpacity=".22" />
      <circle cx="16" cy="16" r="3.4" fill={C.hot} />
      <path d="M10 37h12a7 7 0 0 0 7-7V18a7 7 0 0 1 7-7h2" fill="none" stroke={C.route} strokeWidth="4.5" strokeLinecap="round" />
      <circle cx="10" cy="37" r="4.6" fill={C.route} />
      <circle cx="38" cy="11" r="4.4" fill={tile ? C.tile : C.bg} stroke={C.route} strokeWidth="3.2" />
    </svg>
  );
}

/** Wordmark: "Kaza" + vurgulu "Odak" (Plus Jakarta Sans; SVG kilidiyle aynı renk dengesi). Düz metindir; ekran okuyucu
 *  "Kaza Odak" okur (rolsüz öğeye aria-label verilmez — axe aria-prohibited-attr). */
export function Wordmark({ className }: { className?: string }) {
  const [first, second] = APP_NAME.split(" ");
  return (
    <span className={className} data-testid="brand-wordmark">{first} <span className="text-primary">{second}</span></span>
  );
}
