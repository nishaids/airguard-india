import diagnostic from "../lib/cams-diagnostic.json";

const period = (iso: string) => new Date(iso).toLocaleDateString("en-IN", { month: "short", year: "numeric", timeZone: "Asia/Kolkata" });

/**
 * What the raw atmospheric model's numbers have been worth at Indian stations.
 *
 * Every figure comes from cams-diagnostic.json, written by
 * scripts/explore_raw_cams_development.py from the guarded development join.
 * It is an exploratory diagnostic, not the primary evaluation, and says so.
 */
export default function ModelAccuracyNote({ ozoneLeads, modelled }: { ozoneLeads: boolean; modelled: boolean }) {
  if (!modelled) return null;
  const d = diagnostic;
  const when = `${period(d.period[0])} to ${period(d.period[1])}`;
  return <aside className="live-note" aria-label="How far to trust the modelled value">
    <p><strong>How far to trust a modelled value.</strong> On {d.station_days.toLocaleString("en-IN")} station-days from {when}, the raw CAMS-based AQI differed from what monitors measured by {Math.round(d.raw_cams_mae)} points on average and ran {Math.round(d.raw_cams_bias)} points high; simply repeating the measured value missed by {Math.round(d.persistence_mae)}. No correction is applied yet. This is an exploratory check on development data, not AirGuard&apos;s final evaluation.</p>
    {ozoneLeads && <p><strong>Ozone leads this estimate.</strong> The same CAMS model&apos;s ozone averaged {d.ozone_ratio.toFixed(1)} times the measured value in that check, and ozone set the modelled AQI on {Math.round(d.ozone_dominant_share_cams * 100)}% of station-days against {Math.round(d.ozone_dominant_share_measured * 100)}% in the measurements. An ozone-led modelled AQI is likely to be too high.</p>}
  </aside>;
}
