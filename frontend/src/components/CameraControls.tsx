import { Icon, ICONS } from "./ui";

export type CameraAction = "zoomIn" | "zoomOut" | "rotL" | "rotR" | "pitchUp" | "pitchDown" | "north" | "reset";

const BUTTONS: { a: CameraAction; label: string; icon: string }[] = [
  { a: "zoomIn", label: "Yakınlaştır", icon: ICONS.plus },
  { a: "zoomOut", label: "Uzaklaştır", icon: ICONS.minus },
  { a: "rotL", label: "Sola döndür (30°)", icon: ICONS.rotL },
  { a: "rotR", label: "Sağa döndür (30°)", icon: ICONS.rotR },
  { a: "pitchUp", label: "Eğimi artır", icon: ICONS.up },
  { a: "pitchDown", label: "Eğimi azalt", icon: ICONS.down },
  { a: "north", label: "Kuzeye çevir", icon: ICONS.compass },
  { a: "reset", label: "Görünümü sıfırla (tüm NYC)", icon: ICONS.home },
];

export function CameraControls({ onAction, bearing, readout, compact }: { onAction: (a: CameraAction) => void; bearing: number; readout: string; compact?: boolean }) {
  const buttons = compact ? BUTTONS.filter((b) => ["zoomIn", "zoomOut", "north", "reset"].includes(b.a)) : BUTTONS;
  return (
    <div className="panel p-1.5 flex items-center gap-1" role="toolbar" aria-label="Kamera kontrolleri" data-testid="camera-controls">
      {buttons.map((b) => (
        <button key={b.a} type="button" className="btn !p-2" aria-label={b.label} title={b.label} onClick={() => onAction(b.a)} data-action={b.a}>
          {b.a === "north" ? (
            <span style={{ transform: `rotate(${-bearing}deg)`, display: "inline-flex" }}><Icon d={b.icon} size={16} /></span>
          ) : <Icon d={b.icon} size={16} />}
        </button>
      ))}
      {!compact && <span className="px-2 text-[11.5px] tabular text-muted-foreground whitespace-nowrap hidden xl:inline" data-testid="camera-readout">{readout}</span>}
    </div>
  );
}
