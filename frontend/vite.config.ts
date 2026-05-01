import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// Dev-time convenience: proxy /api and known backend routes to the FastAPI
// server so the frontend can fetch relative paths too. In prod we use
// VITE_API_URL baked into the build.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiTarget = env.VITE_API_URL || 'http://127.0.0.1:8000';

  return {
    base: './',
    plugins: [react()],
    server: {
      port: 5173,
      host: true,
      proxy: {
        '/api':                  { target: apiTarget, changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, '') },
        '/health':               { target: apiTarget, changeOrigin: true },
        '/chat':                 { target: apiTarget, changeOrigin: true },
        '/models':               { target: apiTarget, changeOrigin: true },
        '/auth':                 { target: apiTarget, changeOrigin: true },
        '/igris':                { target: apiTarget, changeOrigin: true },
        '/actions':              { target: apiTarget, changeOrigin: true },
        '/observability':        { target: apiTarget, changeOrigin: true },
        '/monitor':              { target: apiTarget, changeOrigin: true },
        '/system':               { target: apiTarget, changeOrigin: true },
        '/ws':                   { target: apiTarget, changeOrigin: true, ws: true },
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: false,
      target: 'es2020',
    },
  };
});
