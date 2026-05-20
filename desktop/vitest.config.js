import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.js"],
    globals: false,
    include: ["src/**/*.test.{js,jsx}", "tests/**/*.test.{js,jsx}"],
    css: false,
  },
});
