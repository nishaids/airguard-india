import { defineConfig } from "@playwright/test";
// API acceptance uses the existing HTTP development service. No browser
// permissions or actual user location are accessed by these tests.
export default defineConfig({ testDir: "tests/e2e", timeout: 90000, workers: 1, use: { baseURL: process.env.AIRGUARD_TEST_URL || "http://127.0.0.1:3000" }, reporter: [["list"], ["json", { outputFile: "test-results/nationwide-api.json" }]] });
