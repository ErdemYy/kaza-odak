// Türkçe sayı/biçim yardımcıları (binlik ayırıcı nokta, ondalık virgül).
const int = new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 0 });

export const fmtInt = (v: number | null | undefined) => (v == null ? "—" : int.format(v));
export const fmtPct = (v: number | null | undefined, d = 1) =>
  v == null ? "—" : `%${new Intl.NumberFormat("tr-TR", { minimumFractionDigits: d, maximumFractionDigits: d }).format(v * 100)}`;
export const fmtNum = (v: number | null | undefined, d = 1) =>
  v == null ? "—" : new Intl.NumberFormat("tr-TR", { minimumFractionDigits: d, maximumFractionDigits: d }).format(v);
export const fmtCoord = (lng: number, lat: number) => `${lat.toFixed(5)}° K, ${Math.abs(lng).toFixed(5)}° B`;
export const fmtBytes = (b: number) => (b < 1024 ? `${b} B` : b < 1048576 ? `${fmtNum(b / 1024, 1)} KB` : `${fmtNum(b / 1048576, 2)} MB`);

// Araç kategorileri: Faz 2 vehicle_type_mapping.category_tr ile aynı adlar.
const TITLE: Record<string, string> = {
  PASSENGER_CAR: "Binek otomobil", SUV: "SUV / station wagon", TAXI_FOR_HIRE: "Taksi / kiralık araç", UNKNOWN: "Bilinmiyor",
  TRUCK_COMMERCIAL: "Kamyon / ticari", BUS: "Otobüs", VAN: "Van / minibüs", BICYCLE: "Bisiklet", OTHER: "Diğer",
  MOTORCYCLE: "Motosiklet / moped", EMERGENCY: "Acil durum aracı", E_MICROMOBILITY: "Elektrikli mikromobilite",
  morning: "Sabah", afternoon: "Öğleden sonra", evening: "Akşam", night: "Gece",
};
export const trLabel = (v: string) => TITLE[v] ?? v;
