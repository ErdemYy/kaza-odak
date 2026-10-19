import type { MotionLevel } from "../lib/layers";
import type { Theme } from "../map/style";
import { Icon, ICONS } from "./ui";

export type LoadState = { phase: "loading" | "ready" | "error"; message: string };

export function TopBar({ load, theme, onTheme, motion, onMotion, onAssets, assetsOpen }: {
  load: LoadState; theme: Theme; onTheme: () => void; motion: MotionLevel; onMotion: (m: MotionLevel) => void;
  onAssets: () => void; assetsOpen: boolean;
}) {
  const dot = load.phase === "ready" ? "bg-emerald-400" : load.phase === "error" ? "bg-hotspot" : "bg-warning animate-pulse";
  return (
    <header className="absolute top-3 left-3 right-3 z-20 flex items-center gap-3 pointer-events-none">
      <div className="panel pointer-events-auto flex items-center gap-3 px-4 py-2.5">
        <svg width="26" height="26" viewBox="0 0 32 32" aria-hidden="true">
          <rect width="32" height="32" rx="8" fill="#16233B" />
          <circle cx="16" cy="16" r="7.5" fill="none" stroke="#38BDF8" strokeWidth="2.5" />
          <circle cx="16" cy="16" r="2.6" fill="#F87171" />
        </svg>
        <div>
          <h1 className="font-display font-bold text-[17px] leading-none tracking-tight">SafeRoute 3D</h1>
          <p className="text-[11.5px] text-muted leading-tight mt-0.5">New York kaza kümeleri · 3D şehir görüntüleyici</p>
        </div>
      </div>
      <div role="status" aria-live="polite" data-testid="load-status" data-phase={load.phase}
        className="panel pointer-events-auto hidden md:flex items-center gap-2 px-3 py-2 text-[12.5px] max-w-[460px]">
        <span className={`w-2 h-2 rounded-full flex-none ${dot}`} />
        <span className="truncate">{load.message}</span>
      </div>
      <div className="flex-1" />
      <div className="panel pointer-events-auto flex items-center gap-1.5 p-1.5">
        <button type="button" className="btn" aria-pressed={assetsOpen} onClick={onAssets} data-testid="assets-toggle">
          <Icon d={ICONS.cube} size={15} /> 3D varlıklar
        </button>
        <button type="button" className="btn" onClick={onTheme} data-testid="theme-toggle" aria-label={theme === "night" ? "Gündüz moduna geç" : "Gece moduna geç"}>
          <Icon d={theme === "night" ? ICONS.moon : ICONS.sun} size={15} /> {theme === "night" ? "Gece" : "Gündüz"}
        </button>
        <label className="sr-only" htmlFor="motion">Animasyon düzeyi</label>
        <select id="motion" data-testid="motion-select" value={motion} onChange={(e) => onMotion(e.target.value as MotionLevel)}
          className="btn pr-2 appearance-none" title="Animasyon düzeyi">
          <option value="full">Animasyon: tam</option>
          <option value="reduced">Animasyon: azaltılmış</option>
          <option value="off">Animasyon: kapalı</option>
        </select>
      </div>
    </header>
  );
}
