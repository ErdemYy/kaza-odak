// Hafif veri kancası: önbellek (anahtar = URL), iptal (AbortController), isteğe bağlı gecikme (debounce).
// Aynı URL'ye eşzamanlı istekler tek ağ isteğine indirgenir.
import { useEffect, useRef, useState } from "react";
import { getJSON } from "./api";

type Entry = { at: number; data?: unknown; promise?: Promise<unknown> };
const cache = new Map<string, Entry>();
const MAX_ENTRIES = 120;

export function cachedGet<T>(url: string, signal?: AbortSignal, ttlMs = 5 * 60_000): Promise<T> {
  const hit = cache.get(url);
  if (hit?.data !== undefined && Date.now() - hit.at < ttlMs) return Promise.resolve(hit.data as T);
  if (hit?.promise) return hit.promise as Promise<T>;
  // Paylaşılan istek tek bir çağıranın iptaliyle bozulmasın: iptal yalnızca bekleyen tarafı bırakır.
  const promise = getJSON<T>(url).then((data) => {
    cache.set(url, { at: Date.now(), data });
    if (cache.size > MAX_ENTRIES) cache.delete(cache.keys().next().value!);
    return data;
  }).catch((e) => {
    cache.delete(url);
    throw e;
  });
  cache.set(url, { at: Date.now(), promise });
  if (!signal) return promise;
  return new Promise<T>((resolve, reject) => {
    const onAbort = () => reject(new DOMException("İptal edildi", "AbortError"));
    if (signal.aborted) return onAbort();
    signal.addEventListener("abort", onAbort, { once: true });
    promise.then(resolve, reject).finally(() => signal.removeEventListener("abort", onAbort));
  });
}

export function invalidate(prefix: string) {
  for (const k of [...cache.keys()]) if (k.startsWith(prefix)) cache.delete(k);
}

export type QueryState<T> =
  | { status: "idle" | "loading"; data?: T; error?: undefined }
  | { status: "success"; data: T; error?: undefined }
  | { status: "error"; data?: T; error: Error };

/** ``url`` null ise istek yapılmaz. Önceki veri yeni istek sürerken korunur (titreme olmaz). */
export function useQuery<T>(url: string | null, opts: { debounceMs?: number; ttlMs?: number } = {}): QueryState<T> & { reload: () => void } {
  const [state, setState] = useState<QueryState<T>>({ status: url ? "loading" : "idle" });
  const [nonce, setNonce] = useState(0);
  const last = useRef<T | undefined>(undefined);
  useEffect(() => {
    if (!url) {
      setState({ status: "idle", data: last.current });
      return;
    }
    const ctrl = new AbortController();
    setState({ status: "loading", data: last.current });
    const t = window.setTimeout(() => {
      cachedGet<T>(url, ctrl.signal, opts.ttlMs).then((data) => {
        last.current = data;
        setState({ status: "success", data });
      }).catch((e: Error) => {
        if (e.name === "AbortError") return;
        setState({ status: "error", data: last.current, error: e });
      });
    }, opts.debounceMs ?? 0);
    return () => {
      window.clearTimeout(t);
      ctrl.abort();
    };
  }, [url, nonce, opts.debounceMs, opts.ttlMs]);
  return { ...state, reload: () => { if (url) invalidate(url); setNonce((n) => n + 1); } };
}
