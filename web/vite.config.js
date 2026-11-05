import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'

// 打包产物直接输出到 Python 包内（botconnectserver/web_dist），
// 后端通过 importlib.resources 从包内读取，实现自包含。
export default defineConfig({
  plugins: [vue()],
  build: {
    outDir: fileURLToPath(new URL('../botconnectserver/web_dist', import.meta.url)),
    emptyOutDir: true,
  },
})
