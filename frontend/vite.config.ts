import { defineConfig } from "vite";

// Minimal Vite config. The backend API is expected to run on :8000 during
// local development; VITE_API_BASE_URL can override this (e.g. in Docker).
export default defineConfig({
  server: {
    port: 5173,
  },
});
