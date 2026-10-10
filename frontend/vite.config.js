import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// In development the browser talks to the Vite server and Vite forwards /api and /ws to the
// backend, so no CORS and no URL configuration is needed. In production nginx does the same
// (see nginx.conf). Set VITE_API_URL only if the backend lives somewhere else.
// 127.0.0.1 and not "localhost": on Windows localhost resolves to ::1 first, where uvicorn does not listen.
const backend = process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': backend,
      '/ws': { target: backend.replace(/^http/, 'ws'), ws: true },
    },
  },
  build: { outDir: 'dist' },
  test: {
    environment: 'jsdom',
    setupFiles: './src/setupTests.js',
    globals: true,
    css: false,
  },
});
