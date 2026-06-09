import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "/app/static/",
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/v1": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
    },
  },
  build: {
    outDir: "../backend/src/pawcare/web",
    emptyOutDir: true,
    cssCodeSplit: false,
    rollupOptions: {
      output: {
        entryFileNames: "app.js",
        assetFileNames: (assetInfo) =>
          assetInfo.name?.endsWith(".css") ? "app.css" : "assets/[name][extname]",
      },
    },
  },
});
