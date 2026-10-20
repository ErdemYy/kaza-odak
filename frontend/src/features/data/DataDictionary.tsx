// Öznitelik sözlüğü: her sütun için "Ne anlama geliyor? Modele giriyor mu? Hangi dönüşüm? Neden seçildi/elendi?"
// Kaynak: Faz 2 FeatureSpec kayıtları (preprocess/features.py) + Parquet istatistikleri (eksik sayısı).
import { Search } from "lucide-react";
import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { EmptyBlock } from "../../components/common";
import { fmtInt, fmtPct } from "../../lib/format";
import type { DataDictionary, DictColumnSpec } from "../../lib/types";

export interface DictRow {
  name: string; type: string; missing: number | null; rows: number; group: string; origin: string; inModel: boolean;
  featureSets: string[]; spec: DictColumnSpec | null; extra?: string;
}

export function toRows(d: DataDictionary, which: "raw" | "processed"): DictRow[] {
  if (which === "raw") {
    return d.raw.columns.map((c) => ({
      name: c.name, type: c.source_type, missing: c.missing_count, rows: d.raw.rows, group: c.group, origin: "raw",
      inModel: !!c.spec && c.spec.models !== "—", featureSets: [], spec: c.spec,
      extra: c.processed_as ? (c.processed_as !== c.name ? `İşlenmiş tabloda: ${c.processed_as}` : "İşlenmiş tabloda aynı adla") : "İşlenmiş tabloya taşınmadı",
    }));
  }
  return d.processed.columns.map((c) => ({
    name: c.name, type: c.dtype.replace(/^dictionary<values=string.*$/, "kategorik (sözlük)").replace("large_string", "metin"),
    missing: c.missing_count, rows: c.rows, group: c.group, origin: c.origin, inModel: c.in_model || (!!c.spec && c.spec.models !== "—"),
    featureSets: c.in_feature_sets, spec: c.spec,
  }));
}

function ModelBadge({ r }: { r: DictRow }) {
  if (r.featureSets.length) return <Badge variant="outline" className="border-primary/50 text-primary">{r.featureSets.map((s) => s.split("_")[0]).filter((v, i, a) => a.indexOf(v) === i).join(", ")}</Badge>;
  if (r.inModel) return <Badge variant="outline" className="border-primary/50 text-primary">Dönüştürülerek</Badge>;
  return <span className="text-subtle text-[12px]">Hayır</span>;
}

