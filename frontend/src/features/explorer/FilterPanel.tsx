// Kayıt filtreleri. Filtreler sunucuda GERÇEK kayıtlara uygulanır. İki ayrı eylem:
//  1) "Mevcut kümelerde göster": tam veri modelinin etiketleriyle filtrelenmiş kayıtlar (yeniden kümeleme YOK)
//  2) "Yeni kümeleme başlat": Laboratuvar'a filtre kapsamıyla geçer; kümeleme orada açıkça başlatılır
import { FlaskConical, Layers, RotateCcw } from "lucide-react";
import { useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { cn } from "@/lib/utils";
import { useApp } from "../../app/store";
import { InfoTip } from "../../components/common";
import { BOROUGH_ORDER, BOROUGH_TR } from "../../lib/camera";
import { DOWS_SHORT, isEmpty, MONTHS_TR, toQuery, validate, type FilterState } from "../../lib/filters";
import { fmtInt, fmtPct, trLabel } from "../../lib/format";
import { useQuery } from "../../lib/query";
import type { FilterOptions, RecordsSummary } from "../../lib/types";

function Chip({ pressed, onClick, children, title, testId, partial }: { pressed: boolean; onClick: () => void; children: React.ReactNode; title?: string; testId?: string; partial?: boolean }) {
  return (
    <button type="button" aria-pressed={pressed} onClick={onClick} title={title} data-testid={testId}
      className={cn("h-8 rounded-md border px-2.5 text-[12.5px] font-semibold transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring tabular",
        pressed ? "border-primary bg-primary/15 text-foreground" : "border-line text-muted-foreground hover:border-line-strong hover:text-foreground",
        partial && "border-dashed")}>
      {children}
    </button>
  );
}

function Group({ label, children, info, htmlFor }: { label: string; children: React.ReactNode; info?: React.ReactNode; htmlFor?: string }) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1.5">
        {htmlFor ? <Label htmlFor={htmlFor} className="text-[12.5px] font-semibold text-foreground">{label}</Label>
          : <span className="text-[12.5px] font-semibold text-foreground" role="heading" aria-level={3}>{label}</span>}
        {info && <InfoTip>{info}</InfoTip>}
      </div>
      {children}
    </div>
  );
}

const toggle = <T,>(arr: T[], v: T) => (arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);

