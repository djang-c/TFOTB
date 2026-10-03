import { defineConfig } from "@playwright/test";

// Demo-path E2E. Expects `make dev` (API :8000 + web :3000) or starts the web server itself.
export default defineConfig({
  testDir: "./e2e",
  use: { baseURL: "http://localhost:3000" },
  webServer: { command: "pnpm dev", url: "http://localhost:3000", reuseExistingServer: true },
});
