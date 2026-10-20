// Kayıt filtreleri (sunucu tarafında GERÇEK kayıtlara uygulanır). Saf fonksiyonlar; birim testli.

export type InjuryFilter = "any" | "injury" | "no_injury";
export type FatalFilter = "any" | "fatal" | "non_fatal";

export interface FilterState {
  boroughs: string[];
  dateFrom: string | null; // YYYY-AA-GG
  dateTo: string | null;
  years: number[];
  months: number[]; // 1–12
  dows: number[]; // 0 = Pazartesi
  hourFrom: number | null;
  hourTo: number | null;
  vehicles: string[];
  factor: string | null;
  injury: InjuryFilter;
  fatal: FatalFilter;
  excludeMidnight: boolean;
}

export const EMPTY_FILTERS: FilterState = {
  boroughs: [], dateFrom: null, dateTo: null, years: [], months: [], dows: [], hourFrom: null, hourTo: null,
  vehicles: [], factor: null, injury: "any", fatal: "any", excludeMidnight: false,
};

export const MONTHS_TR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"];
export const DOWS_TR = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"];
export const DOWS_SHORT = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];

const sortNum = (a: number[]) => [...new Set(a)].sort((x, y) => x - y);
const sortStr = (a: string[]) => [...new Set(a)].sort();

/** Kanonik biçim: aynı filtre aynı sorgu dizesini ve önbellek anahtarını üretir. */
export function normalize(f: FilterState): FilterState {
  return { ...f, boroughs: sortStr(f.boroughs), years: sortNum(f.years), months: sortNum(f.months), dows: sortNum(f.dows),
    vehicles: sortStr(f.vehicles) };
}

export function isEmpty(f: FilterState): boolean {
  return toQuery(f) === "";
}

/** API sorgu parametreleri (boş alanlar yazılmaz). */
export function toParams(f: FilterState): Record<string, string> {
  const n = normalize(f);
  const p: Record<string, string> = {};
  if (n.boroughs.length) p.boroughs = n.boroughs.join(",");
  if (n.dateFrom) p.date_from = n.dateFrom;
  if (n.dateTo) p.date_to = n.dateTo;
  if (n.years.length) p.years = n.years.join(",");
  if (n.months.length) p.months = n.months.join(",");
  if (n.dows.length) p.dows = n.dows.join(",");
  if (n.hourFrom !== null && n.hourTo !== null) {
    p.hour_from = String(n.hourFrom);
    p.hour_to = String(n.hourTo);
  }
  if (n.vehicles.length) p.vehicles = n.vehicles.join(",");
  if (n.factor) p.factor = n.factor;
  if (n.injury !== "any") p.injury = n.injury;
  if (n.fatal !== "any") p.fatal = n.fatal;
  if (n.excludeMidnight) p.exclude_midnight = "true";
  return p;
}

export function toQuery(f: FilterState): string {
  return new URLSearchParams(toParams(f)).toString();
}

/** Laboratuvar isteği gövdesi için (sunucu aynı ayrıştırıcıyı kullanır). */
export function toBody(f: FilterState): Record<string, string> {
  return toParams(f);
}

/** İstemci tarafı doğrulama (sunucu ayrıca doğrular; burada kullanıcıya anında geri bildirim). */
export function validate(f: FilterState): string[] {
  const errors: string[] = [];
  if (f.dateFrom && f.dateTo && f.dateFrom > f.dateTo) errors.push("Başlangıç tarihi bitiş tarihinden sonra olamaz.");
  if ((f.hourFrom === null) !== (f.hourTo === null)) errors.push("Saat aralığının iki ucu da seçilmeli.");
  for (const h of [f.hourFrom, f.hourTo]) if (h !== null && (h < 0 || h > 23 || !Number.isInteger(h))) errors.push("Saat 0–23 arası olmalı.");
  return errors;
}

export function hourRangeLabel(from: number, to: number): string {
  const pad = (h: number) => String(h).padStart(2, "0");
  return `${pad(from)}:00–${pad(to)}:59${from > to ? " (gece yarısını aşar)" : ""}`;
}

/** Kullanıcıya gösterilen Türkçe filtre özeti (sunucunun describe_tr ile aynı anlam). */
export function describe(f: FilterState, labels: { borough: (b: string) => string; vehicle: (v: string) => string }): string[] {
  const n = normalize(f);
  const out: string[] = [];
  if (n.boroughs.length) out.push(`İlçe: ${n.boroughs.map(labels.borough).join(", ")}`);
  if (n.dateFrom || n.dateTo) out.push(`Tarih: ${n.dateFrom ?? "başlangıç"} → ${n.dateTo ?? "son kayıt"}`);
  if (n.years.length) out.push(`Yıl: ${n.years.join(", ")}`);
  if (n.months.length) out.push(`Ay: ${n.months.map((m) => MONTHS_TR[m - 1]).join(", ")}`);
  if (n.dows.length) out.push(`Gün: ${n.dows.map((d) => DOWS_SHORT[d]).join(", ")}`);
  if (n.hourFrom !== null && n.hourTo !== null) out.push(`Saat: ${hourRangeLabel(n.hourFrom, n.hourTo)}`);
  if (n.vehicles.length) out.push(`Araç: ${n.vehicles.map(labels.vehicle).join(", ")}`);
  if (n.factor) out.push(`Kayıtlı katkı faktörü: ${n.factor}`);
  if (n.injury !== "any") out.push(n.injury === "injury" ? "Yaralanmalı kazalar" : "Yaralanmasız kazalar");
  if (n.fatal !== "any") out.push(n.fatal === "fatal" ? "Ölümle sonuçlanan kazalar" : "Ölümsüz kazalar");
  if (n.excludeMidnight) out.push("00:00 şüpheli kayıtlar hariç");
  return out;
}

export function activeCount(f: FilterState): number {
  return Object.keys(toParams(f)).filter((k) => k !== "hour_to").length;
}

// ---------------------------------------------------------------- zaman dilimi (oynatma)
export type Granularity = "year" | "month" | "hour" | "dow";

export interface TimeSlice {
  granularity: Granularity;
  key: string; // year: "2019", month: "2019-03", hour: "07", dow: "0"
}

/** Oynatma dilimini kullanıcı filtrelerinin üzerine uygular (dilim, ilgili alanı daraltır). */
export function applySlice(f: FilterState, s: TimeSlice | null): FilterState {
  if (!s) return f;
  switch (s.granularity) {
    case "year":
      return { ...f, years: [Number(s.key)] };
    case "month": {
      const [y, m] = s.key.split("-").map(Number);
      return { ...f, years: [y], months: [m] };
    }
    case "hour": {
      const h = Number(s.key);
      return { ...f, hourFrom: h, hourTo: h };
    }
    case "dow":
      return { ...f, dows: [Number(s.key)] };
  }
}

export function sliceLabel(s: TimeSlice): string {
  switch (s.granularity) {
    case "year":
      return s.key;
    case "month": {
      const [y, m] = s.key.split("-").map(Number);
      return `${MONTHS_TR[m - 1]} ${y}`;
    }
    case "hour":
      return `${s.key}:00–${s.key}:59`;
    case "dow":
      return DOWS_TR[Number(s.key)];
  }
}
