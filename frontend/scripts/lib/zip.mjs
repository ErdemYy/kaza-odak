// Salt-okunur, bağımlılıksız ZIP okuyucu (merkezi dizin + stored/deflate). Kaynak arşivler değiştirilmez.

/**
 * GLB'yi JSON + BIN parçalarına ayırır ve harici doku URI'lerini `resolve(uri)` ile çözer.
 * Dönen nesne gltf-transform `io.readJSON()` girdisidir (harici dokular gömülür).
 */
export function glbToJSONDocument(glb, resolve) {
  const b = Buffer.from(glb);
  if (b.readUInt32LE(0) !== 0x46546c67) throw new Error("GLB sihirli sayısı yok (glTF ikili dosyası değil)");
  if (b.readUInt32LE(4) !== 2) throw new Error(`Desteklenmeyen glTF sürümü: ${b.readUInt32LE(4)}`);
  if (b.readUInt32LE(8) !== b.length) throw new Error("GLB uzunluk alanı dosya boyutuyla uyuşmuyor (kesik dosya)");
  let p = 12, json = null, bin = null;
  while (p < b.length) {
    const len = b.readUInt32LE(p), type = b.readUInt32LE(p + 4);
    const chunk = b.subarray(p + 8, p + 8 + len);
    if (type === 0x4e4f534a) json = JSON.parse(chunk.toString("utf8"));
    else if (type === 0x004e4942) bin = new Uint8Array(chunk);
    p += 8 + len;
  }
  if (!json) throw new Error("GLB JSON parçası yok");
  const resources = {};
  if (bin) resources["@glb.bin"] = bin;
  for (const img of json.images ?? []) if (img.uri && !img.uri.startsWith("data:")) resources[img.uri] = new Uint8Array(resolve(img.uri));
  for (const buf of json.buffers ?? []) if (buf.uri && !buf.uri.startsWith("data:")) resources[buf.uri] = new Uint8Array(resolve(buf.uri));
  return { json, resources };
}
import { readFileSync } from "node:fs";
import { inflateRawSync } from "node:zlib";

export function readZip(path) {
  const buf = readFileSync(path);
  let eocd = buf.length - 22;
  while (eocd >= 0 && buf.readUInt32LE(eocd) !== 0x06054b50) eocd--;
  if (eocd < 0) throw new Error(`ZIP merkezi dizini bulunamadı: ${path}`);
  const count = buf.readUInt16LE(eocd + 10);
  let p = buf.readUInt32LE(eocd + 16);
  const entries = new Map();
  for (let i = 0; i < count; i++) {
    if (buf.readUInt32LE(p) !== 0x02014b50) throw new Error("Bozuk merkezi dizin kaydı");
    const method = buf.readUInt16LE(p + 10);
    const csize = buf.readUInt32LE(p + 20);
    const nlen = buf.readUInt16LE(p + 28), xlen = buf.readUInt16LE(p + 30), clen = buf.readUInt16LE(p + 32);
    const local = buf.readUInt32LE(p + 42);
    const name = buf.toString("utf8", p + 46, p + 46 + nlen);
    entries.set(name, { method, csize, local });
    p += 46 + nlen + xlen + clen;
  }
  return {
    names: [...entries.keys()],
    read(name) {
      const e = entries.get(name);
      if (!e) throw new Error(`ZIP içinde yok: ${name}`);
      const start = e.local + 30 + buf.readUInt16LE(e.local + 26) + buf.readUInt16LE(e.local + 28);
      const data = buf.subarray(start, start + e.csize);
      if (e.method === 0) return Buffer.from(data);
      if (e.method === 8) return inflateRawSync(data);
      throw new Error(`Desteklenmeyen sıkıştırma yöntemi ${e.method}: ${name}`);
    },
  };
}
