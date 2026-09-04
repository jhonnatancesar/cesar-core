import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  base: "/admin/",
  plugins: [react(), tailwindcss()],
  build: { outDir: "../src/cesar_core/admin/static", emptyOutDir: true },
  server: { proxy: { "/admin/api": "http://127.0.0.1:8100" } },
  test: { environment: "jsdom", setupFiles: "./src/test-setup.ts" },
});
