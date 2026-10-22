// Zaman oynatma: gerçek kayıtların tarih/saat alanlarına göre (sunucu tarafı kovalar). Her adım, uygulanan
// filtrelerin üzerine bir zaman dilimi ekler; harita yoğunluğu, küme merkezleri ve noktalar sunucudan yeniden
// filtrelenir. Temsili araç animasyonu bu oynatmayla ilişkili değildir.
// Sonuç modunda (kayıtlı Faz 3 deneyi / dinamik iş) kovalar YALNIZCA o sonucun olaylarından sayılır: oynatma
// deneyin kapsamını aşamaz, küme üyeliği sabit kalır ve yeniden kümeleme yapılmaz.
import { ChevronLeft, ChevronRight, Pause, Play, X } from "lucide-react";
import { useEffect, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { cn } from "@/lib/utils";
import { useApp } from "../../app/store";
import { InfoTip } from "../../components/common";
import { DOWS_SHORT, sliceLabel, toQuery, type Granularity } from "../../lib/filters";
import { fmtInt } from "../../lib/format";
import { useQuery } from "../../lib/query";
import type { Timeline } from "../../lib/types";

const G_LABEL: Record<Granularity, string> = { year: "Yıl", month: "Ay", dow: "Gün", hour: "Saat" };

function bucketLabel(g: Granularity, key: string) {
  if (g === "dow") return DOWS_SHORT[Number(key)];
  if (g === "hour") return `${key}:00`;
  return key;
}

type ResultTimeline = Timeline & { coverage: { n_events: number; date_min: string | null; date_max: string | null }; reclustered: boolean };

export function TimeControls({ disabledReason, compact, resultId }: { disabledReason: string | null; compact?: boolean; resultId?: string | null }) {
  const applied = useApp((s) => s.applied);
  const g = useApp((s) => s.granularity);
  const setG = useApp((s) => s.setGranularity);
  const slice = useApp((s) => s.slice);
  const setSlice = useApp((s) => s.setSlice);
  const playing = useApp((s) => s.playing);
  const setPlaying = useApp((s) => s.setPlaying);
  const motion = useApp((s) => s.motion);
  const q = toQuery(applied);
  const tl = useQuery<Timeline & Partial<ResultTimeline>>(disabledReason ? null : resultId
    ? `/api/results/${encodeURIComponent(resultId)}/timeline?granularity=${g}`
    : `/api/records/timeline?granularity=${g}${q ? `&${q}` : ""}`);
  const coverage = resultId ? tl.data?.coverage : undefined;
  const buckets = useMemo(() => tl.data?.buckets ?? [], [tl.data]);
  const idx = slice && slice.granularity === g ? buckets.findIndex((b) => b.key === slice.key) : -1;
  const max = Math.max(1, ...buckets.map((b) => b.count));

  const go = (i: number) => {
    if (!buckets.length) return;
    const j = ((i % buckets.length) + buckets.length) % buckets.length;
    setSlice({ granularity: g, key: buckets[j].key });
  };

  useEffect(() => {
    if (!playing || !buckets.length) return;
    const ms = motion === "full" ? 1600 : 2600;
    const t = window.setInterval(() => {
      const s = useApp.getState().slice;
      const cur = s && s.granularity === g ? buckets.findIndex((b) => b.key === s.key) : -1;
      const next = cur + 1;
      if (next >= buckets.length) {
        setPlaying(false);
        return;
      }
      setSlice({ granularity: g, key: buckets[next].key });
    }, ms);
    return () => window.clearInterval(t);
  }, [playing, buckets, g, motion, setPlaying, setSlice]);

  if (disabledReason) {
    return (
      <div className="panel px-3 py-2 text-[12px] text-muted-foreground" data-testid="time-controls" data-state="disabled">
        <span className="font-semibold text-foreground mr-1.5">Zaman oynatma kapalı.</span>{disabledReason}
      </div>
    );
  }

  const current = idx >= 0 ? buckets[idx] : null;
  return (
    <div className={cn("panel px-3 py-2.5", compact ? "space-y-2" : "space-y-2")} data-testid="time-controls" data-state={slice ? "slice" : "all"}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="eyebrow">Zaman</span>
        <ToggleGroup type="single" size="sm" variant="outline" value={g} onValueChange={(v) => v && setG(v as Granularity)} aria-label="Zaman ölçeği">
          {(["year", "month", "dow", "hour"] as Granularity[]).map((k) => (
            <ToggleGroupItem key={k} value={k} className="px-2.5 text-[12px]" data-testid={`time-g-${k}`}>{G_LABEL[k]}</ToggleGroupItem>
          ))}
        </ToggleGroup>
        <div className="flex items-center gap-1">
          <Button size="icon-sm" variant="outline" aria-label="Önceki adım" onClick={() => go(idx < 0 ? buckets.length - 1 : idx - 1)} disabled={!buckets.length}><ChevronLeft /></Button>
          <Button size="sm" variant={playing ? "secondary" : "default"} onClick={() => { if (!playing && idx < 0) go(0); setPlaying(!playing); }}
            disabled={!buckets.length} aria-label={playing ? "Oynatmayı duraklat" : "Zaman içinde oynat"} data-testid="time-play">
            {playing ? <Pause /> : <Play />} {playing ? "Duraklat" : "Oynat"}
          </Button>
          <Button size="icon-sm" variant="outline" aria-label="Sonraki adım" onClick={() => go(idx + 1)} disabled={!buckets.length}><ChevronRight /></Button>
          {slice && (
            <Button size="icon-sm" variant="ghost" aria-label="Zaman dilimini kaldır (tüm dönem)" onClick={() => { setPlaying(false); setSlice(null); }} data-testid="time-clear"><X /></Button>
          )}
        </div>
        <div className="ml-auto flex items-center gap-1.5 text-[12.5px] tabular" aria-live="polite" data-testid="time-readout">
          {current && slice ? (
            <><span className="font-display font-bold text-[14px]">{sliceLabel(slice)}</span><span className="text-muted-foreground">· {fmtInt(current.count)} {resultId ? "görünür olay" : "kayıt"}</span></>
          ) : (
            <span className="text-muted-foreground">Tüm dönem{tl.data ? ` · ${fmtInt(tl.data.n_events)} ${resultId ? "görünür olay" : "kayıt"}` : ""}</span>
          )}
          <InfoTip>
            Oynatma, gerçek kaza kayıtlarının tarih ve saat alanlarını kullanır; her adımda haritadaki yoğunluk, küme merkezleri
            ve noktalar sunucuda yeniden filtrelenir (küme etiketleri değişmez). Temsili araç animasyonları gerçek kaza verisi değildir.
            {resultId && " Bu görünümde kovalar yalnızca seçili deneyin kapsadığı olaylardan sayılır; oynatma deneyin veri aralığını aşmaz."}
            {g === "hour" && " 00:00 kovası, saati bilinmeyen kayıtların gece yarısına yuvarlanmasıyla şişmiş olabilir."}
          </InfoTip>
        </div>
      </div>
      {resultId && coverage && (
        <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[11.5px] text-muted-foreground tabular" data-testid="time-coverage">
          <span>Deney kapsamı: <b className="text-foreground font-semibold">{coverage.date_min} → {coverage.date_max}</b> · {fmtInt(coverage.n_events)} olay</span>
          <span data-testid="time-recluster">Kümeleme yeniden çalıştırıldı mı? <b className="text-foreground font-semibold">Hayır</b> — üyelik sabit, yalnızca görünen olaylar süzülür</span>
        </div>
      )}
      {!compact && (
        <div className="relative">
          <div className="flex h-8 items-end gap-px" aria-hidden>
            {buckets.map((b, i) => (
              <button key={b.key} type="button" tabIndex={-1} onClick={() => { setPlaying(false); go(i); }}
                title={`${bucketLabel(g, b.key)} — ${fmtInt(b.count)} kayıt`}
                className={cn("flex-1 min-w-[2px] rounded-[1px] transition-colors", i === idx ? "bg-hotspot" : "bg-primary/45 hover:bg-primary/80",
                  g === "hour" && b.key === "00" && i !== idx && "bg-warning/60")}
                style={{ height: `${Math.max(4, (b.count / max) * 100)}%` }} />
            ))}
          </div>
          <input type="range" min={0} max={Math.max(0, buckets.length - 1)} step={1} value={Math.max(0, idx)}
            onChange={(e) => { setPlaying(false); go(Number(e.target.value)); }} disabled={!buckets.length}
            aria-label="Zaman dilimi" aria-valuetext={current && slice ? `${sliceLabel(slice)}, ${fmtInt(current.count)} kayıt` : "Tüm dönem"}
            className="mt-1 w-full accent-[#38BDF8] h-4" data-testid="time-range" />
          <div className="flex justify-between text-[10.5px] text-subtle tabular" aria-hidden>
            <span>{buckets[0] ? bucketLabel(g, buckets[0].key) : ""}</span>
            <span>{buckets.at(-1) ? bucketLabel(g, buckets.at(-1)!.key) : ""}</span>
          </div>
        </div>
      )}
      {tl.status === "error" && (
        <p role="alert" className="text-[12px] text-hotspot">
          {resultId ? `Bu sonuç için olay–zaman eşleşmesi alınamadı; oynatma devre dışı (${tl.error.message}).` : tl.error.message}
        </p>
      )}
    </div>
  );
}
