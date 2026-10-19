// OpenFreeMap (OpenMapTiles şeması) bina katmanında NYC yükseklik verisinin denetimi.
// OpenMapTiles, OSM'de height/min_height veya building:levels etiketi olmayan binalara
// render_height için varsayılan bir değer atar. Bu betik beş ilçeden örnek z14 karolarını indirir,
// render_height dağılımını ölçer ve sonucu reports/phase4/building_height_audit.json'a yazar.
// Kullanım: node scripts/audit-building-heights.mjs
import { VectorTile } from "@mapbox/vector-tile";
import { PbfReader as Pbf } from "pbf";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const OUT = resolve(here, "../../reports/phase4/building_height_audit.json");
const TILEJSON = "https://tiles.openfreemap.org/planet";

// Her ilçeden yoğun yerleşim noktaları (WGS84)
const SAMPLES = {
  MANHATTAN: [[-73.985, 40.758], [-74.009, 40.709], [-73.958, 40.775]],
  BROOKLYN: [[-73.99, 40.693], [-73.944, 40.678], [-73.897, 40.661]],
  QUEENS: [[-73.83, 40.758], [-73.79, 40.705], [-73.92, 40.744]],
  BRONX: [[-73.896, 40.861], [-73.917, 40.827], [-73.858, 40.84]],
  "STATEN ISLAND": [[-74.077, 40.642], [-74.153, 40.59], [-74.19, 40.545]],
};

const tileOf = (lon, lat, z) => {
  const n = 2 ** z;
  const x = Math.floor(((lon + 180) / 360) * n);
  const r = (lat * Math.PI) / 180;
  const y = Math.floor(((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2) * n);
  return [x, y];
};

const tj = await (await fetch(TILEJSON)).json();
const template = tj.tiles[0];
const result = { source: TILEJSON, tiles_template: template, zoom: 14, generated_at: new Date().toISOString(), boroughs: {} };
const all = [];
for (const [borough, pts] of Object.entries(SAMPLES)) {
  const heights = [];
  let hide3d = 0;
  for (const [lon, lat] of pts) {
    const [x, y] = tileOf(lon, lat, 14);
    const url = template.replace("{z}", "14").replace("{x}", x).replace("{y}", y);
    const buf = new Uint8Array(await (await fetch(url)).arrayBuffer());
    const layer = new VectorTile(new Pbf(buf)).layers.building;
    if (!layer) continue;
    // Planetiler aynı öznitelikli binaları tek MultiPolygon özelliğinde birleştirir: bina sayısı =
    // dış halka sayısı (ilk halkayla aynı yönlü halkalar), öznitelik özelliğin tüm halkalarına aittir.
    for (let i = 0; i < layer.length; i++) {
      const f = layer.feature(i);
      const p = f.properties;
      const rings = f.loadGeometry();
      const area = (r) => r.reduce((s, q, k) => s + (r[(k + 1) % r.length].x - q.x) * (r[(k + 1) % r.length].y + q.y), 0);
      const sign = Math.sign(area(rings[0]));
      const outer = rings.filter((r) => Math.sign(area(r)) === sign).length;
      for (let k = 0; k < outer; k++) {
        if (p.hide_3d) hide3d++;
        heights.push(Number(p.render_height ?? NaN));
      }
    }
  }
  const valid = heights.filter((h) => Number.isFinite(h));
  const counts = {};
  for (const h of valid) counts[h] = (counts[h] ?? 0) + 1;
  const top = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 5).map(([h, c]) => ({ render_height: Number(h), share: c / valid.length }));
  result.boroughs[borough] = {
    tiles: pts.length, buildings: heights.length, hide_3d: hide3d,
    share_render_height_5: valid.filter((h) => h === 5).length / valid.length,
    median: valid.sort((a, b) => a - b)[Math.floor(valid.length / 2)], max: Math.max(...valid), most_common: top,
  };
  all.push(...valid);
}
result.overall = { buildings: all.length, share_render_height_5: all.filter((h) => h === 5).length / all.length };
mkdirSync(dirname(OUT), { recursive: true });
writeFileSync(OUT, JSON.stringify(result, null, 2));
console.log(JSON.stringify(result, null, 2));
