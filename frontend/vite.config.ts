import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Single-page app: every route renders in the browser (the 3D views need it) and the build is a static folder
// (dist/client) that any static host can serve. The API address is read at build time from VITE_API_BASE.
export default defineConfig({
  resolve: { tsconfigPaths: true },
  plugins: [tanstackStart({ spa: { enabled: true } }), react(), tailwindcss()],
});
