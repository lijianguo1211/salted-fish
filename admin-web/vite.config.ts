import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// 后端地址：读 admin-web/.env*（VITE_API_BASE），默认本机 30089
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const api = env.VITE_API_BASE || 'http://127.0.0.1:30089';

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        // 开发时把 /api 代理到 FastAPI，避免跨域
        '/api': {
          target: api,
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api/, ''),
        },
      },
    },
  };
});