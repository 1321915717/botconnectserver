import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'

// WebSocket 宿主机端口：默认 8320（对应 docker-compose 里 8320→9101 的映射）。
// 如需其他端口，构建时用 VITE_WS_PORT 环境变量覆盖：
//   VITE_WS_PORT=9101 npm run build
const wsPort = process.env.VITE_WS_PORT || '8320'

// 打包产物直接输出到 Python 包内（botconnectserver/web_dist），
// 后端通过 importlib.resources 从包内读取，实现自包含。
export default defineConfig({
  plugins: [vue()],
  define: {
    'import.meta.env.VITE_WS_PORT': JSON.stringify(wsPort),
  },
  build: {
    outDir: fileURLToPath(new URL('../botconnectserver/web_dist', import.meta.url)),
    emptyOutDir: true,
  },
})
