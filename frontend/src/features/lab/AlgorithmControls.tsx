// Algoritma, öznitelik seti, parametreler ve kapsam. Desteklenmeyen kombinasyonlar seçilemez ve gerekçesi gösterilir.
import { Filter, Play } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { cn } from "@/lib/utils";
import { InfoTip, Note } from "../../components/common";
import { fmtInt, fmtPct } from "../../lib/format";
import type { Experiment, LabCapabilities, RecordsSummary } from "../../lib/types";
import { budgetWarnings, DEFAULT_PARAMS, defaultForm, PARAM_LABELS, paramKeys, registryMatch, type Algorithm, type LabForm, type Validation } from "./labForm";

const ALGOS: { id: Algorithm; label: string; note: string }[] = [
  { id: "dbscan", label: "DBSCAN", note: "Yoğunluk tabanlı; gürültüyü ayırır. Ana model." },
  { id: "kmeans", label: "K-Means", note: "Merkez tabanlı; her olayı bir kümeye atar." },
  { id: "hdbscan", label: "HDBSCAN", note: "Değişken yoğunluk; ağırlık desteklemez." },
];

export function AlgorithmControls({ form, setForm, cap, validation, scope, filtersTr, filtersEmpty, experiments, onEditFilters, onSubmit, submitting, submitError }: {
  form: LabForm; setForm: (f: LabForm) => void; cap: LabCapabilities; validation: Validation; scope: RecordsSummary | undefined;
  filtersTr: string[]; filtersEmpty: boolean; experiments: Experiment[]; onEditFilters: () => void; onSubmit: () => void;
  submitting: boolean; submitError: string | null;
}) {
  const fs = cap.feature_sets[form.featureSet];
  const allowed = cap.compatibility[form.algorithm].allowed;
  const warnings = budgetWarnings(form, scope?.n_events ?? null, cap.budget);
  const blocked = warnings.some((w) => w.level === "block");
  const invalid = Object.keys(validation.errors).length > 0 || !!validation.compatibilityError;
  const match = registryMatch(form, validation, filtersEmpty, experiments);
  const setAlgo = (a: Algorithm) => {
    const fsNext = cap.compatibility[a].allowed.includes(form.featureSet) ? form.featureSet : cap.compatibility[a].allowed[0];
    // HDBSCAN örneklemi zorunlu açar; HDBSCAN'den çıkınca bu zorlama geri alınır (aksi hâlde DBSCAN/K-Means istekleri
    // fark edilmeden 100.000 olaylık örneklemle gider ve Faz 3 kaydıyla eşleşmez).
    const leavingHdb = form.algorithm === "hdbscan" && a !== "hdbscan";
    setForm({ ...form, algorithm: a, featureSet: fsNext, params: { ...DEFAULT_PARAMS[a] },
      useSample: a === "hdbscan" ? true : leavingHdb ? false : form.useSample,
      sampleN: a === "hdbscan" ? "100000" : leavingHdb ? defaultForm().sampleN : form.sampleN });
  };
  const setParam = (k: string, v: string) => setForm({ ...form, params: { ...form.params, [k]: v } });

  return (
    <form className="space-y-5" onSubmit={(e) => { e.preventDefault(); if (!invalid && !blocked) onSubmit(); }} noValidate data-testid="algorithm-controls">
      <fieldset className="space-y-2">
        <legend className="text-[13px] font-semibold mb-2">Algoritma</legend>
        <ToggleGroup type="single" variant="outline" value={form.algorithm} onValueChange={(v) => v && setAlgo(v as Algorithm)} className="w-full" aria-label="Algoritma">
          {ALGOS.map((a) => <ToggleGroupItem key={a.id} value={a.id} className="flex-1 font-semibold" data-testid={`lab-algo-${a.id}`}>{a.label}</ToggleGroupItem>)}
        </ToggleGroup>
        <p className="text-[12px] text-muted-foreground">{ALGOS.find((a) => a.id === form.algorithm)!.note}</p>
      </fieldset>

      <fieldset className="space-y-2" aria-describedby="fs-help">
        <legend className="text-[13px] font-semibold mb-1">Öznitelik seti</legend>
        <p id="fs-help" className="text-[11.5px] text-subtle">Mekânsal setler "nerede tekrar ediyor?", uzay-zamansal set "aynı yerde ve aynı dönemde mi?" sorusunu yanıtlar.</p>
        <div role="radiogroup" aria-label="Öznitelik seti" className="space-y-1.5">
          {Object.entries(cap.feature_sets).map(([id, f]) => {
            const ok = allowed.includes(id);
            const reason = cap.compatibility[form.algorithm].reasons[id];
            return (
              <label key={id} className={cn("flex gap-2.5 rounded-md border p-2.5 text-[12.5px]",
                form.featureSet === id ? "border-primary bg-primary/[0.07]" : "border-line", ok ? "cursor-pointer hover:border-line-strong" : "opacity-60 cursor-not-allowed")}
                data-testid={`lab-fs-${id}`} data-disabled={!ok}>
                <input type="radio" name="feature-set" value={id} checked={form.featureSet === id} disabled={!ok}
                  onChange={() => setForm({ ...form, featureSet: id })} className="mt-0.5 accent-[#38BDF8]" />
                <span className="min-w-0">
                  <span className="flex flex-wrap items-center gap-1.5 font-semibold">
                    {f.label}
                    <Badge variant="outline" className={f.kind === "spatiotemporal" ? "border-warning/60 text-warning" : "border-line-strong text-muted-foreground"}>
                      {f.kind === "spatiotemporal" ? "Uzay-zaman · deneysel" : "Mekânsal"}
                    </Badge>
                  </span>
                  {ok && <span className="block text-muted-foreground mt-0.5">{f.metric} · {f.level}</span>}
                  {!ok && reason && (
                    <span className="mt-0.5 flex items-start gap-1 text-warning" data-testid={`lab-fs-reason-${id}`}>
                      <span>Desteklenmiyor: {reason}</span>
                    </span>
                  )}
                </span>
              </label>
            );
          })}
        </div>
        {validation.compatibilityError && <p role="alert" className="text-[12px] text-hotspot">{validation.compatibilityError}</p>}
      </fieldset>

      <fieldset className="space-y-3">
        <legend className="text-[13px] font-semibold mb-1">Parametreler</legend>
        <div className="grid grid-cols-2 gap-3">
          {paramKeys(form).map((k) => {
            const meta = PARAM_LABELS[k];
            const [lo, hi] = cap.bounds[form.algorithm][k] ?? [0, 0];
            const auto = form.algorithm === "hdbscan" && k === "min_samples" && form.hdbAutoMinSamples;
            const err = validation.errors[k];
            return (
              <div key={k} className="space-y-1">
                <div className="flex items-center gap-1">
                  <Label htmlFor={`p-${k}`} className="text-[12px] font-mono">{meta?.label ?? k}{meta?.unit ? ` (${meta.unit})` : ""}</Label>
                  {meta && <InfoTip>{meta.help} Aralık: {lo}–{hi}.</InfoTip>}
                </div>
                <Input id={`p-${k}`} inputMode="decimal" value={auto ? "" : form.params[k] ?? ""} disabled={auto} placeholder={auto ? "= min_cluster_size" : undefined}
                  onChange={(e) => setParam(k, e.target.value)} aria-invalid={!!err} aria-describedby={err ? `p-${k}-err` : undefined}
                  className="h-9 tabular" data-testid={`lab-param-${k}`} />
                {err && <p id={`p-${k}-err`} className="text-[11.5px] text-hotspot" role="alert">{err}</p>}
              </div>
            );
          })}
        </div>
        {form.algorithm === "hdbscan" && (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Checkbox id="hdb-auto" checked={form.hdbAutoMinSamples} onCheckedChange={(c) => setForm({ ...form, hdbAutoMinSamples: c === true })} />
              <Label htmlFor="hdb-auto" className="text-[12.5px]">min_samples = min_cluster_size (scikit-learn varsayılanı)</Label>
            </div>
            <div className="flex items-center gap-2 text-[12.5px]">
              <span>Küme seçimi:</span>
              <ToggleGroup type="single" size="sm" variant="outline" value={form.params.cluster_selection_method ?? "eom"} onValueChange={(v) => v && setParam("cluster_selection_method", v)} aria-label="Küme seçim yöntemi">
                <ToggleGroupItem value="eom" className="px-2.5">eom</ToggleGroupItem>
                <ToggleGroupItem value="leaf" className="px-2.5">leaf</ToggleGroupItem>
              </ToggleGroup>
            </div>
          </div>
        )}
      </fieldset>

      <fieldset className="space-y-2.5">
        <legend className="text-[13px] font-semibold mb-1">Veri kapsamı</legend>
        <div className="rounded-md border border-line bg-surface-2/50 p-3 space-y-2" data-testid="lab-scope">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-[12px] text-muted-foreground">Kapsamdaki kayıt</span>
            <span className="font-display font-bold tabular text-[16px]" data-testid="lab-scope-count">{scope ? fmtInt(scope.n_events) : "…"}</span>
          </div>
          {scope && <div className="text-[11.5px] text-subtle">{fmtPct(scope.share_of_total)} · payda: {scope.denominator}</div>}
          <ul className="flex flex-wrap gap-1">
            {(filtersTr.length ? filtersTr : ["Filtre yok — tüm uygun kayıtlar"]).map((t) => (
              <li key={t}><Badge variant="outline" className="border-line-strong text-muted-foreground font-medium whitespace-normal">{t}</Badge></li>
            ))}
          </ul>
          <Button type="button" variant="outline" size="sm" onClick={onEditFilters}><Filter /> Filtreleri düzenle (3D Keşif)</Button>
        </div>
        <div className="flex items-center gap-2">
          <Checkbox id="use-sample" checked={form.useSample} onCheckedChange={(c) => setForm({ ...form, useSample: c === true })} />
          <Label htmlFor="use-sample" className="text-[12.5px]">Basit rastgele olay örneklemi kullan</Label>
          <InfoTip>Kapsamdaki olaylardan yerine koymadan, sabit tohumla örneklem. Faz 3'teki HDBSCAN örneklemiyle aynı yöntem.</InfoTip>
        </div>
        {form.useSample && (
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="s-n" className="text-[12px]">Örneklem boyutu</Label>
              <Input id="s-n" inputMode="numeric" value={form.sampleN} onChange={(e) => setForm({ ...form, sampleN: e.target.value })} className="h-9 tabular" aria-invalid={!!validation.errors.sampleN} data-testid="lab-sample-n" />
              {validation.errors.sampleN && <p className="text-[11.5px] text-hotspot" role="alert">{validation.errors.sampleN}</p>}
            </div>
            <div className="space-y-1">
              <Label htmlFor="s-seed" className="text-[12px]">Tohum</Label>
              <Input id="s-seed" inputMode="numeric" value={form.sampleSeed} onChange={(e) => setForm({ ...form, sampleSeed: e.target.value })} className="h-9 tabular" aria-invalid={!!validation.errors.sampleSeed} />
              {validation.errors.sampleSeed && <p className="text-[11.5px] text-hotspot" role="alert">{validation.errors.sampleSeed}</p>}
            </div>
          </div>
        )}
      </fieldset>

      <div className="rounded-md border border-line p-3 text-[12px] space-y-1" data-testid="lab-info">
        <div><span className="text-muted-foreground">Öznitelikler: </span><span className="font-mono">{fs.features.join(", ")}</span> <span className="text-subtle">({fs.phase2_set})</span></div>
        <div><span className="text-muted-foreground">Mesafe metriği: </span>{fs.metric}</div>
        <div><span className="text-muted-foreground">Fit düzeyi: </span>{fs.level}</div>
        <div><span className="text-muted-foreground">Algoritma sürümü: </span>scikit-learn {cap.software["scikit-learn"] ?? "—"} · {cap.code_version}</div>
        <div><span className="text-muted-foreground">Deney kimliği: </span>iş gönderilince atanır (istek + veri sürümü + kod sürümü özeti)</div>
        <p className="text-subtle pt-1">{fs.note}</p>
      </div>

      {match && (
        <Note title="Kayıtlı konfigürasyon" testId="lab-registry-hint">
          Bu istek Faz 3'teki <code>{match.experiment_id}</code> deneyiyle aynı. Doğrulanmış kayıtlı sonuç yüklenecek; yeniden fit yapılmaz.
        </Note>
      )}
      {warnings.map((w) => <Note key={w.text} tone="warning" title={w.level === "block" ? "Kaynak bütçesi aşılıyor" : undefined} testId={w.level === "block" ? "lab-budget-block" : undefined}>{w.text}</Note>)}
      {submitError && <p role="alert" className="text-[12.5px] text-hotspot" data-testid="lab-submit-error">{submitError}</p>}
      <Button type="submit" className="w-full" disabled={invalid || blocked || submitting || !scope} data-testid="lab-submit">
        <Play /> {match ? "Kayıtlı sonucu yükle" : "Analizi başlat"}
      </Button>
      <p className="text-[11.5px] text-subtle leading-snug">
        Hesaplama sunucuda ayrı bir süreçte yapılır; arayüz donmaz. Aynı istek daha önce tamamlandıysa önbellekten gelir.
      </p>
    </form>
  );
}
