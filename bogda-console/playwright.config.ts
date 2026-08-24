import { defineConfig } from "@playwright/test";

const viewports = [
  { name: "desktop-1440", width: 1440, height: 900 },
  { name: "desktop-1280", width: 1280, height: 800 },
  { name: "tablet-768", width: 768, height: 1024 },
  { name: "phone-390", width: 390, height: 844 },
  { name: "phone-360", width: 360, height: 800 },
  { name: "phone-320", width: 320, height: 800 },
];

export default defineConfig({
  testDir: "tests/browser",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 30_000,
  expect: { timeout: 7_500 },
  reporter: [["line"]],
  use: {
    baseURL: "http://127.0.0.1:3101",
    headless: true,
    trace: "retain-on-failure",
  },
  projects: viewports.map(({ name, width, height }) => ({
    name,
    use: { viewport: { width, height } },
  })),
  webServer: {
    command: "py -3.11 -m bogda_console",
    url: "http://127.0.0.1:3101/api/v1/capabilities",
    reuseExistingServer: false,
    timeout: 60_000,
    env: {
      ...process.env,
      BOGDA_CONSOLE_PROFILE: "mock-all",
      BOGDA_CONSOLE_TEST_MODE: "1",
      BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS: "deployment-service,deployment-dorm",
      BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS: "schedule-service,schedule-dorm",
      BOGDA_CONSOLE_ALLOWED_QUEUE_IDS: "queue-service,queue-cpu,queue-gpu",
      BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES: "pi-service,dorm-x86",
      BOGDA_CONSOLE_REPLICA_COUNT: "1",
      BOGDA_CONSOLE_PUBLIC_HOST: "127.0.0.1",
      BOGDA_CONSOLE_PUBLIC_PORT: "3101",
    },
  },
});
