import { describe, expect, it } from "vitest";
import { KEYS, catalogue, isServable, message, reviewState, type Locale } from "../app/lib/messages";

describe("translation review gate", () => {
  it("serves English for every key", () => {
    for (const key of KEYS) {
      expect(isServable("en", key)).toBe(true);
      expect(message("en", key).length).toBeGreaterThan(0);
    }
  });

  it("refuses every unreviewed Hindi and Tamil string and falls back to English", () => {
    for (const locale of ["hi", "ta"] as Locale[]) {
      for (const key of KEYS) {
        expect(isServable(locale, key)).toBe(false);
        expect(message(locale, key)).toBe(catalogue.en[key].text);
      }
    }
  });

  it("will not serve a translated health string without a named reviewer", () => {
    const planted = { ...catalogue.hi.advisorySensitive, text: "unreviewed text", reviewedBy: null };
    const original = catalogue.hi.advisorySensitive;
    (catalogue.hi as Record<string, typeof planted>).advisorySensitive = planted;
    try {
      expect(isServable("hi", "advisorySensitive")).toBe(false);
      expect(message("hi", "advisorySensitive")).toBe(catalogue.en.advisorySensitive.text);
    } finally {
      (catalogue.hi as Record<string, typeof original>).advisorySensitive = original;
    }
  });

  it("serves a translated string once a named reviewer has approved it", () => {
    const original = catalogue.ta.title;
    (catalogue.ta as Record<string, typeof original>).title = {
      text: "காற்றின் தரம்", category: "ui", reviewedBy: "Test Reviewer", reviewedAt: "2026-10-11",
    };
    try {
      expect(isServable("ta", "title")).toBe(true);
      expect(message("ta", "title")).toBe("காற்றின் தரம்");
      // One approved UI string must not imply the health strings are approved.
      expect(isServable("ta", "advisoryGeneral")).toBe(false);
    } finally {
      (catalogue.ta as Record<string, typeof original>).title = original;
    }
  });

  it("reports review state per locale, with health approval tracked separately", () => {
    const state = reviewState();
    const english = state.find(row => row.locale === "en");
    expect(english?.healthReviewed).toBe(true);
    for (const locale of ["hi", "ta"]) {
      const row = state.find(entry => entry.locale === locale);
      expect(row?.reviewed).toBe(0);
      expect(row?.healthReviewed).toBe(false);
      expect(row?.reviewers).toEqual([]);
    }
  });
});
