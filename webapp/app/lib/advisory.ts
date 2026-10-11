import { guidance, type Cohort } from "./i18n";
export const ADVISORY_VERSION = "exposure-guidance-v1";
export function advisory(categoryIndex: number | undefined, cohort: Cohort) {
  return { version: ADVISORY_VERSION, severity: categoryIndex === undefined ? "UNAVAILABLE" : categoryIndex >= 4 ? "HIGH" : categoryIndex >= 2 ? "ELEVATED" : "LOWER", shortGuidance: guidance(categoryIndex, cohort), outdoorGuidance: "Use the relatively lower-exposure window as a planning aid; lower AQI does not mean zero health risk.", disclaimer: "AirGuard provides environmental information and general exposure guidance, not medical advice." };
}
