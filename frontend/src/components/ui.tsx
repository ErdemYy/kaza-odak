import type { ReactNode } from "react";

export function Switch({ checked, onChange, label, disabled }: { checked: boolean; onChange: () => void; label: string; disabled?: boolean }) {
  return <button type="button" role="switch" aria-checked={checked} aria-label={label} className="switch" onClick={onChange} disabled={disabled} />;
}

export function Stat({ label, value, tone }: { label: string; value: ReactNode; tone?: "primary" | "warning" | "hotspot" }) {
  const color = tone === "hotspot" ? "text-hotspot" : tone === "warning" ? "text-warning" : tone === "primary" ? "text-primary" : "text-text";
  return (
    <div className="min-w-0">
      <div className="text-[11px] text-muted leading-tight">{label}</div>
      <div className={`font-display font-bold text-[15px] tabular leading-snug ${color}`}>{value}</div>
    </div>
  );
}

export function Icon({ d, size = 16 }: { d: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={d} />
    </svg>
  );
}

export const ICONS = {
  plus: "M12 5v14M5 12h14",
  minus: "M5 12h14",
  rotL: "M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5",
  rotR: "M21 12a9 9 0 1 1-3-6.7L21 8M21 3v5h-5",
  up: "m6 15 6-6 6 6",
  down: "m6 9 6 6 6-6",
  compass: "M12 2 8 12l4 10 4-10z",
  home: "M3 11 12 3l9 8M5 10v10h14V10",
  close: "M6 6l12 12M18 6 6 18",
  cube: "M21 8 12 3 3 8v8l9 5 9-5zM3 8l9 5 9-5M12 13v8",
  sun: "M12 4V2M12 22v-2M4.9 4.9 3.5 3.5M20.5 20.5l-1.4-1.4M4 12H2M22 12h-2M4.9 19.1l-1.4 1.4M20.5 3.5l-1.4 1.4M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10z",
  moon: "M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z",
  layers: "m12 2 10 5-10 5L2 7zM2 17l10 5 10-5M2 12l10 5 10-5",
  target: "M12 2v4M12 18v4M2 12h4M18 12h4M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z",
};
