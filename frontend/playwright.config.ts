import { defineConfig } from "@playwright/test";

const port = Number(process.env.FRONTEND_E2E_PORT || "4173");

export default defineConfig({
  testDir: "./e2e",
  timeout: 120000,
  fullyParallel: false,
  reporter: "list",
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    headless: true,
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_CHROME_PATH || "/usr/bin/google-chrome",
      args: ["--no-sandbox", "--disable-dev-shm-usage"],
    },
  },
  webServer: {
    command: "bash ./scripts/start-sketchmath-e2e.sh",
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: false,
    timeout: 120000,
    env: {
      FRIDAY_SKETCHMATH_ENABLED: "1",
      FRIDAY_SKETCHMATH_DOCUMENT_V1_ENABLED: "1",
      REACT_APP_SKETCHMATH_ENABLED: "1",
      REACT_APP_SKETCHMATH_FEATURE_HISTORY_ENABLED: "1",
      FRIDAY_SKETCHMATH_HOLE_FEATURES_ENABLED: "1",
      REACT_APP_SKETCHMATH_HOLE_FEATURES_ENABLED: "1",
      FRIDAY_SKETCHMATH_REVOLVE_FEATURES_ENABLED: "1",
      REACT_APP_SKETCHMATH_REVOLVE_FEATURES_ENABLED: "1",
      FRIDAY_SKETCHMATH_FILLET_FEATURES_ENABLED: "1",
      REACT_APP_SKETCHMATH_FILLET_FEATURES_ENABLED: "1",
      FRIDAY_SKETCHMATH_CHAMFER_FEATURES_ENABLED: "1",
      REACT_APP_SKETCHMATH_CHAMFER_FEATURES_ENABLED: "1",
      FRIDAY_SKETCHMATH_PATTERN_FEATURES_ENABLED: "1",
      REACT_APP_SKETCHMATH_PATTERN_FEATURES_ENABLED: "1",
      FRIDAY_SKETCHMATH_MIRROR_FEATURES_ENABLED: "1",
      REACT_APP_SKETCHMATH_MIRROR_FEATURES_ENABLED: "1",
      FRIDAY_SKETCHMATH_ARTIFACT_JOBS_ENABLED: "1",
      REACT_APP_SKETCHMATH_ARTIFACT_JOBS_ENABLED: "1",
      FRONTEND_E2E_PORT: String(port),
    },
  },
});
