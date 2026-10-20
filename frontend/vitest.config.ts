import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  // Saf mantık testleri node ortamında; bileşen testleri dosya başında "@vitest-environment jsdom" ile.
  test: { include: ["tests/unit/**/*.test.{ts,tsx}"], environment: "node", testTimeout: 30_000 },
});
