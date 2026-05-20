import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.js"],
    globals: false,
    include: ["src/**/*.test.{js,jsx}", "tests/**/*.test.{js,jsx}"],
    css: false,
  },
});
