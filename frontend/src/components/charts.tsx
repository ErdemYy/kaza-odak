// Karşılaştırma grafikleri (Recharts). İlkeler: tek seri = tek ton (birincil); farklı ölçekli metrikler çift
// eksen yerine ayrı küçük grafiklerde; ızgara ve eksenler geri planda; her çubukta üzerine gelince ipucu;
// payda/kapsam başlıkta yazılır; durum renkleri (uyarı) yalnızca etiketli durumlar için.
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ReactNode } from "react";
import { fmtInt, fmtNum } from "../lib/format";

const AXIS = { stroke: "#2E4166", tick: { fill: "#94A3B8", fontSize: 11.5, fontFamily: "Manrope" } };
export const CHART = { primary: "#38BDF8", muted: "#38BDF866", warning: "#F59E0B", hotspot: "#F87171", grid: "#22314D", surface: "#111C30" };

function TipBox({ title, rows }: { title: ReactNode; rows: { k: string; v: ReactNode }[] }) {
  return (
    <div className="rounded-md border border-line bg-popover px-2.5 py-2 text-[12px] shadow-lg">
      <div className="font-semibold mb-1">{title}</div>
      {rows.map((r) => (
        <div key={r.k} className="flex justify-between gap-4 tabular"><span className="text-muted-foreground">{r.k}</span><span>{r.v}</span></div>
      ))}
    </div>
  );
}

export interface BarDatum { label: string; value: number; flag?: string | null; highlight?: boolean }

/** Tek serili dikey çubuk grafik. ``flag`` taşıyan çubuklar (ör. kısmi yıl) soluk çizilir ve ipucunda açıklanır. */
export function ColumnChart({ data, height = 220, valueLabel, format = (v) => fmtInt(v), ariaLabel, testId }: {
  data: BarDatum[]; height?: number; valueLabel: string; format?: (v: number) => string; ariaLabel: string; testId?: string;
}) {
  return (
    <figure data-testid={testId} aria-label={ariaLabel} role="img" className="w-full" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 4, bottom: 0, left: 0 }} barCategoryGap={2}>
          <CartesianGrid vertical={false} stroke={CHART.grid} strokeDasharray="0" />
          <XAxis dataKey="label" {...AXIS} tickLine={false} interval="preserveStartEnd" minTickGap={8} />
          <YAxis {...AXIS} tickLine={false} axisLine={false} width={52} tickFormatter={(v) => fmtInt(v)} />
          <Tooltip cursor={{ fill: "#ffffff0d" }} content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const d = payload[0].payload as BarDatum;
            return <TipBox title={d.label} rows={[{ k: valueLabel, v: format(d.value) }, ...(d.flag ? [{ k: "Not", v: d.flag }] : [])]} />;
          }} />
          <Bar dataKey="value" radius={[4, 4, 0, 0]} isAnimationActive={false}>
            {data.map((d) => <Cell key={d.label} fill={d.highlight ? CHART.hotspot : d.flag ? CHART.muted : CHART.primary} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </figure>
  );
}

/** Yatay çubuklar (kategoriler uzun adlıysa). */
export function RowChart({ data, valueLabel, format = (v) => fmtInt(v), ariaLabel, max }: {
  data: BarDatum[]; valueLabel: string; format?: (v: number) => string; ariaLabel: string; max?: number;
}) {
  const top = max ?? Math.max(1, ...data.map((d) => d.value));
  return (
    <ul className="space-y-2" aria-label={ariaLabel}>
      {data.map((d) => (
        <li key={d.label} className="grid grid-cols-[minmax(0,140px)_1fr_auto] items-center gap-3 text-[12.5px]">
          <span className="truncate" title={d.label}>{d.label}</span>
          <span className="h-2 rounded-sm bg-surface-2" aria-hidden>
            <span className="block h-full rounded-sm" style={{ width: `${(d.value / top) * 100}%`, background: d.highlight ? CHART.hotspot : CHART.primary }} />
          </span>
          <span className="tabular text-right text-muted-foreground min-w-[64px]" title={valueLabel}>{format(d.value)}</span>
        </li>
      ))}
    </ul>
  );
}

/** Tek ölçüt × parametre çizgisi (ör. K-Means k → siluet). İşaretli nokta seçili konfigürasyondur. */
export function SweepChart({ data, xLabel, yLabel, format = (v) => fmtNum(v, 3), selectedX, ariaLabel, height = 180, refY }: {
  data: { x: number; y: number | null }[]; xLabel: string; yLabel: string; format?: (v: number) => string; selectedX?: number;
  ariaLabel: string; height?: number; refY?: { y: number; label: string };
}) {
  return (
    <figure aria-label={ariaLabel} role="img" className="w-full" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 10, right: 12, bottom: 4, left: 0 }}>
          <CartesianGrid stroke={CHART.grid} vertical={false} />
          <XAxis dataKey="x" {...AXIS} tickLine={false} type="number" domain={["dataMin", "dataMax"]} ticks={data.map((d) => d.x)}
            scale="log" allowDataOverflow padding={{ left: 12, right: 12 }} />
          <YAxis {...AXIS} tickLine={false} axisLine={false} width={48} tickFormatter={(v) => format(v)} />
          {refY && <ReferenceLine y={refY.y} stroke={CHART.warning} strokeDasharray="4 3" label={{ value: refY.label, fill: "#94A3B8", fontSize: 11, position: "insideTopRight" }} />}
          <Tooltip content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const d = payload[0].payload as { x: number; y: number | null };
            return <TipBox title={`${xLabel} = ${d.x}`} rows={[{ k: yLabel, v: d.y === null ? "tanımsız" : format(d.y) }]} />;
          }} />
          <Line dataKey="y" stroke={CHART.primary} strokeWidth={2} isAnimationActive={false} connectNulls={false}
            dot={(p: { cx?: number; cy?: number; payload?: { x: number } }) => (
              <circle key={`${p.cx}-${p.cy}`} cx={p.cx} cy={p.cy} r={p.payload?.x === selectedX ? 6 : 4}
                fill={p.payload?.x === selectedX ? CHART.hotspot : CHART.primary} stroke={CHART.surface} strokeWidth={2} />
            )} />
        </LineChart>
      </ResponsiveContainer>
    </figure>
  );
}
