/// <reference types="vitest/config" />
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// VITE_API_PROXY (e.g. https://d123.cloudfront.net) lets `npm run dev` talk to a deployed API
// when public/config.json sets "useMocks": false. Without it, /api is not proxied.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiProxy = env.VITE_API_PROXY;

  return {
    plugins: [react()],
    server: {
      proxy: apiProxy
        ? { '/api': { target: apiProxy, changeOrigin: true, secure: true } }
        : undefined,
    },
    build: {
      sourcemap: false,
      chunkSizeWarningLimit: 700,
    },
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['./src/test/setup.ts'],
      css: false,
      restoreMocks: true,
      testTimeout: 15_000,
    },
  };
});
