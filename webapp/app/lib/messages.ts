// Translation catalogue with per-string review state.
//
// Health guidance that is wrong in Tamil or Hindi is worse than English the
// reader has to work at, so review is tracked per string rather than per
// locale: a reviewed navigation label must not drag an unreviewed advisory into
// the page with it. `message()` serves a translation only when that exact
// string has been approved by a named reviewer, and falls back to English
// otherwise. docs/I18N_REVIEW.md holds the ledger.
//
// next-intl is the intended library once there is reviewed text to serve. It is
// not installed yet: its routing and provider plumbing would add a dependency
// and locale-prefixed routes while every non-English health string is still
// unreviewed, and the gate below is the part that actually prevents harm.

export type Locale = "en" | "hi" | "ta";
export type Category = "ui" | "health";

export type Entry = {
  text: string;
  category: Category;
  /** Name of the human who approved this exact string, or null. */
  reviewedBy: string | null;
  reviewedAt: string | null;
};

export const LOCALE_NAMES: Record<Locale, string> = { en: "English", hi: "हिन्दी", ta: "தமிழ்" };

const english = (text: string, category: Category = "ui"): Entry => ({
  text,
  category,
  reviewedBy: "source language",
  reviewedAt: null,
});

const untranslated = (category: Category = "ui"): Entry => ({
  text: "",
  category,
  reviewedBy: null,
  reviewedAt: null,
});

export const KEYS = [
  "title",
  "search",
  "current",
  "tomorrow",
  "measuredBadge",
  "modelledBadge",
  "cohortPrompt",
  "advisoryHeading",
  "advisoryGeneral",
  "advisorySensitive",
  "notMedicalAdvice",
] as const;
export type Key = typeof KEYS[number];

const HEALTH_KEYS: Key[] = ["advisoryHeading", "advisoryGeneral", "advisorySensitive", "notMedicalAdvice"];

export const catalogue: Record<Locale, Record<Key, Entry>> = {
  en: {
    title: english("Air quality, with its evidence"),
    search: english("Search city, place, PIN code or coordinates"),
    current: english("Current air quality"),
    tomorrow: english("Tomorrow’s AirGuard AQI forecast"),
    measuredBadge: english("Measured at a station"),
    modelledBadge: english("Modelled on a 0.4° grid"),
    cohortPrompt: english("Who is this forecast for?"),
    advisoryHeading: english("What this means for you", "health"),
    advisoryGeneral: english(
      "Use this forecast to plan your usual activities. A lower AQI does not mean zero health risk.",
      "health",
    ),
    advisorySensitive: english(
      "Consider shorter, less strenuous outdoor activity and a lower-exposure time or route. If symptoms occur, stop and follow your existing care plan.",
      "health",
    ),
    notMedicalAdvice: english("This is general information, not medical advice.", "health"),
  },
  // Hindi and Tamil: nothing is served until a named reviewer approves each
  // string. Machine or unreviewed translation of health guidance is refused.
  hi: Object.fromEntries(KEYS.map(key => [key, untranslated(HEALTH_KEYS.includes(key) ? "health" : "ui")])) as Record<Key, Entry>,
  ta: Object.fromEntries(KEYS.map(key => [key, untranslated(HEALTH_KEYS.includes(key) ? "health" : "ui")])) as Record<Key, Entry>,
};

/** True when this exact string may be shown in this locale. */
export function isServable(locale: Locale, key: Key): boolean {
  const entry = catalogue[locale]?.[key];
  if (!entry) return false;
  if (locale === "en") return true;
  return Boolean(entry.text && entry.reviewedBy);
}

/** The string to display, falling back to English when review is missing. */
export function message(locale: Locale, key: Key): string {
  return isServable(locale, key) ? catalogue[locale][key].text : catalogue.en[key].text;
}

/** Per-locale review state, for the status page and docs/I18N_REVIEW.md. */
export function reviewState() {
  return (Object.keys(catalogue) as Locale[]).map(locale => {
    const entries = KEYS.map(key => catalogue[locale][key]);
    const health = KEYS.filter(key => catalogue[locale][key].category === "health");
    return {
      locale,
      name: LOCALE_NAMES[locale],
      translated: entries.filter(entry => entry.text).length,
      total: KEYS.length,
      reviewed: KEYS.filter(key => isServable(locale, key)).length,
      healthReviewed: health.every(key => isServable(locale, key)),
      reviewers: Array.from(new Set(entries.map(entry => entry.reviewedBy).filter(Boolean))) as string[],
      servable: locale === "en" || KEYS.some(key => isServable(locale, key)),
    };
  });
}
