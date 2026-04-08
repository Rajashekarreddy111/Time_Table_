import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

const devHost = process.env.VITE_DEV_HOST ?? "127.0.0.1";

// https://vitejs.dev/config/
export default defineConfig(() => ({
  server: {
    host: devHost,
    port: 8080,
    strictPort: true,
    hmr: {
      overlay: false,
      host: devHost,
    },
  },
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
}));
