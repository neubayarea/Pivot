import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // REST and the match WebSocket go to the local API (`uv run python -m pivot_api`).
    proxy: { "/api": { target: "http://127.0.0.1:8000", ws: true } },
  },
  test: { environment: "node" },
});
