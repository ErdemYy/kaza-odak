// 3D varlık kaydı (public/models/registry.json) türleri ve lisans doğrulaması.

export interface AssetRecord {
  id: string;
  name_tr: string;
  category: "vehicle" | "prop";
  file: string;
  lod1: { file: string; bytes: number; triangles: number; sha256: string } | null;
  source: { pack: string; archive: string; archive_sha256: string; entry: string; source_url: string; original_bytes: number; original_sha256: string };
  author: string;
  license: string;
  license_url: string;
  attribution: string;
  optimized: { bytes: number; sha256: string; triangles: number; vertices: number; textures: { size: [number, number]; bytes: number }[]; extensions: string[] };
  axes: { up: string; forward: string | null };
  native_size: [number, number, number];
  real_size_m: number;
  measure: "length" | "height";
  scale: number;
  ground_offset: number;
  animated_nodes: string[];
  optimization_status: string;
}

export interface AssetRegistry {
  generated_at: string;
  tool: string;
  archives: Record<string, { sha256: string; bytes: number; license: string }>;
  not_used: { file: string; reason: string }[];
  models: AssetRecord[];
}

const REQUIRED: (keyof AssetRecord)[] = ["id", "file", "author", "license", "license_url", "attribution", "source"];
/** Kabul edilen lisanslar (proje şartnamesi: CC0 veya uyumlu Creative Commons). */
const ALLOWED_LICENSE = /^(CC0|CC BY)/;

/** Lisans/kaynak bilgisi eksik veya kabul dışı modelleri reddeder; sorun listesini döndürür. */
export function validateRegistry(reg: AssetRegistry): string[] {
  const problems: string[] = [];
  if (!Array.isArray(reg.models) || reg.models.length === 0) problems.push("Kayıtta model yok");
  for (const m of reg.models ?? []) {
    for (const k of REQUIRED) if (m[k] === undefined || m[k] === null || m[k] === "") problems.push(`${m.id ?? "?"}: '${k}' eksik`);
    if (m.license && !ALLOWED_LICENSE.test(m.license)) problems.push(`${m.id}: lisans kabul dışı (${m.license})`);
    if (m.source && !/^https:\/\//.test(m.source.source_url ?? "")) problems.push(`${m.id}: kaynak URL'si yok`);
    if (!(m.scale > 0) || !Number.isFinite(m.scale)) problems.push(`${m.id}: geçersiz ölçek`);
  }
  return problems;
}
