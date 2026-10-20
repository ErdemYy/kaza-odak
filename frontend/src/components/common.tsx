// Ortak sunum bileşenleri: metrik, bilgi simgesi, durum görünümleri, kapsam rozeti, bölüm başlığı.
import { AlertTriangle, CircleAlert, Info, Inbox, RotateCw } from "lucide-react";
import type { ReactNode } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

/** Sayısal gösterge. ``value`` null/undefined → "mevcut değil" (sahte değer gösterilmez). */
export function MetricCard({ label, value, unit, hint, tone, info, testId, size = "md", className }: {
  label: string; value: ReactNode | null | undefined; unit?: string; hint?: ReactNode; tone?: "primary" | "warning" | "hotspot";
  info?: ReactNode; testId?: string; size?: "md" | "lg"; className?: string;
}) {
  const color = tone === "hotspot" ? "text-hotspot" : tone === "warning" ? "text-warning" : tone === "primary" ? "text-primary" : "text-foreground";
  const missing = value === null || value === undefined;
  return (
    <div className={cn("min-w-0", className)} data-testid={testId}>
      <div className="flex items-center gap-1.5 text-[12px] font-medium text-muted-foreground">
        <span className="truncate">{label}</span>
        {info && <InfoTip>{info}</InfoTip>}
      </div>
      <div className={cn("font-display font-bold tabular leading-tight mt-1", size === "lg" ? "text-[30px] sm:text-[34px]" : "text-[20px]", missing ? "text-subtle" : color)}>
        {missing ? <span title="Bu değer kaynakta yok veya bu kapsam için tanımsız">—</span> : value}
        {!missing && unit && <span className="ml-1 text-[13px] font-semibold text-muted-foreground">{unit}</span>}
      </div>
      {hint && <div className="text-[12px] text-subtle mt-1 leading-snug">{hint}</div>}
    </div>
  );
}

export function InfoTip({ children, label = "Açıklama" }: { children: ReactNode; label?: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button type="button" aria-label={label}
          className="inline-flex size-5 items-center justify-center rounded-sm text-subtle hover:text-primary focus-visible:text-primary focus-visible:ring-2 focus-visible:ring-ring">
          <Info className="size-3.5" aria-hidden />
        </button>
      </TooltipTrigger>
      <TooltipContent className="max-w-[320px] text-[12px] leading-snug">{children}</TooltipContent>
    </Tooltip>
  );
}

export function LoadingBlock({ label = "Yükleniyor…", lines = 3, className }: { label?: string; lines?: number; className?: string }) {
  return (
    <div className={cn("space-y-2", className)} role="status" aria-live="polite" aria-busy="true">
      {Array.from({ length: lines }, (_, i) => <Skeleton key={i} className={cn("h-4 bg-surface-2", i === 0 && "w-2/3")} />)}
      <span className="sr-only">{label}</span>
    </div>
  );
}

export function ErrorBlock({ title = "Veri alınamadı", error, onRetry, className }: { title?: string; error: Error | string; onRetry?: () => void; className?: string }) {
  return (
    <Alert variant="destructive" className={cn("border-hotspot/50 bg-hotspot/10 text-foreground", className)} role="alert">
      <CircleAlert className="text-hotspot" />
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription className="text-muted-foreground">
        <p>{typeof error === "string" ? error : error.message}</p>
        {onRetry && (
          <Button size="sm" variant="outline" className="mt-2" onClick={onRetry}><RotateCw /> Yeniden dene</Button>
        )}
      </AlertDescription>
    </Alert>
  );
}

export function EmptyBlock({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("flex items-center gap-2.5 rounded-md border border-dashed border-line px-3 py-4 text-[13px] text-muted-foreground", className)}>
      <Inbox className="size-4 shrink-0" aria-hidden /> <div>{children}</div>
    </div>
  );
}

export function Note({ children, tone = "info", title, className, testId }: { children: ReactNode; tone?: "info" | "warning"; title?: string; className?: string; testId?: string }) {
  const Icon = tone === "warning" ? AlertTriangle : Info;
  return (
    <div data-testid={testId} className={cn("flex gap-2.5 rounded-md border px-3 py-2.5 text-[12.5px] leading-snug",
      tone === "warning" ? "border-warning/40 bg-warning/[0.07]" : "border-primary/30 bg-primary/[0.06]", className)}>
      <Icon className={cn("size-4 shrink-0 mt-[1px]", tone === "warning" ? "text-warning" : "text-primary")} aria-hidden />
      <div className="min-w-0">
        {title && <div className="font-semibold text-foreground mb-0.5">{title}</div>}
        <div className="text-muted-foreground">{children}</div>
      </div>
    </div>
  );
}

const SCOPE_TONE: Record<string, string> = {
  full_weighted: "border-primary/50 text-primary",
  sample: "border-warning/60 text-warning",
  region: "border-line-strong text-muted-foreground",
  year: "border-line-strong text-muted-foreground",
  variant: "border-line-strong text-muted-foreground",
  records: "border-line-strong text-muted-foreground",
};
const SCOPE_LABEL: Record<string, string> = {
  full_weighted: "Tam veri", sample: "Örneklem", region: "Bölge", year: "Tek yıl", variant: "Kalite varyantı", records: "Kayıt düzeyi",
};

export function ScopeBadge({ scope, title }: { scope: string | null | undefined; title?: string }) {
  if (!scope) return null;
  return (
    <Badge variant="outline" className={cn("font-semibold", SCOPE_TONE[scope] ?? "")} title={title}>
      {SCOPE_LABEL[scope] ?? scope}
    </Badge>
  );
}

export function PageHeader({ title, description, actions, eyebrow }: { title: string; description?: ReactNode; actions?: ReactNode; eyebrow?: string }) {
  return (
    <header className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
      <div className="min-w-0">
        {eyebrow && <div className="eyebrow mb-1.5">{eyebrow}</div>}
        <h1 className="text-[24px] sm:text-[28px] font-bold leading-tight">{title}</h1>
        {description && <div className="mt-1.5 text-[14px] text-muted-foreground max-w-[78ch] leading-relaxed">{description}</div>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2 shrink-0">{actions}</div>}
    </header>
  );
}

export function Section({ title, description, actions, children, className, id }: {
  title: string; description?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; id?: string;
}) {
  return (
    <section className={cn("surface p-4 sm:p-5 min-w-0", className)} aria-labelledby={id ? `${id}-title` : undefined}>
      <div className="flex items-start justify-between gap-3 mb-3.5">
        <div className="min-w-0 flex-1">
          <h2 id={id ? `${id}-title` : undefined} className="text-[16px] font-bold leading-tight">{title}</h2>
          {description && <div className="text-[12.5px] text-muted-foreground mt-1 leading-snug max-w-[80ch]">{description}</div>}
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
      {children}
    </section>
  );
}

/** Tek sayının birden çok biçimde gösterimi için: tanımsız değerin nedeni. */
export function NotApplicable({ reason }: { reason: string }) {
  return <span className="text-subtle font-semibold" title={reason} aria-label={`Uygulanamaz: ${reason}`}>Uygulanamaz</span>;
}
