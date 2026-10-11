import { defineConfig } from "vitest/config";
import { transformWithOxc } from "vite";
export default defineConfig({ plugins: [{ name: "next-jsx-pages", enforce: "pre", async transform(code, id) { if (/\/app\/.*\.js$/.test(id)) return transformWithOxc(code, id, { lang: "jsx", jsx: { runtime: "automatic" } }); } }], test: { environment: "jsdom", include: ["tests/**/*.test.tsx", "tests/**/*.test.ts"], setupFiles: ["./tests/setup.ts"], globals: true } });
