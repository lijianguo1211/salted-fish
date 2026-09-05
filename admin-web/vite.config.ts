import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// 后端地址：默认本机 30089（与 backend/.env 的 SALTED_FISH_PORT 一致），可用 VITE_API_BASE 覆盖
const api = process.env.VITE_API_BASE || 'http://127.0.0.1:30089';

export default defineConfig({
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
});