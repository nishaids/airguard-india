"""Write the data-source register from the evidence files, not from memory.

    python -m scripts.build_data_source_register

Outputs ``results/research/data_source_manifest.json`` and
``docs/research/DATA_SOURCE_REGISTER.md``. Descriptive facts (provider, endpoint,
licence) are declared once below; every count is read from a committed evidence
artefact or, for live records, from a read-only database query. When a count
cannot be read it is written as ``null`` with the reason, never guessed.

The register separates five kinds of data and never lets one stand in for
another: OBSERVED, HISTORICAL_REANALYSIS, ARCHIVED_OPERATIONAL_FORECAST,
LIVE_FORECAST and MODELLED_OUTPUT. A short-lead proxy is not an archived
operational forecast, and data from OpenAQ is not official CPCB data.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results/research"
OUT_JSON = RES / "data_source_manifest.json"
OUT_MD = ROOT / "docs/research/DATA_SOURCE_REGISTER.md"
KINDS = ("OBSERVED", "HISTORICAL_REANALYSIS", "ARCHIVED_OPERATIONAL_FORECAST", "LIVE_FORECAST", "MODELLED_OUTPUT")


def read(path):
    p = ROOT / path
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def database_counts():
    """Read-only counts of live and prospective records. Returns (counts, reason-if-unavailable)."""
    try:
        from src.ingestion import settings
        settings.load_env()
        from src.nationwide.store import Store
        queries = {
            "provider_events": "select count(*) from airguard.provider_events",
            "nationwide_forecast_runs": "select count(*) from airguard.forecast_runs",
            "nationwide_forecast_verifications": "select count(*) from airguard.forecast_verifications",
            "nationwide_verified_target_days": "select count(distinct (f.target_start at time zone 'Asia/Kolkata')::date) from airguard.forecast_verifications v join airguard.forecast_runs f on f.id=v.forecast_run_id",
            "research_forecast_runs": "select count(*) from airguard.research_forecast_runs",
            "research_issue_days": "select count(distinct target_date) from airguard.research_forecast_runs",
            "research_forecast_verifications": "select count(*) from airguard.research_forecast_verifications",
            "live_observation_rows": "select count(*) from airguard.air_quality_observations",
            "fire_detection_rows": "select count(*) from airguard.fire_detections",
            "cpcb_successful_ingestions": "select count(*) from airguard.ingestion_runs where source_id='CPCB/data.gov.in' and status in ('SUCCESS','PARTIAL')",
            "cpcb_failed_ingestions": "select count(*) from airguard.ingestion_runs where source_id='CPCB/data.gov.in' and status='FAILED'",
        }
        counts = {}
        with Store().cursor() as cur:
            for name, sql in queries.items():
                cur.execute(sql)
                counts[name] = int(list(cur.fetchone().values())[0])
        return counts, None
    except Exception as error:  # noqa: BLE001 - the register still builds; the gap is stated
        return None, f"database not queried ({type(error).__name__})"


def build():
    measured = read("results/research/measured_dataset.json") or {}
    openaq = read("results/research/data_manifests/openaq_hours_manifest.json") or {}
    weather = read("results/research/data_manifests/weather_archive_manifest.json") or {}
    firms = read("results/research/data_manifests/firms_archive_manifest.json") or {}
    proxy = read("results/research/data_manifests/cams_archive_manifest.json") or {}
    acquisition = read("results/research/cams_development_acquisition.json") or {}
    plan = read("results/research/cams_development_acquisition_plan.v2.json") or {}
    join = read("results/research/cams_development_alignment.json") or {}
    legacy = read("data/raw/PROVENANCE.json") or {}
    corrections = read("results/research/data_manifests/station_metadata_corrections.v2.json")
    live, live_gap = database_counts()

    raw_hours = openaq.get("rows")
    excluded = measured.get("hourly_exclusion_reason_counts") or {}
    station_days = measured.get("station_days")
    rejected = measured.get("rejected_targets")
    verified = [j for j in (acquisition.get("jobs") or {}).values() if j.get("status") == "VERIFIED_GRIB"]
    # A date is usable only when both halves of its pair (surface and lowest model level) are verified.
    group = {j["id"]: j["group"] for j in plan.get("jobs") or []}
    halves = {}
    for job_id, job in (acquisition.get("jobs") or {}).items():
        if job.get("status") == "VERIFIED_GRIB":
            halves.setdefault(group.get(job_id), set()).update((job.get("request") or {}).get("date", []))
    run_dates = sorted(set.intersection(*halves.values())) if len(halves) == 2 else []

    sources = [
        {
            "id": "A_B_station_observations", "kind": "OBSERVED",
            "provider": "OpenAQ v3, upstream provider CPCB (Central Pollution Control Board monitoring network)",
            "official_dataset_name": "OpenAQ sensor hourly aggregates for CPCB-network monitors",
            "url": "https://openaq.org", "api_endpoint": "https://api.openaq.org/v3/sensors/{id}/hours",
            "time_coverage": measured.get("date_coverage"), "geographic_coverage": f"{measured.get('usable_cities')} Indian cities",
            "station_count": measured.get("usable_stations"), "selected_stations": measured.get("selected_stations"),
            "pollutants": ["PM2.5", "PM10", "O3"], "units": "ug/m3 (gas sensors reporting ppb are not converted to mass)",
            "sampling_frequency": "hourly aggregates; daily station targets derived by AirGuard",
            "download_date": openaq.get("updated_at"), "license": "OpenAQ terms; per-station upstream licence metadata preserved (docs/LICENSES.md)",
            "update_frequency": "as delivered by OpenAQ; its CPCB copy stopped advancing on 2026-10-07 14:30 UTC (observed 2026-10-09)",
            "missing_data": {"raw_hourly_rows": raw_hours, "hourly_exclusions": excluded,
                             "station_days": station_days, "rejected_station_day_targets": rejected,
                             "rejected_target_share": round(rejected / station_days, 4) if station_days and rejected is not None else None},
            "quality_control": "75% hourly coverage, provider flags, zero readings, stuck-sensor runs, invalid values; Severe days kept as lower-bound censored targets",
            "issue_time_availability": measured.get("conditional_assumption"),
            "is_official_cpcb_data": False,
            "note": measured.get("provenance"),
            "evidence": ["results/research/measured_dataset.json", "results/research/data_manifests/openaq_hours_manifest.json"],
        },
        {
            "id": "A_direct_cpcb_feed", "kind": "OBSERVED",
            "provider": "CPCB via data.gov.in", "official_dataset_name": "Real time Air Quality Index from various locations",
            "url": "https://www.data.gov.in", "api_endpoint": "https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69",
            "time_coverage": None, "station_count": None, "pollutants": "per-station min/max/average; no unit published",
            "license": "Government Open Data Licence - India",
            "status": "UNAVAILABLE: no successful response recorded",
            "live_ingestion_attempts": {k: (live or {}).get(k) for k in ("cpcb_successful_ingestions", "cpcb_failed_ingestions")},
            "is_official_cpcb_data": True, "used_in_research": False,
            "evidence": ["docs/airguard2/live_data_implementation.md", "database: airguard.ingestion_runs"],
        },
        {
            "id": "C_weather_archive", "kind": "ARCHIVED_OPERATIONAL_FORECAST",
            "provider": "Open-Meteo (NOAA GFS, model gfs_seamless)", "official_dataset_name": "Open-Meteo Previous Runs API",
            "url": "https://open-meteo.com", "api_endpoint": weather.get("endpoint"),
            "time_coverage": weather.get("window"), "geographic_coverage": f"{weather.get('points')} station-matched points",
            "variables": weather.get("variables"), "lead": weather.get("lead"),
            "issue_time_valid": weather.get("issue_time_valid"), "issue_time_availability": weather.get("why"),
            "not_available": weather.get("not_available"), "download_date": weather.get("updated_at"),
            "license": "Open-Meteo CC BY 4.0; free API non-commercial",
            "evidence": ["results/research/data_manifests/weather_archive_manifest.json"],
        },
        {
            "id": "D_cams_operational_archive", "kind": "ARCHIVED_OPERATIONAL_FORECAST",
            "provider": "Copernicus Atmosphere Monitoring Service (ECMWF), via the Atmosphere Data Store",
            "official_dataset_name": "CAMS global atmospheric composition forecasts", "url": "https://ads.atmosphere.copernicus.eu",
            "api_endpoint": "ADS API (cdsapi), dataset cams-global-atmospheric-composition-forecasts",
            "plan_run_range": plan.get("run_range"), "planned_jobs": len(plan.get("jobs") or []),
            "verified_jobs": len(verified), "paired_initialisation_dates": [run_dates[0], run_dates[-1]] if run_dates else None,
            "paired_initialisation_date_count": len(run_dates), "area": plan.get("area"),
            "product": "00 UTC operational forecast, surface and lowest model level, 0.4-degree grid",
            "issue_time_valid": True, "join": {k: join.get(k) for k in ("rows", "stations", "cities", "dates", "valid_targets", "censored_severe_retained")},
            "license": "Copernicus licence (free; attribution 'Generated using Copernicus Atmosphere Monitoring Service information')",
            "acquisition_state": acquisition.get("counts"), "reanalysis_substitution": "prohibited",
            "evidence": ["results/research/cams_development_acquisition.json", "results/research/cams_development_alignment.json"],
        },
        {
            "id": "D_cams_short_lead_proxy", "kind": "MODELLED_OUTPUT",
            "provider": "CAMS global via Open-Meteo", "official_dataset_name": "Open-Meteo Air Quality API, past hours",
            "api_endpoint": proxy.get("endpoint"), "time_coverage": proxy.get("window"), "variables": proxy.get("variables"),
            "issue_time_valid": proxy.get("issue_time_valid"), "issue_time_availability": proxy.get("why_not"),
            "use": "exploratory only; never a substitute for archived operational forecasts",
            "license": "Open-Meteo CC BY 4.0 + Copernicus attribution; free API non-commercial",
            "evidence": ["results/research/data_manifests/cams_archive_manifest.json"],
        },
        {
            "id": "E_station_metadata", "kind": "OBSERVED",
            "provider": "OpenAQ locations, with versioned AirGuard corrections", "api_endpoint": "https://api.openaq.org/v3/locations",
            "catalogue_universe": measured.get("catalogue_universe"), "corrections_file_present": corrections is not None,
            "note": "Coordinates and city labels as delivered, corrected only through versioned correction files; current-catalogue survivorship is a disclosed limitation",
            "evidence": ["results/research/data_manifests/station_selection.json", "results/research/data_manifests/station_metadata_corrections.v2.json"],
        },
        {
            "id": "F_legacy_aqi", "kind": "OBSERVED",
            "provider": "Kaggle export of CPCB data (2015-2020)", "official_dataset_name": (legacy.get("dataset") or {}).get("title_configured"),
            "url": (legacy.get("dataset") or {}).get("kaggle_url"), "download_date": legacy.get("downloaded_at_utc"),
            "license": (legacy.get("license") or {}).get("string_as_displayed_on_kaggle"),
            "upstream": (legacy.get("upstream_source") or {}).get("organisation"),
            "use": "1.0 historical replay only; cannot establish today's conditions or forecast availability",
            "evidence": ["data/raw/PROVENANCE.json"],
        },
        {
            "id": "G_live_inputs", "kind": "LIVE_FORECAST",
            "provider": "Open-Meteo (CAMS global air quality, GFS weather), OpenAQ, NASA FIRMS",
            "api_endpoint": "air-quality-api.open-meteo.com/v1/air-quality; api.open-meteo.com/v1/forecast; api.openaq.org/v3; firms.modaps.eosdis.nasa.gov/api/area",
            "label_on_site": "MODELLED unless a recent nearby station supplies MEASURED values",
            "records": {k: (live or {}).get(k) for k in ("provider_events", "live_observation_rows", "fire_detection_rows")},
            "records_unavailable_reason": live_gap,
            "evidence": ["docs/DATA_SOURCES.md", "database: airguard.provider_events"],
        },
        {
            "id": "H_prospective_records", "kind": "LIVE_FORECAST",
            "provider": "AirGuard (issued forecasts) and OpenAQ (later outcomes)",
            "records": {k: (live or {}).get(k) for k in ("nationwide_forecast_runs", "nationwide_forecast_verifications", "nationwide_verified_target_days",
                                                         "research_forecast_runs", "research_issue_days", "research_forecast_verifications")},
            "records_unavailable_reason": live_gap,
            "rule": "issued forecasts are append-only; outcomes are paired later and never alter the issued value",
            "evidence": ["database: airguard.forecast_runs / research_forecast_runs and their verification tables"],
        },
        {
            "id": "satellite_fire", "kind": "OBSERVED",
            "provider": "NASA FIRMS", "official_dataset_name": firms.get("source"), "api_endpoint": firms.get("endpoint"),
            "time_coverage": firms.get("window"), "area": firms.get("area"),
            "issue_time_availability": firms.get("why"), "research_use": measured.get("fire_features"),
            "license": "NASA open data policy; FIRMS attribution", "note": "thermal anomalies, not air-quality observations",
            "evidence": ["results/research/data_manifests/firms_archive_manifest.json"],
        },
    ]
    assert all(s["kind"] in KINDS for s in sources)
    return {"generated_by": "scripts/build_data_source_register.py",
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "kinds": list(KINDS), "sources": sources}


def markdown(manifest):
    s = {x["id"]: x for x in manifest["sources"]}
    m, d, a = s["A_B_station_observations"], s["D_cams_operational_archive"], s["A_direct_cpcb_feed"]
    h, g = s["H_prospective_records"], s["G_live_inputs"]
    md = m["missing_data"]
    lines = [
        "# Data source register",
        "",
        f"Generated {manifest['generated_at_utc']} by `scripts/build_data_source_register.py` from committed evidence and read-only database counts. "
        "Machine-readable copy: `results/research/data_source_manifest.json`. Licences and attribution: `docs/LICENSES.md`; provider quotas: `docs/DATA_SOURCES.md`.",
        "",
        "Every source carries one of five kinds and none stands in for another: **OBSERVED**, **HISTORICAL_REANALYSIS** (none is used), "
        "**ARCHIVED_OPERATIONAL_FORECAST**, **LIVE_FORECAST**, **MODELLED_OUTPUT**.",
        "",
        "| Source | Kind | Provider | Coverage | Issue-time status | Evidence |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for x in manifest["sources"]:
        cover = x.get("time_coverage") or x.get("paired_initialisation_dates") or x.get("plan_run_range") or "-"
        status = x.get("status") or ("valid" if x.get("issue_time_valid") is True else "NOT valid" if x.get("issue_time_valid") is False else "see notes")
        lines.append(f"| `{x['id']}` | {x['kind']} | {x['provider']} | {cover} | {status} | {', '.join('`'+e+'`' for e in x['evidence'][:2])} |")
    lines += [
        "",
        "## What the numbers say",
        "",
        f"- **Station observations** come from CPCB-network monitors **through OpenAQ**: {m['station_count']} usable stations in "
        f"{m['geographic_coverage']}, {m['time_coverage'][0]} to {m['time_coverage'][1]}. This is not official CPCB data and the targets "
        "are AirGuard's CPCB-style daily AQI from PM2.5, PM10 and ozone, not the bulletin AQI.",
        f"- Missing data: of {md['station_days']:,} station-days, {md['rejected_station_day_targets']:,} ({md['rejected_target_share']:.1%}) have no valid "
        f"target. Of {md['raw_hourly_rows']:,} raw hourly rows, {md['hourly_exclusions'].get('under_75_percent_coverage', 0):,} fall in under-covered hours.",
        f"- **The official CPCB feed** (data.gov.in) has never returned data to this project: {a['live_ingestion_attempts']['cpcb_successful_ingestions']} "
        f"successful and {a['live_ingestion_attempts']['cpcb_failed_ingestions']} failed recorded ingestions.",
        f"- **Archived operational CAMS**: {d['verified_jobs']} of {d['planned_jobs']} planned ADS files verified, covering "
        f"{d['paired_initialisation_date_count']} initialisation dates with both surface and model-level fields ({d['paired_initialisation_dates'][0]} to {d['paired_initialisation_dates'][1]}). "
        f"Current join: {d['join']['rows']:,} station-days, {d['join']['stations']} stations, {d['join']['dates']} dates. Reanalysis substitution is prohibited.",
        "- **The Open-Meteo CAMS past-hours series is not an archived forecast**: its values come from runs initialised after the issue time, so it is "
        "kept as exploratory modelled output only.",
        "- **Weather predictors** use Open-Meteo's previous-runs archive at a two-day lead, which is older than what an operator would have had, so it "
        "handicaps rather than flatters the weather features. Boundary-layer height is not archived at any previous-run lead.",
        "- **Fire detections** are archived but withheld from the strict models: acquisition time does not prove publication time.",
    ]
    if h["records_unavailable_reason"]:
        lines.append(f"- Live and prospective counts: {h['records_unavailable_reason']}.")
    else:
        r = h["records"]
        lines.append(f"- **Prospective records**: {r['research_forecast_runs']} fixed-time research forecasts over {r['research_issue_days']} target days with "
                     f"{r['research_forecast_verifications']} verified outcomes; {r['nationwide_forecast_runs']:,} on-demand nationwide forecasts with "
                     f"{r['nationwide_forecast_verifications']} station pairs over {r['nationwide_verified_target_days']} verified target days.")
        lines.append(f"- **Live inputs**: {g['records']['provider_events']:,} recorded provider events.")
    lines += ["", "Per-source details (endpoint, units, sampling, licence, quality control, issue-time rule) are in the JSON manifest.", ""]
    return "\n".join(lines)


def main():
    manifest = build()
    OUT_JSON.write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")
    OUT_MD.write_text(markdown(manifest), encoding="utf-8")
    print(json.dumps({"sources": len(manifest["sources"]), "json": OUT_JSON.relative_to(ROOT).as_posix(), "markdown": OUT_MD.relative_to(ROOT).as_posix()}))


if __name__ == "__main__":
    main()
