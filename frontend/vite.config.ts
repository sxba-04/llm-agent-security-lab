import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_');
  if (env.VITE_HOSTED === 'true') {
    const value = env.VITE_API_BASE_URL || '';
    let valid = false;
    try { const url = new URL(value); valid = url.protocol === 'https:' && url.origin === value; } catch { /* Invalid build configuration. */ }
    if (!valid) throw new Error('VITE_HOSTED=true requires VITE_API_BASE_URL as an HTTPS origin without a trailing slash or path.');
  } else if (env.VITE_API_BASE_URL) {
    throw new Error('VITE_API_BASE_URL requires VITE_HOSTED=true.');
  }
  return {
  plugins: [react()],
  server: {
    host: '127.0.0.1', port: 5173, strictPort: true,
    proxy: { '/api': { target: 'http://127.0.0.1:8765', changeOrigin: false } },
  },
  preview: { host: '127.0.0.1' },
  test: { include: ['src/**/*.test.{ts,tsx}'], environment: 'jsdom', setupFiles: ['./src/test-setup.ts'], clearMocks: true },
  };
});
