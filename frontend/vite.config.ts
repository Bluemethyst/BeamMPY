import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue({ template: { compilerOptions: { isCustomElement: tag => tag.startsWith('m3e-') } } })],
  build: { outDir: '../beammpy/web', emptyOutDir: true },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8080',
      '/socket.io': 'http://127.0.0.1:8080',
    },
  },
})
