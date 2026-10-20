import "@fontsource/plus-jakarta-sans/600.css";
import "@fontsource/plus-jakarta-sans/700.css";
import "@fontsource/plus-jakarta-sans/800.css";
import "@fontsource/manrope/400.css";
import "@fontsource/manrope/500.css";
import "@fontsource/manrope/600.css";
import "@fontsource/manrope/700.css";
import "maplibre-gl/dist/maplibre-gl.css";
import "./styles.css";
import { setWorkerUrl } from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";

// MapLibre 6 karo işleme worker'ını ayrı bir modül dosyası olarak yükler; Vite bunu varlık olarak kopyalar.
setWorkerUrl(workerUrl);
// Karanlık tema önceliklidir (shadcn dark: varyantları); hareket düzeyi CSS'e de yansır.
document.documentElement.classList.add("dark");
document.documentElement.dataset.motion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "reduced" : "full";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
