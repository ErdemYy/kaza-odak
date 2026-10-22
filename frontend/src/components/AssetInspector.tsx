import { MapPin, Trash2 } from "lucide-react";
import { useState } from "react";
import type { LngLat } from "../lib/geo";
import { fmtBytes, fmtInt, fmtNum } from "../lib/format";
import type { AssetRegistry } from "../lib/registry";
import type { InspectorPlacement } from "../map/threeLayer";
import { ModelPreview } from "./ModelPreview";
import { Icon, ICONS } from "./ui";

function Field({ label, value, step, onChange, testid, suffix }: { label: string; value: number; step: number; onChange: (v: number) => void; testid: string; suffix?: string }) {
  return (
    <label className="flex items-center justify-between gap-2 text-[12px]">
      <span className="text-muted-foreground">{label}</span>
      <span className="flex items-center gap-1">
        <input type="number" step={step} value={Number(value.toFixed(7))} data-testid={testid}
          onChange={(e) => Number.isFinite(e.target.valueAsNumber) && onChange(e.target.valueAsNumber)}
          className="w-[118px] rounded-md bg-surface-2 border border-line px-2 py-1 tabular text-right focus:outline-none focus:border-primary" />
        {suffix && <span className="text-subtle w-4">{suffix}</span>}
      </span>
    </label>
  );
}

