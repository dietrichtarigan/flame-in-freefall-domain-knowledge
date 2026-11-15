import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/**
 * Konfigurasi minimal untuk deployment kita.
 *
 * Berkas asli dari Figma Make memuat plugin khusus (site.json, overlay galat,
 * import-assets) yang hanya berguna di lingkungan Figma dan menolak dibangun
 * tanpa folder .figma. Semua itu tidak dibutuhkan di sini.
 *
 * base: "./"  -> aset dirujuk relatif, supaya hasil build bisa disajikan dari
 *                sub-jalur /flare/ oleh scripts/brain.py tanpa konfigurasi lagi.
 */
export default defineConfig({
  base: "./",
  plugins: [react()],
  build: {
    outDir: "../flare",
    emptyOutDir: true,
  },
});
