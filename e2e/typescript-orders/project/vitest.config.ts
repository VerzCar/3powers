import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    globals: true,
    include: ["tests/**/*.{test,spec}.ts"],
    coverage: {
      provider: "v8",
      // LCOV is the contract the 3Powers core consumes for diff-coverage.
      reporter: ["text", "lcov"],
      reportsDirectory: "coverage",
      include: ["src/**/*.ts"],
      exclude: ["src/index.ts"],
    },
  },
});
