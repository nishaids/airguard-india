// English is complete. Health translations cannot be enabled without review.
export const translations = {
  en: { enabled: true, healthReviewed: true, title: "Air quality, with its evidence", search: "Search city, place, PIN code or coordinates", current: "Current air quality", tomorrow: "Tomorrow’s AirGuard AQI Forecast" },
  hi: { enabled: false, healthReviewed: false, title: "वायु गुणवत्ता", search: "", current: "", tomorrow: "" },
  ta: { enabled: false, healthReviewed: false, title: "காற்றின் தரம்", search: "", current: "", tomorrow: "" },
} as const;
export const copy = translations.en;
export const cohorts = ["General adult", "Children", "Older adults", "Asthma/COPD", "Heart conditions", "Pregnancy", "Outdoor workers"] as const;
export type Cohort = typeof cohorts[number];
// Deterministic exposure rules, not a clinical scoring model. Source and review
// rationale are in docs/DATA_SOURCES.md and the methodology page.
export function guidance(categoryIndex: number | undefined, cohort: Cohort) {
  if (categoryIndex === undefined) return "Air quality is unavailable. Check local monitoring and public-health advice before planning strenuous outdoor activity.";
  const sensitive = cohort !== "General adult";
  if (categoryIndex >= 4) return sensitive ? "Reduce time and strenuous activity outdoors during this high-pollution period. Consider a lower-exposure time or place and follow your clinician’s existing advice." : "Reduce prolonged or strenuous outdoor activity during this high-pollution period. Choose a lower-exposure time and route where possible.";
  if (categoryIndex >= 2) return sensitive ? "Consider shorter, less strenuous outdoor activity and a lower-exposure time or route. If symptoms occur, stop the activity and follow your existing care plan." : "Consider moving prolonged or strenuous activity to a lower-exposure time or route. Pay attention to symptoms.";
  if (categoryIndex === 1 && sensitive) return "Sensitive people may experience discomfort. Adjust the timing or intensity of activity if symptoms occur.";
  return "Use this forecast to plan your usual activities. Lower AQI does not mean zero health risk; avoid nearby smoke and heavily trafficked routes where possible.";
}
