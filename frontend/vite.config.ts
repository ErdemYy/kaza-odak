import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";

// Geliştirmede /api istekleri FastAPI katman sunucusuna (saferoute serve) yönlendirilir.
const api = process.env.SAFEROUTE_API ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: { port: 5173, proxy: { "/api": api } },
  preview: { port: 4173, proxy: { "/api": api } },
  build: {
    target: "es2022",
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        manualChunks: (id: string) =>
          id.includes("node_modules/maplibre-gl") ? "maplibre" : id.includes("node_modules/three") ? "three"
            : /node_modules\/(recharts|d3-|victory-vendor)/.test(id) ? "charts" : undefined,
      },
    },
  },
});
