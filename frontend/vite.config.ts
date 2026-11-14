import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Server-side configuration only; inference credentials stay in Python.
const apiTarget = process.env.IMAGE_API_PROXY_TARGET ?? 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  worker: { format: 'es' },
  // Prebundle the lazy PDF reader so the first PDF import does not reload the UI.
  optimizeDeps: { include: ['pdfjs-dist/legacy/build/pdf.mjs'] },
  server: { proxy: { '/api': apiTarget } },
  preview: { proxy: { '/api': apiTarget } },
});
