"use client";

import { useEffect, useMemo, useState } from "react";
import { Area, AreaChart, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceDot, ResponsiveContainer } from "recharts";
import { Metric, Banner, Loading, Badge, SectionTitle, Table } from "../components/ui";
import { BAND_COLOUR, BUCKET_COLOUR, axisTick, tooltipProps } from "../components/theme";

const shortDate = (iso) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
const longDate = (iso) => new Date(iso).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" });

const BASELINE_LABEL = {
  airguard_corrected_inputs: "AirGuard forecast (as shown on this page)",
  airguard_correction_14_days_old: "AirGuard forecast, if the correction were two weeks old",
  airguard_uncorrected_inputs: "AirGuard forecast, inputs left uncorrected",
  baseline_same_as_today_modelled: "Baseline: tomorrow = today (modelled)",
  baseline_atmospheric_model_next_day: "Baseline: the atmospheric model's own next day",
  baseline_same_as_today_measured: "Baseline: tomorrow = today (measured; not available live)",
};

function CityCard({ city, selected, onSelect }) {
  if (!city.ok) {
    return (
      <div className="card" style={{ opacity: 0.6 }}>
        <strong>{city.city}</strong>
        <p className="caption" style={{ marginBottom: 0 }}>{city.message}</p>
      </div>
    );
  }
  const colour = BUCKET_COLOUR[city.tomorrow.bucket] || "#7e8899";
  const change = city.tomorrow.aqi - city.today.aqi;
  return (
    <button
      type="button"
      className="card"
      onClick={() => onSelect(city.city)}
      style={{
        textAlign: "left", cursor: "pointer", font: "inherit", color: "inherit", width: "100%",
        borderColor: selected ? colour : undefined, boxShadow: selected ? `0 0 0 1px ${colour}` : undefined,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
        <strong>{city.city}</strong>
        <Badge colour={colour}>{city.tomorrow.bucket}</Badge>
      </div>
      <div style={{ fontSize: "2.1rem", fontWeight: 700, lineHeight: 1.15, marginTop: 6 }}>{city.tomorrow.aqi.toFixed(0)}</div>
      <div className="caption" style={{ margin: 0 }}>
        tomorrow &middot; today {city.today.aqi.toFixed(0)} ({change >= 0 ? "+" : ""}{change.toFixed(0)})
      </div>
    </button>
  );
}

export default function LivePage() {
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(null);
  const [selected, setSelected] = useState("Delhi");
  const [cohort, setCohort] = useState("healthy_adult");

  useEffect(() => {
    fetch("/api/live_forecast")
      .then(async (r) => {
        const body = await r.json();
        if (body.ok) setData(body);
        else setFailed(body.message || "The live forecast is unavailable.");
      })
      .catch(() => setFailed("The live forecast service did not respond."));
  }, []);

  const city = useMemo(() => {
    if (!data) return null;
    const usable = data.cities.filter((c) => c.ok);
    return usable.find((c) => c.city === selected) || usable[0] || null;
  }, [data, selected]);

  const chart = useMemo(() => {
    if (!city) return [];
    return [
      ...city.history.map((h) => ({ date: shortDate(h.date), modelled: h.aqi })),
      { date: shortDate(city.tomorrow.date), modelled: null },
    ];
  }, [city]);

  if (failed) {
    return (
      <div>
        <span className="eyebrow">Tomorrow, from current conditions</span>
        <h1>Live forecast</h1>
        <Banner kind="error">
          {failed} Nothing is shown in its place. The <a href="/forecast">historical explorer</a> still works.
        </Banner>
      </div>
    );
  }
  if (!data) return <Loading rows={2} />;

  const evaluation = data.evaluation;
  const headline = evaluation?.holdout?.airguard_corrected_inputs;
  const chosen = city?.cohorts.find((c) => c.cohort === cohort);

  return (
    <div>
      <span className="eyebrow">Tomorrow, from current conditions</span>
      <h1>Live forecast</h1>
      <p className="caption" style={{ maxWidth: "80ch" }}>
        Tomorrow&apos;s AQI for twelve cities, computed at {data.local_time}. The forecasting model is the one
        described on the rest of this site; what is new is that it is fed today&apos;s conditions.
      </p>

      <Banner kind="warn">
        <strong>Inputs are {data.inputs.label}.</strong> They come from the {data.inputs.source}, on a grid of about
        40 km. They are not readings from monitoring stations: no current government-monitor data could be obtained
        when this page was built. This is an experimental academic forecast, not an official one. For official air
        quality, use the Central Pollution Control Board.
      </Banner>

      <div className="grid grid-4" style={{ marginTop: 18 }}>
        {data.cities.map((c) => (
          <CityCard key={c.city} city={c} selected={city?.city === c.city} onSelect={setSelected} />
        ))}
      </div>

      {city && (
        <>
          <SectionTitle eyebrow={city.city} caption={`Forecast for ${longDate(city.tomorrow.date)}.`}>
            {city.city}: {city.tomorrow.aqi.toFixed(0)}, {city.tomorrow.bucket}
          </SectionTitle>

          <div className="grid grid-4">
            <Metric hero label="Forecast AQI, tomorrow" value={city.tomorrow.aqi.toFixed(0)} delta={city.tomorrow.bucket} />
            <Metric
              hero
              label="Likely range"
              value={city.tomorrow.likely_range ? `${city.tomorrow.likely_range[0].toFixed(0)} – ${city.tomorrow.likely_range[1].toFixed(0)}` : "n/a"}
              delta="where 8 in 10 measured values fell in testing"
              help="From the backtest: the middle 80% of the forecast's errors against measured values, applied to this forecast."
            />
            <Metric hero label="Today, modelled" value={city.today.aqi.toFixed(0)} delta={`${city.today.bucket} · led by ${city.today.dominant_pollutant}`} />
            <Metric
              hero
              label="Atmospheric model, tomorrow"
              value={city.tomorrow.atmospheric_model_aqi !== null ? city.tomorrow.atmospheric_model_aqi.toFixed(0) : "n/a"}
              delta="for comparison"
              help="The AQI computed directly from the atmospheric model's own forecast for tomorrow, with the same correction."
            />
          </div>

          <div className="grid grid-1-4">
            <div>
              <h3>Two weeks of modelled AQI, and tomorrow&apos;s forecast</h3>
              <div className="card" style={{ padding: "18px 10px 8px" }}>
                <ResponsiveContainer width="100%" height={300}>
                  <AreaChart data={chart} margin={{ top: 16, right: 22, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="liveFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#56B4E9" stopOpacity={0.45} />
                        <stop offset="100%" stopColor="#56B4E9" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid vertical={false} />
                    <XAxis dataKey="date" tick={axisTick} tickLine={false} axisLine={false} minTickGap={24} />
                    <YAxis tick={axisTick} tickLine={false} axisLine={false} width={42} />
                    <Tooltip {...tooltipProps} />
                    <Area type="monotone" dataKey="modelled" name="Modelled AQI" stroke="#56B4E9" strokeWidth={2} fill="url(#liveFill)" dot={false} />
                    <ReferenceDot
                      x={shortDate(city.tomorrow.date)} y={city.tomorrow.aqi} r={6}
                      fill="#D55E00" stroke="#06080c" strokeWidth={2}
                      label={{ value: "forecast", position: "top", fill: "#D55E00", fontSize: 11 }}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              <p className="caption">
                Today&apos;s value is a daily mean that includes {city.today.forecast_hours_in_daily_mean} hours still
                to come, taken from the atmospheric model&apos;s forecast.
              </p>
            </div>

            <div>
              <h3>Today&apos;s modelled concentrations</h3>
              <Table
                columns={["Pollutant", "Used", "As modelled", "Unit"]}
                rows={Object.keys(city.today.concentrations).map((p) => ({
                  Pollutant: p,
                  Used: city.today.concentrations[p],
                  "As modelled": city.today.concentrations_before_correction[p],
                  Unit: city.today.units[p],
                }))}
              />
              <p className="caption">
                &ldquo;Used&rdquo; differs from &ldquo;as modelled&rdquo; where a correction was fitted:{" "}
                {data.inputs.corrected_against_measurements ? data.inputs.correction_note : "none is applied"}.
              </p>
            </div>
          </div>

          <h3>Health Advisory Index for today&apos;s modelled air</h3>
          <div className="card">
            <label htmlFor="live-cohort">Cohort</label>
            <select id="live-cohort" value={cohort} onChange={(e) => setCohort(e.target.value)} style={{ maxWidth: 320 }}>
              {city.cohorts.map((c) => (
                <option key={c.cohort} value={c.cohort}>{c.label}</option>
              ))}
            </select>
          </div>
          {chosen && (
            <div className="advisory" style={{ "--band-colour": BAND_COLOUR[chosen.band] || "#7e8899" }}>
              <div className="advisory-band">
                <span className="dot" />
                {chosen.band} risk &mdash; {chosen.label} &middot; HAI {chosen.hai.toFixed(0)}
              </div>
              <p>{chosen.advisory.text}</p>
            </div>
          )}
          <p className="caption">
            The index describes today&apos;s modelled air, not tomorrow&apos;s. It is a research index, it has not been
            clinically validated, and it is not medical advice.
          </p>
        </>
      )}

      <SectionTitle
        eyebrow="How far to trust it"
        caption={evaluation ? `Tested against ${evaluation.truth}. Window ${evaluation.window.first_day} to ${evaluation.window.last_day}; every figure is from days after ${evaluation.window.holdout_from}, which the correction never saw.` : undefined}
      >
        Tested against government monitors
      </SectionTitle>

      {evaluation && headline ? (
        <>
          <div className="grid grid-4">
            <Metric label="Typical miss" value={`${headline.mae} AQI`} delta="mean absolute error" />
            <Metric label="Average lean" value={`${headline.bias > 0 ? "+" : ""}${headline.bias} AQI`} delta={headline.bias > 0 ? "forecast runs high" : "forecast runs low"} />
            <Metric label="Right category" value={`${headline.same_category_percent}%`} delta={`within one: ${headline.within_one_category_percent}%`} />
            <Metric label="City-days tested" value={headline.n.toLocaleString()} delta="held out" />
          </div>
          <Table
            columns={["Forecast for tomorrow", "MAE", "Bias", "RMSE", "Right category %", "Days"]}
            rows={Object.entries(evaluation.holdout)
              .filter(([, m]) => m.n)
              .map(([name, m]) => ({
                "Forecast for tomorrow": BASELINE_LABEL[name] || name,
                MAE: m.mae, Bias: m.bias, RMSE: m.rmse, "Right category %": m.same_category_percent, Days: m.n,
              }))}
          />
          <p className="caption" style={{ maxWidth: "90ch" }}>
            {evaluation.optimism_note} The atmospheric-model baseline is flattered for the same reason: its past
            values are analyses, not day-ahead forecasts.
          </p>
          {evaluation.measured_inputs?.airguard?.n ? (
            <Banner kind="info">
              <strong>What limits this page is its inputs.</strong> A forecast that simply repeats today&apos;s
              measured value misses by {evaluation.holdout.baseline_same_as_today_measured.mae} points, far better
              than anything above, but it needs current measurements, which could not be obtained. Fed measured
              PM2.5, PM10 and ozone, the AirGuard model itself missed by {evaluation.measured_inputs.airguard.mae}{" "}
              points on {evaluation.measured_inputs.airguard.n} city-days, against{" "}
              {evaluation.measured_inputs.same_as_today_measured.mae} for repeating today on the same days: on 2026
              data it did not beat that simple rule.
            </Banner>
          ) : null}
        </>
      ) : (
        <Banner kind="warn">This forecast has not been tested against measurements. Treat it as a demonstration only.</Banner>
      )}

      <SectionTitle eyebrow="Read before relying on it">What this page does not tell you</SectionTitle>
      <div className="card">
        <ul style={{ margin: 0, paddingLeft: 20, lineHeight: 1.7 }}>
          {data.caveats.map((c) => <li key={c}>{c}</li>)}
          <li>Latest modelled hour used: {data.inputs.latest_hour.replace("T", " ")} IST. Model: {data.model}.</li>
        </ul>
      </div>
    </div>
  );
}