export function FilterPanel({ onStartLab }: { onStartLab: () => void }) {
  const draft = useApp((s) => s.draft);
  const applied = useApp((s) => s.applied);
  const setDraft = useApp((s) => s.setDraft);
  const applyDraft = useApp((s) => s.applyDraft);
  const reset = useApp((s) => s.resetFilters);
  const opts = useQuery<FilterOptions>("/api/filters/options", { ttlMs: 30 * 60_000 });
  const errors = validate(draft);
  const q = toQuery(draft);
  const preview = useQuery<RecordsSummary>(errors.length ? null : `/api/records/summary${q ? `?${q}` : ""}`, { debounceMs: 350 });
  const dirty = toQuery(draft) !== toQuery(applied);
  const o = opts.data;
  const partialYears = useMemo(() => {
    if (!o) return new Set<number>();
    const s = new Set<number>();
    if (!o.date_min.endsWith("-01-01")) s.add(Number(o.date_min.slice(0, 4)));
    if (!o.date_max.endsWith("-12-31")) s.add(Number(o.date_max.slice(0, 4)));
    return s;
  }, [o]);
  const hourOn = draft.hourFrom !== null && draft.hourTo !== null;
  const set = (p: Partial<FilterState>) => setDraft(p);

  return (
    <div className="flex min-h-0 flex-1 flex-col" data-testid="filter-panel">
      <div className="min-h-0 flex-1 overflow-y-auto scroll-thin space-y-5 pr-1">
        <p className="text-[12px] text-muted-foreground leading-snug">
          Filtreler sunucuda gerçek kaza kayıtlarına uygulanır. Payda: kümelemeye uygun {o ? fmtInt(o.n_events) : "…"} kayıt
          (geçerli NYC koordinatı ve tarih).
        </p>

        <Group label="İlçe">
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="İlçe filtresi">
            {BOROUGH_ORDER.map((b) => (
              <Chip key={b} pressed={draft.boroughs.includes(b)} onClick={() => set({ boroughs: toggle(draft.boroughs, b) })} testId={`f-borough-${b}`}>
                {BOROUGH_TR[b]}
              </Chip>
            ))}
          </div>
        </Group>

        <Group label="Tarih aralığı" info="Başlangıç ve bitiş günü dahildir. Tek bir günü incelemek için iki alana aynı tarihi girin.">
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <Label htmlFor="f-date-from" className="text-[11.5px] text-muted-foreground">Başlangıç</Label>
              <Input id="f-date-from" type="date" value={draft.dateFrom ?? ""} min={o?.date_min} max={o?.date_max}
                onChange={(e) => set({ dateFrom: e.target.value || null })} className="h-9 tabular" aria-invalid={errors.length > 0 && !!draft.dateFrom} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="f-date-to" className="text-[11.5px] text-muted-foreground">Bitiş</Label>
              <Input id="f-date-to" type="date" value={draft.dateTo ?? ""} min={o?.date_min} max={o?.date_max}
                onChange={(e) => set({ dateTo: e.target.value || null })} className="h-9 tabular" />
            </div>
          </div>
          {o && <p className="text-[11.5px] text-subtle">Veri kapsamı: {o.date_min} → {o.date_max}</p>}
        </Group>

        <Group label="Yıl" info="Kesikli kenarlı yıllar kısmidir: veri kapsamı yılın tamamını içermez.">
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Yıl filtresi">
            {(o?.years ?? []).map((y) => (
              <Chip key={y.year} pressed={draft.years.includes(y.year)} onClick={() => set({ years: toggle(draft.years, y.year) })}
                partial={partialYears.has(y.year)} title={`${fmtInt(y.count)} kayıt${partialYears.has(y.year) ? " · kısmi yıl" : ""}`} testId={`f-year-${y.year}`}>
                {y.year}
              </Chip>
            ))}
          </div>
        </Group>

        <Group label="Ay">
          <div className="grid grid-cols-6 gap-1.5" role="group" aria-label="Ay filtresi">
            {MONTHS_TR.map((m, i) => (
              <Chip key={m} pressed={draft.months.includes(i + 1)} onClick={() => set({ months: toggle(draft.months, i + 1) })} title={m}>{m.slice(0, 3)}</Chip>
            ))}
          </div>
        </Group>

        <Group label="Haftanın günü">
          <div className="grid grid-cols-7 gap-1" role="group" aria-label="Gün filtresi">
            {DOWS_SHORT.map((d, i) => (
              <Chip key={d} pressed={draft.dows.includes(i)} onClick={() => set({ dows: toggle(draft.dows, i) })}>{d}</Chip>
            ))}
          </div>
        </Group>

        <Group label="Saat aralığı" htmlFor="f-hour-on"
          info="Kapsayıcı aralık. Başlangıç bitişten büyükse gece yarısını aşar (ör. 22–04). 00:00 kayıtlarının bir kısmı saati bilinmeyen kayıtlar olabilir.">
          <div className="flex items-center gap-2.5">
            <Switch id="f-hour-on" checked={hourOn} onCheckedChange={(on) => set(on ? { hourFrom: 7, hourTo: 10 } : { hourFrom: null, hourTo: null })} />
            <span className="text-[12.5px] tabular text-muted-foreground" aria-live="polite">
              {hourOn ? `${String(draft.hourFrom).padStart(2, "0")}:00 – ${String(draft.hourTo).padStart(2, "0")}:59${draft.hourFrom! > draft.hourTo! ? " (gece yarısını aşar)" : ""}` : "Tüm saatler"}
            </span>
          </div>
          {hourOn && (
            <div className="grid grid-cols-2 gap-2 pt-1">
              {(["hourFrom", "hourTo"] as const).map((k) => (
                <div key={k} className="space-y-1">
                  <Label htmlFor={`f-${k}`} className="text-[11.5px] text-muted-foreground">{k === "hourFrom" ? "Başlangıç saati" : "Bitiş saati (dahil)"}</Label>
                  <Select value={String(draft[k])} onValueChange={(v) => set({ [k]: Number(v) })}>
                    <SelectTrigger id={`f-${k}`} className="w-full h-9 tabular"><SelectValue /></SelectTrigger>
                    <SelectContent className="max-h-[280px]">
                      {Array.from({ length: 24 }, (_, h) => (
                        <SelectItem key={h} value={String(h)} className="tabular">{String(h).padStart(2, "0")}:00{k === "hourTo" ? "–" + String(h).padStart(2, "0") + ":59" : ""}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              ))}
              <button type="button" className="col-span-2 justify-self-start text-[11.5px] text-primary hover:underline" onClick={() => set({ hourFrom: 22, hourTo: 4 })}>
                Gece aralığı örneği: 22:00–04:59
              </button>
            </div>
          )}
        </Group>

        <Group label="Araç türü" info="Kazaya karışan araçlardan en az biri seçilen kategoride (Faz 2 kural tabanlı normalizasyon, 12 kategori).">
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Araç türü filtresi">
            {(o?.vehicles ?? []).map((v) => (
              <Chip key={v.value} pressed={draft.vehicles.includes(v.value)} onClick={() => set({ vehicles: toggle(draft.vehicles, v.value) })}
                title={`${fmtInt(v.count)} kaza`} testId={`f-vehicle-${v.value}`}>{trLabel(v.value)}</Chip>
            ))}
          </div>
        </Group>

        <Group label="Kaydedilmiş katkı faktörü" htmlFor="f-factor"
          info="NYPD'nin kayda geçirdiği etken (beş araç alanından herhangi biri). Nedensellik kanıtı değildir; metinler kaynak veri setindeki İngilizce kodlardır.">
          <Select value={draft.factor ?? "__any"} onValueChange={(v) => set({ factor: v === "__any" ? null : v })}>
            <SelectTrigger id="f-factor" className="w-full h-9"><SelectValue placeholder="Tümü" /></SelectTrigger>
            <SelectContent className="max-h-[320px]">
              <SelectItem value="__any">Tümü</SelectItem>
              {(o?.factors ?? []).map((f) => (
                <SelectItem key={f.value} value={f.value}>{f.value} <span className="text-subtle tabular">· {fmtInt(f.count)}</span></SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Group>

        <Group label="Yaralanma durumu">
          <ToggleGroup type="single" variant="outline" size="sm" value={draft.injury} onValueChange={(v) => v && set({ injury: v as FilterState["injury"] })} aria-label="Yaralanma durumu" className="w-full">
            <ToggleGroupItem value="any" className="flex-1">Tümü</ToggleGroupItem>
            <ToggleGroupItem value="injury" className="flex-1">Yaralanmalı</ToggleGroupItem>
            <ToggleGroupItem value="no_injury" className="flex-1">Yaralanmasız</ToggleGroupItem>
          </ToggleGroup>
        </Group>

        <Group label="Ölümle sonuçlanan kaza">
          <ToggleGroup type="single" variant="outline" size="sm" value={draft.fatal} onValueChange={(v) => v && set({ fatal: v as FilterState["fatal"] })} aria-label="Ölümlü kaza filtresi" className="w-full">
            <ToggleGroupItem value="any" className="flex-1">Tümü</ToggleGroupItem>
            <ToggleGroupItem value="fatal" className="flex-1" data-testid="f-fatal-only">Yalnızca ölümlü</ToggleGroupItem>
            <ToggleGroupItem value="non_fatal" className="flex-1">Ölümsüz</ToggleGroupItem>
          </ToggleGroup>
        </Group>

        <div className="flex items-start gap-2.5">
          <Checkbox id="f-midnight" checked={draft.excludeMidnight} onCheckedChange={(c) => set({ excludeMidnight: c === true })} className="mt-0.5" />
          <div className="space-y-0.5">
            <Label htmlFor="f-midnight" className="text-[12.5px] font-semibold">00:00 şüpheli kayıtları hariç tut</Label>
            <p className="text-[11.5px] text-subtle leading-snug">
              Saati tam 00:00 olan {o ? fmtInt(o.midnight_suspect) : "…"} uygun kayıt; bir kısmı saati bilinmeyen kayıtların gece yarısına
              yuvarlanmış hâli olabilir (Faz 2 bayrağı).
            </p>
          </div>
        </div>
      </div>

      <div className="shrink-0 border-t border-line pt-3 mt-3 space-y-2.5">
        {errors.length > 0 && <p role="alert" className="text-[12px] text-hotspot">{errors.join(" ")}</p>}
        <div className="flex items-baseline justify-between gap-2 text-[12.5px]" aria-live="polite" data-testid="filter-preview">
          <span className="text-muted-foreground">Bu filtreyle</span>
          <span className="font-display font-bold tabular text-[15px]">
            {preview.data ? fmtInt(preview.data.n_events) : "…"} <span className="text-[12px] font-semibold text-muted-foreground">kayıt</span>
            {preview.data && preview.data.share_of_total !== null && (
              <span className="ml-1 text-[11.5px] font-medium text-subtle">({fmtPct(preview.data.share_of_total)})</span>
            )}
          </span>
        </div>
        {preview.status === "error" && <p role="alert" className="text-[12px] text-hotspot">{preview.error.message}</p>}
        <div className="grid grid-cols-[1fr_auto] gap-2">
          <Button onClick={applyDraft} disabled={errors.length > 0 || !dirty} data-testid="filter-apply">
            <Layers /> Mevcut kümelerde göster
          </Button>
          <Button variant="outline" size="icon" onClick={reset} aria-label="Filtreleri sıfırla" title="Filtreleri sıfırla" disabled={isEmpty(draft) && isEmpty(applied)} data-testid="filter-reset">
            <RotateCcw />
          </Button>
        </div>
        <Button variant="secondary" className="w-full" onClick={() => { applyDraft(); onStartLab(); }} disabled={errors.length > 0} data-testid="filter-to-lab">
          <FlaskConical /> Bu filtreyle yeni kümeleme başlat…
        </Button>
        <p className="text-[11px] text-subtle leading-snug">
          "Mevcut kümelerde göster" yeniden kümeleme yapmaz: kayıtlar tam veri modelinin kümeleriyle gösterilir. Yeni kümeleme
          Laboratuvar'da ayrı bir iş olarak başlatılır.
        </p>
      </div>
    </div>
  );
}