// Faz 8B: model seçimi önizleyiciyi de açar. Faz 4/8 sözleşmesi korunur: model düğmesi modeli haritaya da yerleştirir
// (E08, viewer E). "Haritadan kaldır" sonrası önizleme açık kalır ve "Haritaya yerleştir" ile yeniden yerleştirilebilir.
export function AssetInspector({ registry, placement, onChange, onClose, onPlaceHere, error, mapCenter }: {
  registry: AssetRegistry | null; placement: InspectorPlacement | null; onChange: (p: InspectorPlacement | null) => void;
  onClose: () => void; onPlaceHere: () => void; error: string | null; mapCenter: LngLat;
}) {
  const [previewId, setPreviewId] = useState<string | null>(placement?.modelId ?? null);
  const shownId = placement?.modelId ?? previewId;
  const rec = registry?.models.find((m) => m.id === shownId) ?? null;
  const placed = !!placement && placement.modelId === rec?.id;
  const set = (patch: Partial<InspectorPlacement>) => placement && onChange({ ...placement, ...patch });
  const place = (modelId: string) => onChange({ modelId, lngLat: placement?.lngLat ?? mapCenter, altitudeM: 0, headingDeg: placement?.headingDeg ?? 29, scale: 1 });
  return (
    <aside className="p-3.5 space-y-3"
      aria-label="3D varlık inceleyici" data-testid="asset-inspector">
      <div className="flex items-center justify-between">
        <h2 className="panel-title">3D varlıklar (GLB)</h2>
        <button type="button" className="btn !p-1.5" onClick={onClose} aria-label="Kapat"><Icon d={ICONS.close} size={14} /></button>
      </div>
      {!registry && <div className="h-24 rounded-lg bg-surface-2 animate-pulse" role="status" aria-label="Varlık kaydı yükleniyor" />}
      {registry && (
        <>
          <div className="grid grid-cols-2 gap-1.5" role="group" aria-label="Model seçimi">
            {registry.models.map((m) => (
              <button key={m.id} type="button" className="btn !justify-start !min-h-[30px] !py-1" aria-pressed={shownId === m.id} data-model={m.id}
                onClick={() => { setPreviewId(m.id); place(m.id); }}>
                {m.name_tr}
              </button>
            ))}
          </div>
          {!rec && <p className="text-[12px] text-muted-foreground">Önizlemek ve haritaya yerleştirmek için bir model seçin.</p>}
          {rec && (
            <section className="space-y-2.5 rounded-xl border border-line bg-surface-2/40 p-3" aria-label={`${rec.name_tr} modeli`}>
              <div className="flex items-baseline justify-between gap-2">
                <h3 className="font-display font-bold text-[14px]" data-testid="preview-title">{rec.name_tr}</h3>
                <span className="text-[11px] text-subtle" data-testid="preview-license-short">
                  <a className="text-primary hover:underline" href={rec.license_url} target="_blank" rel="noopener">{rec.license.replace(/\s*\(.*\)$/, "")}</a> · {rec.author.replace(/\s*\(.*\)$/, "")}
                </span>
              </div>
              <ModelPreview record={rec} />
              <div className="flex flex-wrap items-center gap-1.5" data-testid="placement-status" data-placed={placed}>
                {placed ? (
                  <>
                    <span className="mr-auto inline-flex items-center gap-1 text-[11.5px] text-success"><MapPin className="size-3.5" aria-hidden /> Haritada</span>
                    <button type="button" className="btn !py-1 text-[11.5px]" onClick={onPlaceHere} data-testid="place-here">Harita merkezine taşı</button>
                    <button type="button" className="btn !py-1 text-[11.5px]" onClick={() => onChange(null)} data-testid="remove-model"><Trash2 className="size-3.5" aria-hidden /> Modeli kaldır</button>
                  </>
                ) : (
                  <>
                    <span className="mr-auto text-[11.5px] text-muted-foreground">Haritada değil</span>
                    <button type="button" className="btn !py-1 text-[11.5px]" onClick={() => place(rec.id)} data-testid="place-model"><MapPin className="size-3.5" aria-hidden /> Haritaya yerleştir</button>
                  </>
                )}
              </div>
              {placed && placement && (
                <details className="disclosure border-t border-line pt-2" open>
                  <summary className="text-[11.5px] font-semibold text-muted-foreground">Konum, yön ve ölçek</summary>
                  <div className="space-y-2 pt-2">
                    <Field label="Boylam" value={placement.lngLat[0]} step={0.00001} suffix="°" testid="insp-lng" onChange={(v) => set({ lngLat: [v, placement.lngLat[1]] })} />
                    <Field label="Enlem" value={placement.lngLat[1]} step={0.00001} suffix="°" testid="insp-lat" onChange={(v) => set({ lngLat: [placement.lngLat[0], v] })} />
                    <Field label="İrtifa (zeminden)" value={placement.altitudeM} step={0.5} suffix="m" testid="insp-alt" onChange={(v) => set({ altitudeM: v })} />
                    <Field label="Yön (kuzeyden)" value={placement.headingDeg} step={5} suffix="°" testid="insp-heading" onChange={(v) => set({ headingDeg: ((v % 360) + 360) % 360 })} />
                    <Field label="Ölçek çarpanı" value={placement.scale} step={0.25} testid="insp-scale" onChange={(v) => set({ scale: Math.min(20, Math.max(0.1, v)) })} />
                    <p className="text-[10.5px] text-subtle">Ölçek 1 = gerçek boyut ({fmtNum(rec.real_size_m, 1)} m {rec.measure === "length" ? "uzunluk" : "yükseklik"}).</p>
                  </div>
                </details>
              )}
            </section>
          )}
          {error && <div role="alert" className="rounded-lg border border-hotspot/50 bg-hotspot/10 p-2.5 text-[12px]">{error}</div>}
          {rec && (
            <details className="disclosure" open>
              <summary className="text-[11.5px] font-semibold text-muted-foreground">Kaynak ve lisans</summary>
              <dl className="text-[11.5px] space-y-1 pt-1.5" data-testid="asset-license">
                <div className="flex justify-between gap-2"><dt className="text-muted-foreground">Kaynak</dt><dd className="text-right"><a className="text-primary hover:underline" href={rec.source.source_url} target="_blank" rel="noopener">{rec.source.pack}</a></dd></div>
                <div className="flex justify-between gap-2"><dt className="text-muted-foreground">Yazar</dt><dd>{rec.author}</dd></div>
                <div className="flex justify-between gap-2"><dt className="text-muted-foreground">Lisans</dt><dd className="text-right"><a className="text-primary hover:underline" href={rec.license_url} target="_blank" rel="noopener">{rec.license}</a></dd></div>
                <div className="flex justify-between gap-2"><dt className="text-muted-foreground">Üçgen (LOD0 / LOD1)</dt><dd className="tabular">{fmtInt(rec.optimized.triangles)} / {rec.lod1 ? fmtInt(rec.lod1.triangles) : "—"}</dd></div>
                <div className="flex justify-between gap-2"><dt className="text-muted-foreground">Boyut (orijinal → web)</dt><dd className="tabular">{fmtBytes(rec.source.original_bytes)} → {fmtBytes(rec.optimized.bytes)}</dd></div>
                <div className="flex justify-between gap-2"><dt className="text-muted-foreground">Doku</dt><dd className="tabular">{rec.optimized.textures.map((t) => `${t.size[0]}×${t.size[1]}`).join(", ")}</dd></div>
              </dl>
              <p className="text-[11.5px] text-subtle pt-1">{rec.attribution}</p>
            </details>
          )}
          <p className="text-[10.5px] text-subtle leading-snug border-t border-line pt-2">
            {placement ? "Paneli kapatmak yerleştirilen modeli haritada bırakır; kaldırmak için \"Modeli kaldır\"ı kullanın. " : ""}
            Araç hareketleri temsili bir simülasyondur; geçmiş kazaların gerçek hareket kayıtlarını göstermez.
          </p>
        </>
      )}
    </aside>
  );
}