export function DataDictionaryTable({ rows, label, testId }: { rows: DictRow[]; label: string; testId: string }) {
  const [q, setQ] = useState("");
  const [group, setGroup] = useState("all");
  const [modelOnly, setModelOnly] = useState("all");
  const [open, setOpen] = useState<DictRow | null>(null);
  const groups = useMemo(() => [...new Set(rows.map((r) => r.group))].sort(), [rows]);
  const filtered = rows.filter((r) => (group === "all" || r.group === group)
    && (modelOnly === "all" || (modelOnly === "model" ? r.inModel : !r.inModel))
    && (!q || `${r.name} ${r.spec?.meaning ?? ""}`.toLocaleLowerCase("tr").includes(q.toLocaleLowerCase("tr"))));
  return (
    <div data-testid={testId}>
      <div className="flex flex-wrap items-end gap-2 mb-3">
        <div className="relative min-w-[220px] flex-1">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-4 text-subtle" aria-hidden />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Sütun adı veya anlam ara…" className="pl-8 h-9" aria-label={`${label} içinde ara`} />
        </div>
        <Select value={group} onValueChange={setGroup}>
          <SelectTrigger className="h-9 w-[190px]" aria-label="Grup"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tüm gruplar</SelectItem>
            {groups.map((g) => <SelectItem key={g} value={g}>{g}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={modelOnly} onValueChange={setModelOnly}>
          <SelectTrigger className="h-9 w-[170px]" aria-label="Modele giriş"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tümü</SelectItem>
            <SelectItem value="model">Modele girenler</SelectItem>
            <SelectItem value="nomodel">Modele girmeyenler</SelectItem>
          </SelectContent>
        </Select>
        <span className="text-[12px] text-muted-foreground tabular ml-auto" aria-live="polite">{filtered.length} / {rows.length} sütun</span>
      </div>
      {filtered.length === 0 ? <EmptyBlock>Aramayla eşleşen sütun yok.</EmptyBlock> : (
        <div className="overflow-x-auto -mx-1 px-1">
          <Table className="text-[12.5px] min-w-[860px]">
            <TableHeader>
              <TableRow>
                <TableHead>Sütun</TableHead><TableHead>Tür</TableHead><TableHead className="text-right">Eksik</TableHead>
                <TableHead>Anlam</TableHead><TableHead>Modele giriyor mu?</TableHead><TableHead>Grup</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((r) => (
                <TableRow key={r.name} className="cursor-pointer" onClick={() => setOpen(r)}>
                  <TableCell>
                    <button type="button" className="font-mono text-[12px] text-primary hover:underline text-left focus-visible:ring-2 focus-visible:ring-ring rounded-sm outline-none"
                      onClick={(e) => { e.stopPropagation(); setOpen(r); }} data-column={r.name}>{r.name}</button>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{r.type}</TableCell>
                  <TableCell className={cn("text-right tabular", r.missing && r.missing / r.rows > 0.2 ? "text-warning" : "")}>
                    {r.missing === null ? "—" : <>{fmtInt(r.missing)} <span className="text-subtle">({fmtPct(r.missing / r.rows)})</span></>}
                  </TableCell>
                  <TableCell className="max-w-[320px] whitespace-normal">{r.spec?.meaning ?? "—"}</TableCell>
                  <TableCell><ModelBadge r={r} /></TableCell>
                  <TableCell className="text-muted-foreground">{r.group}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      <Sheet open={!!open} onOpenChange={(o) => !o && setOpen(null)}>
        <SheetContent side="right" className="w-full sm:max-w-[520px] bg-surface border-line overflow-y-auto" data-testid="feature-sheet">
          {open && (
            <>
              <SheetHeader>
                <SheetTitle className="font-mono text-[17px]">{open.name}</SheetTitle>
                <SheetDescription>{open.group} · {open.type} · {open.origin === "raw" ? "kaynak sütunu" : "türetilmiş (Faz 2)"}</SheetDescription>
              </SheetHeader>
              <dl className="px-4 pb-6 space-y-4 text-[13.5px]">
                <QA q="Ne anlama geliyor?" a={open.spec?.meaning} />
                <QA q="Modele giriyor mu?" a={open.featureSets.length ? `Evet — öznitelik setleri: ${open.featureSets.join(", ")}` : open.spec?.models && open.spec.models !== "—" ? `Dönüştürülmüş biçimiyle: ${open.spec.models}` : "Hayır"} />
                <QA q="Hangi dönüşüm uygulandı?" a={open.spec?.transform} />
                <QA q="Neden seçildi veya elendi?" a={open.spec ? (open.spec.exclusion_reason && open.spec.exclusion_reason !== "—" ? open.spec.exclusion_reason : "Modelde kullanılır (bkz. öznitelik seti tanımı).") : undefined} />
                <QA q="Filtrede kullanımı" a={open.spec?.filter_use} />
                <QA q="Yorumda kullanımı" a={open.spec?.interpretation_use} />
                <QA q="Eksik değer" a={open.missing === null ? "Parquet istatistiği yok" : `${fmtInt(open.missing)} / ${fmtInt(open.rows)} (${fmtPct(open.missing / open.rows, 2)})`} />
                {open.extra && <QA q="İşlenmiş tabloda" a={open.extra} />}
                {open.spec?.source && <p className="text-[11.5px] text-subtle">{open.spec.source}</p>}
              </dl>
            </>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}

function QA({ q, a }: { q: string; a: string | undefined | null }) {
  return (
    <div>
      <dt className="text-[12px] font-semibold text-muted-foreground">{q}</dt>
      <dd className="mt-0.5 leading-relaxed">{a || <span className="text-subtle">Kaynakta açıklama yok</span>}</dd>
    </div>
  );
}
