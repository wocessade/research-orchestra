import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export function resolveDevPorts(env: Record<string, string | undefined>) {
  const publicPort = Number(env.BOGDA_CONSOLE_PUBLIC_PORT ?? "3101");
  const bffPort = Number(env.BOGDA_CONSOLE_BFF_PORT ?? "3102");
  for (const [name, port] of [["public", publicPort], ["bff", bffPort]] as const) {
    if (port === 3100) throw new Error(`3100 is reserved for the legacy console (${name})`);
    if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error(`invalid ${name} port`);
  }
  return { publicPort, bffPort };
}

const ports = resolveDevPorts(process.env);

export default defineConfig({
  root: "frontend",
  plugins: [react()],
  server: {
    host: process.env.BOGDA_CONSOLE_PUBLIC_HOST ?? "127.0.0.1",
    port: ports.publicPort,
    strictPort: true,
    proxy: { "/api": `http://127.0.0.1:${ports.bffPort}` },
  },
  build: { outDir: "dist", emptyOutDir: true },
  test: {
    environment: "jsdom",
    include: ["../tests/frontend/**/*.test.{ts,tsx}"],
    setupFiles: ["../tests/frontend/setup.ts"],
  },
});
