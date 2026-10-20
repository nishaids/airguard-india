"""Build the final novelty and prior-art audit from verified literature records.

    python -m scripts.build_novelty_audit

Inputs: the existing full-text review (results/research/literature_fulltext_review.json),
identifier verification (literature_verification.json) and the logged search
(literature_search_log.json), all produced by committed scripts. The studies
added from the 2026-10-20 search are recorded below at the depth actually read
(abstract or title); unknown design facts are written as "not established".

Outputs: results/research/literature_matrix.json and
docs/research/FINAL_NOVELTY_AND_PRIOR_ART_AUDIT.md.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results/research"
OUT_JSON = RES / "literature_matrix.json"
OUT_MD = ROOT / "docs/research/FINAL_NOVELTY_AND_PRIOR_ART_AUDIT.md"
NA = "not established"

#: Studies found by the logged 2026-10-20 Crossref search and judged relevant on title/abstract screening.
SEARCH_ADDITIONS = [
    {"id": "munteanu_2026", "authors": "Munteanu et al.", "year": 2026, "venue": "Sensors", "doi": "10.3390/s26185844",
     "title": "Evaluating Graph-Centrality Context for Station-Level Correction of CAMS Air Quality Reanalysis in Lombardy from 2018 to 2021",
     "text_status": "ABSTRACT_ONLY", "data_geography": "CAMS European reanalysis vs ARPA Lombardia stations, Italy, 2018-2021",
     "horizon": "none (reanalysis correction)", "methods": "graph-centrality features with GTWR, XGBoost, random forest",
     "relation": "Station-level CAMS correction exists; it uses reanalysis, not archived forecasts available at issue time."},
    {"id": "sarafian_2025", "authors": "Sarafian et al.", "year": 2025, "venue": "Remote Sensing", "doi": "10.3390/rs17020222",
     "title": "Correction of CAMS PM10 Reanalysis Improves AI-Based Dust Event Forecast", "text_status": "ABSTRACT_ONLY",
     "data_geography": "CAMS PM10 reanalysis vs in-situ stations; dust events", "horizon": "dust-event forecasting downstream",
     "methods": "ML correction of CAMS PM10 fields with in-situ data", "extremes": "targets rare dust events",
     "relation": "ML correction of CAMS against stations for rare events; reanalysis input, so not an issue-time forecast test."},
    {"id": "stortini_2020", "authors": "Stortini et al.", "year": 2020, "venue": "Atmosphere", "doi": "10.3390/atmos11050447",
     "title": "Operational Forecast and Daily Assessment of the Air Quality in Italy: A Copernicus-CAMS Downstream Service",
     "text_status": "ABSTRACT_ONLY", "data_geography": "Italy, national domain", "horizon": "daily operational forecast",
     "methods": "CAMS-downstream national forecasting and assessment chain", "deployment": "operational national service (ASI/SNPA)",
     "relation": "Operational CAMS-downstream services exist; AirGuard is not the first operational CAMS-based forecaster."},
    {"id": "june_2021", "authors": "June et al.", "year": 2021, "venue": "J. Air & Waste Management Assoc.", "doi": "10.1080/10962247.2020.1856216",
     "title": "Operational bias correction for PM2.5 using the AIRPACT air quality forecast system in the Pacific Northwest",
     "text_status": "TITLE_ONLY", "data_geography": "Pacific Northwest, USA", "methods": "operational PM2.5 bias correction (details not read)",
     "deployment": "operational forecast system (AIRPACT)",
     "relation": "Operational station bias correction of a chemical-transport forecast is established practice."},
    {"id": "gualtieri_2025", "authors": "Gualtieri et al.", "year": 2025, "venue": "Atmospheric Pollution Research", "doi": "10.1016/j.apr.2025.102567",
     "title": "Assessing capability of Copernicus Atmosphere Monitoring Service to forecast PM2.5 and PM10 hourly concentrations in a European air quality hotspot",
     "text_status": "TITLE_ONLY", "data_geography": "a European hotspot", "methods": "evaluation of CAMS hourly PM forecasts",
     "relation": "CAMS forecast skill against stations is routinely evaluated outside India."},
    {"id": "kaffashzadeh_2024", "authors": "Kaffashzadeh and Kazemi", "year": 2024, "venue": "Geosci. Model Dev.", "doi": "10.5194/gmd-17-4155-2024",
     "title": "Assessment of surface ozone products from downscaled CAMS reanalysis and CAMS daily forecast using urban air quality monitoring stations in Iran",
     "text_status": "ABSTRACT_ONLY", "data_geography": "27 urban stations, Iran, 2020", "methods": "spectral decomposition of CAMS reanalysis and daily-forecast ozone",
     "relation": "CAMS surface-ozone mismatch at urban stations is documented elsewhere; consistent with AirGuard's large ozone correction factors."},
    {"id": "ghude_2020", "authors": "Ghude et al.", "year": 2020, "venue": "Current Science", "doi": "10.18520/cs/v118/i11/1803-1815",
     "title": "Evaluation of PM2.5 Forecast using Chemical Data Assimilation in the WRF-Chem Model: A Novel Initiative Under the Ministry of Earth Sciences Air Quality Early Warning System for Delhi, India",
     "text_status": "TITLE_ONLY", "data_geography": "Delhi, India", "methods": "WRF-Chem with chemical data assimilation",
     "deployment": "MoES Air Quality Early Warning System (operational)",
     "relation": "India already has an operational national early-warning system for Delhi; AirGuard does not replace or rival it."},
    {"id": "kalita_2023", "authors": "Kalita et al.", "year": 2023, "venue": "Atmospheric Environment", "doi": "10.1016/j.atmosenv.2023.120013",
     "title": "Forecasting of an unusual dust event over western India by the Air Quality Early Warning System",
     "text_status": "TITLE_ONLY", "data_geography": "western India", "extremes": "single dust event", "deployment": "AQEWS (operational)",
     "relation": "Indian operational extreme-event forecasting exists for specific events."},
    {"id": "lawrence_2025", "authors": "Lawrence et al.", "year": 2025, "venue": "Environ. Monit. Assess.", "doi": "10.1007/s10661-025-14700-4",
     "title": "Evaluating machine learning models and imputation strategies for Air Quality Index forecasting in urban India",
     "text_status": "TITLE_ONLY", "data_geography": "urban India", "methods": "ML models and imputation for AQI forecasting",
     "relation": "Indian AQI forecasting with ML is a crowded area; model choice alone is not novel."},
    {"id": "dar_2025", "authors": "Dar et al.", "year": 2025, "venue": "Franklin Open", "doi": "10.1016/j.fraope.2025.100435",
     "title": "Spatiotemporal clustering and multivariate forecasting of air quality index across Indian cities using machine learning and deep learning models",
     "text_status": "TITLE_ONLY", "data_geography": "multiple Indian cities", "methods": "clustering plus ML/DL forecasting",
     "relation": "Multi-city Indian AQI forecasting and clustering exist."},
    {"id": "b_2026", "authors": "B. et al.", "year": 2026, "venue": "Air Qual. Atmos. Health", "doi": "10.1007/s11869-026-01973-y",
     "title": "Integrated air quality monitoring and PM2.5 forecasting in India: a comparative study of machine learning and deep learning approaches",
     "text_status": "TITLE_ONLY", "data_geography": "India", "methods": "ML vs DL comparison",
     "relation": "Further Indian ML/DL comparison; whether issue-time availability was audited is not established."},
    {"id": "murad_2021", "authors": "Murad et al.", "year": 2021, "venue": "Sensors", "doi": "10.3390/s21238009",
     "title": "Probabilistic Deep Learning to Quantify Uncertainty in Air Quality Forecasting", "text_status": "ABSTRACT_ONLY",
     "methods": "probabilistic deep learning", "uncertainty": "predictive uncertainty, reliability of confidence estimates",
     "relation": "Uncertainty-aware air-quality forecasting is established; severity-conditioned coverage is the narrower question."},
    {"id": "wang_2018", "authors": "Wang et al.", "year": 2018, "venue": "Applied Soft Computing", "doi": "10.1016/j.asoc.2018.07.030",
     "title": "Application of a novel early warning system based on fuzzy time series in urban air quality forecasting in China",
     "text_status": "TITLE_ONLY", "data_geography": "Chinese cities", "warning": "early-warning system",
     "relation": "Air-quality early-warning systems with ML forecasting are established."},
]

GAPS = [
    ("Station-level correction of CAMS forecasts", "ESTABLISHED", "petetin_2022, bertrand2023, riccio_chianese_2024, casciaro_2022, munteanu_2026, june_2021",
     "Applying it to CPCB-network monitors in Indian cities was not found among the reviewed studies.", "PENDING: no primary CAMS comparison has run (archive at 9/36 files)."),
    ("Correction trained only on forecasts available at issue time (archived operational runs, 20:00 IST contract)", "PARTIALLY ESTABLISHED",
     "petetin_2022 and riccio_chianese_2024 use operational CAMS; munteanu_2026 and sarafian_2025 use reanalysis",
     "An explicit, code-enforced availability contract with a violation count is AirGuard's design.", "Guard implemented; 0 violations in the 18,540-row join; publication times are nominal, not observed."),
    ("Temporal and geographic transfer evaluation (rolling origin, unseen stations and cities)", "ESTABLISHED METHOD",
     "bergmeir2012, roberts2017, meyer2018, garciacrespi2026, riccio_chianese_2024 (held-out stations)",
     "Application to ~100 Indian cities.", "Done for the non-CAMS paper; pending for CAMS."),
    ("Severe AQI treated as lower-bound censored, never as an exact 401", "NOT FOUND",
     "none of the reviewed studies treats the open Severe band as censored", "Possible contribution, narrow.", "Implemented; 383 censored Severe station-days in the measured set; primary CAMS evaluation pending."),
    ("Coverage audited by pollution category (Mondrian / severity-conditioned)", "PARTIALLY ESTABLISHED",
     "romano2019, xu2021, gibbs2021, angelopoulos2024, adjei_2026, murad_2021",
     "Reporting that marginal coverage hides poor coverage in polluted categories, for Indian AQI.", "Exploratory, non-CAMS: 90% intervals covered 57-75% of Severe days (pilot); no guarantee claimed."),
    ("Under-warning versus over-warning trade-off for advisories", "ESTABLISHED CONCEPT",
     "murphy1977 (cost-loss), wang_2018 (early warning), angelopoulos2024 (risk control)",
     "Two-sided warning losses per cohort are AirGuard's framing.", "Exploratory only; no policy is called optimal."),
    ("Immutable forecast ledger and prospective verification", "ESTABLISHED PRACTICE",
     "operational services such as stortini_2020, colette_2025, ghude_2020", "Engineering, not novelty.",
     "Running since 2026-10-11: 108 fixed-time forecasts, 10 verified outcomes; no skill claim."),
    ("Separation of raw, corrected and experimental forecasts in the public product", "ESTABLISHED PRACTICE", "operational services label model output",
     "Engineering and communication, not novelty.", "Live: modelled labels, no deployed correction or interval."),
]

CLAIMS = [
    ("AirGuard forecasts next-day AQI across Indian cities from CAMS-based inputs", "SUPPORTED (as a service)", "live site; docs/DATA_SOURCES.md"),
    ("The forecast is accurate / beats CAMS or persistence", "NOT SUPPORTED", "no primary CAMS experiment; live track record has 3 verified days; 2026 backtest of the 1.0 model did not beat persistence"),
    ("Station-calibrated CAMS correction improves Indian forecasts", "NOT YET TESTED", "CAMS archive 9/36; MODEL_SELECTION_REPORT.md: NOT READY"),
    ("Weather Ridge beats climatology on held-out dates (non-CAMS paper)", "SUPPORTED", "paper snapshot; Strict Ridge MAE 8.96 lower than climatology, 95% block interval [-12.49, -5.61]"),
    ("History Ridge beats persistence", "NOT ESTABLISHED", "PROGRESS.md; MODEL_SELECTION_REPORT.md"),
    ("Intervals are calibrated in polluted categories", "NOT SUPPORTED", "pilot: Severe coverage 57-75% for nominal 90%"),
    ("Any warning policy is optimal", "NOT SUPPORTED", "WARNING_POLICY_EXTENSION_REPORT.md"),
    ("AirGuard is the first / state of the art", "NOT SUPPORTED", "operational CAMS-downstream and Indian early-warning systems exist (this audit)"),
    ("AirGuard improves health outcomes", "NOT SUPPORTED", "no outcome study; HAI is a heuristic, not clinically validated"),
    ("Severe days are handled without inventing exact values", "SUPPORTED (method)", "censoring in src/nationwide/aqi.py and the research metrics"),
]


def main():
    review = json.loads((RES / "literature_fulltext_review.json").read_text(encoding="utf-8"))
    verification = json.loads((RES / "literature_verification.json").read_text(encoding="utf-8"))
    search = json.loads((RES / "literature_search_log.json").read_text(encoding="utf-8"))
    status = {e["key"]: e["status"] for e in verification["entries"]}
    hits = {h["doi"].lower() for q in search["queries"] for h in q["hits"] if h["doi"]}
    for a in SEARCH_ADDITIONS:
        assert a["doi"].lower() in hits, f"{a['id']} must come from the logged search"

    rows = []
    for e in review["entries"]:
        rows.append({"id": e["id"], "authors": e["authors"], "year": e["year"], "title": e["title"], "doi": e.get("doi"),
                     "verification": status.get(e["id"], "NOT_CHECKED"), "text_status": e["text_status"],
                     "data_geography": e.get("geography_data", NA), "methods_task": e.get("task", NA),
                     "evaluation_spatial": e.get("validation_splits", NA), "inputs_availability": e.get("inputs_availability", NA),
                     "uncertainty_warning": e.get("uncertainty_advisory", NA), "relation": e.get("overlap_limits", NA), "origin": "full-text review 2026-10-12"})
    for a in SEARCH_ADDITIONS:
        rows.append({"id": a["id"], "authors": a["authors"], "year": a["year"], "title": a["title"], "doi": a["doi"],
                     "verification": "VERIFIED_DOI (Crossref search record)", "text_status": a["text_status"],
                     "data_geography": a.get("data_geography", NA), "methods_task": a.get("methods", NA),
                     "evaluation_spatial": NA, "inputs_availability": NA,
                     "uncertainty_warning": "; ".join(x for x in (a.get("uncertainty"), a.get("warning"), a.get("extremes")) if x) or NA,
                     "deployment": a.get("deployment", NA), "relation": a["relation"], "origin": "logged Crossref search 2026-10-20"})
    matrix = {"generated_by": "scripts/build_novelty_audit.py", "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "rows": rows, "gaps": [dict(zip(("element", "prior_art_status", "closest", "airguard_distinction", "evidence"), g)) for g in GAPS],
              "claims": [dict(zip(("claim", "status", "evidence"), c)) for c in CLAIMS]}
    OUT_JSON.write_text(json.dumps(matrix, indent=2) + "\n", encoding="utf-8")

    vc = verification["counts"]
    verified = sum(v for k, v in vc.items() if k.startswith("VERIFIED"))
    unique_hits = len(hits)
    cell = lambda s: str(s).replace("|", "/").replace("\n", " ")
    md = [
        "# Final novelty and prior-art audit",
        "",
        f"Generated {matrix['generated_at_utc']} by `scripts/build_novelty_audit.py`. Machine-readable: `results/research/literature_matrix.json`. "
        "This audit supersedes the bounded `NOVELTY_AUDIT.md` and builds on `LITERATURE_FULLTEXT_REVIEW.md`; nothing there is discarded.",
        "",
        "## Verdict",
        "",
        "AirGuard's individual methods are all established: station-level CAMS correction, gradient boosting and ridge models, rolling-origin and spatial "
        "validation, conformal intervals, cost-loss warnings and operational forecast ledgers each have prior art below, and India already runs operational "
        "early-warning systems. **No first-ever or state-of-the-art claim is supported.**",
        "",
        "What was not found among the reviewed studies is the combination: archived operational CAMS forecasts corrected at CPCB-network monitors across about "
        "100 Indian cities, under a code-enforced issue-time contract, judged by temporal and unseen-station transfer, with the open Severe band treated as "
        "censored and with coverage and under-warning reported by pollution category. That combination is a defensible *research design*. It becomes a "
        "*contribution* only when the primary CAMS experiment has run; today it has not (archive 9 of 36 files, no eligible fold).",
        "",
        "## How the literature was checked",
        "",
        f"- **Identifier verification** (`scripts/literature_audit.py verify`, {verification['checked_at_utc']}): {len(verification['entries'])} records "
        f"from the paper bibliography and the full-text review. {verified} verified against Crossref, arXiv or the official landing page; "
        f"{vc.get('URL_REACHABLE', 0)} are official web resources that resolve; {vc.get('NOT_VERIFIED', 0)} could not be machine-verified "
        "(the 2014 CPCB AQI report, whose official PDF URL returns a web page, and Holm 1979, whose JSTOR page blocks automated access). "
        "Both are standard references; they are flagged, not removed, because the paper is a frozen snapshot.",
        f"- **Logged search** (`scripts/literature_audit.py search`, {search['searched_at_utc']}): {len(search['queries'])} fixed queries against Crossref, "
        f"top 20 journal articles from 2018 each, {unique_hits} unique records. Titles were screened for air quality plus a relevant method or region; "
        f"{len(SEARCH_ADDITIONS)} studies were judged relevant and added below at the depth actually read.",
        f"- **Limits**: {search['limitations']}. This is a targeted, reproducible audit, not a systematic review; no independent human has accepted it.",
        "",
        "## Literature matrix",
        "",
        "Design facts are given only where the text was read. \"not established\" means the audit did not read enough to say.",
        "",
        ":::landscape",
        "| Study | Venue / DOI | Read | Data and geography | Method / task | Evaluation, spatial holdout | Inputs at issue time | Uncertainty, extremes, warnings | Relation to AirGuard |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in rows:
        md.append(f"| {cell(r['authors'])} ({r['year']}): {cell(r['title'])[:110]} | {cell(r.get('doi') or 'no DOI')} ({cell(r['verification'])}) | {cell(r['text_status'])} | "
                  f"{cell(r['data_geography'])[:140]} | {cell(r['methods_task'])[:140]} | {cell(r['evaluation_spatial'])[:140]} | {cell(r['inputs_availability'])[:140]} | "
                  f"{cell(r['uncertainty_warning'])[:140]} | {cell(r['relation'])[:200]} |")
    md += [":::", "", "## Gap matrix", "", ":::landscape",
           "| AirGuard element | Prior-art status | Closest studies | What would be AirGuard's | Evidence today |", "| --- | --- | --- | --- | --- |"]
    md += [f"| {g[0]} | {g[1]} | {g[2]} | {g[3]} | {g[4]} |" for g in GAPS]
    md += [":::", "", "## Claim-evidence matrix", "", "| Claim | Status | Evidence |", "| --- | --- | --- |"]
    md += [f"| {c[0]} | **{c[1]}** | {c[2]} |" for c in CLAIMS]
    md += ["", "## What may be said", "",
           "- \"Among the studies reviewed, none evaluated archived operational CAMS forecasts corrected at CPCB-network monitors across Indian cities under an "
           "explicit issue-time contract with censored Severe outcomes.\" (scoped, true today)",
           "- Not: \"first\", \"novel method\", \"state of the art\", \"validated\", \"improves health\", \"guaranteed coverage\".",
           "", "## Remaining actions", "",
           "- Run the primary CAMS experiment when the archive allows an eligible fold; only then can the gap become a contribution.",
           "- Read the full texts of the title-only additions (Ghude 2020, Kalita 2023, June 2021, Lawrence 2025) before citing their designs.",
           "- Independent human acceptance of this audit and of the frozen paper's bibliography.", ""]
    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({"rows": len(rows), "gaps": len(GAPS), "claims": len(CLAIMS)}))


if __name__ == "__main__":
    main()
