import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Local dev: proxy /api to the FastAPI backend so no VITE_API_BASE is needed
  server: { proxy: { "/api": "http://localhost:8000" } },
});
