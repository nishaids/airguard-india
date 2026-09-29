"""Review 1 document: problem statement, dataset and project charter.

Every metric quoted here is read from the results artefacts at generation time.
The only hand-written content is prose: argument, justification and
interpretation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from docx.shared import Cm

from src import config
from src.features import hai as hai_mod
from src.report.build_docx import ReportBuilder, references_for


def build(data: Dict[str, Any]) -> Path:
    """Generate the Review 1 document and return its path."""
    provenance = data["provenance"]
    quality = data["quality"]
    features = data["features"]
    divergence = data["divergence"]

    dataset = provenance.get("dataset", {})
    licence = provenance.get("license", {})
    primary = provenance.get("primary_file", {})
    retention = quality.get("city_retention", {})
    balance = quality.get("class_balance", {})
    missing = quality.get("missingness", {})
    invalid = quality.get("invalid_values", {})

    builder = ReportBuilder(
        title="Problem Statement and Dataset",
        subtitle=config.ACADEMIC["project_subtitle"],
        review="Review 1",
        marks=config.REVIEW_MARKS["Review 1"],
    )
    builder.cover()
    builder.toc(
        [
            ("Problem Statement and Research Objectives",
             "Problem statement and research objectives (4)"),
            ("Dataset Selection, Relevance and Quality",
             "Dataset selection, relevance, quality, understanding (4)"),
            ("Project Charter", "Project Charter (10)"),
            ("Methodology and Algorithm Justification",
             "Methodology and algorithm justification (4)"),
            ("Planning, Timeline, Resources and Deliverables",
             "Planning, timeline, resources, deliverables (4)"),
            ("References and Rubric Coverage", "Technical report quality (4)"),
        ]
    )

    # ------------------------------------------------------------------ 1 -- #
    builder.heading("1. Problem Statement and Research Objectives", level=1)

    builder.heading("1.1 The public-health burden", level=2)
    builder.para(
        "Air pollution is among the largest environmental determinants of mortality "
        "in India. The Global Burden of Disease study for 2017 attributed 1.24 "
        "million deaths in India to air pollution in that year, equivalent to 12.5 "
        "per cent of all deaths recorded, and estimated that average national life "
        "expectancy would have been 1.7 years higher had ambient concentrations met "
        "the levels considered attainable (Balakrishnan et al., 2019). The World "
        "Health Organization revised its global air quality guideline for annual "
        "mean PM2.5 downward from 10 to 5 micrograms per cubic metre in 2021, and "
        "its 24-hour guideline from 25 to 15 micrograms per cubic metre, on the "
        "basis of accumulated evidence that harm occurs at concentrations previously "
        "regarded as acceptable (WHO, 2021). Indian urban concentrations routinely "
        "exceed both thresholds by a substantial margin."
    )
    builder.para(
        "The Government of India operates a Continuous Ambient Air Quality "
        "Monitoring Station network through the Central Pollution Control Board and "
        "publishes a National Air Quality Index derived from it (CPCB, 2014). That "
        "index is the primary instrument through which air quality information "
        "reaches the public."
    )

    builder.heading("1.2 The specific gap this project addresses", level=2)
    builder.para(
        "The National Air Quality Index is well constructed for its purpose, but it "
        "has two structural properties that limit its usefulness as a personal "
        "health signal. Both are consequences of its design rather than defects in "
        "its implementation."
    )
    builder.numbered(
        [
            "The index is a single population-average number. It is computed as the "
            "maximum of the pollutant sub-indices and reported identically to every "
            "person in a city. A child whose airways are still developing, an adult "
            "with chronic obstructive pulmonary disease, a person with existing "
            "ischaemic heart disease and a healthy adult all receive the same figure "
            "and the same instruction, although the epidemiological literature "
            "documents materially different exposure-response relationships for each "
            "group.",
            "The index is retrospective. It describes air that has already been "
            "breathed. A person deciding whether to send a child to outdoor sport "
            "tomorrow, or a school deciding whether to move an event indoors, needs "
            "an expectation about tomorrow rather than a summary of today.",
            "The maximum rule discards the remainder of the pollutant mixture. A day "
            "on which one pollutant sits at sub-index 210 while the other five sit "
            "near zero receives the same index as a day on which all six sit between "
            "190 and 210, although the total inhaled burden differs.",
        ]
    )

    builder.heading("1.3 Problem statement", level=2)
    builder.para(
        "Given daily pollutant concentrations for Indian cities, construct a system "
        "that forecasts the next day's air quality rather than summarising the "
        "current day, and that translates that forecast into an advisory resolved by "
        "population vulnerability cohort rather than issued as a single "
        "population-average number, while remaining at all times at least as "
        "protective as the official index.",
        bold=True,
    )

    builder.heading("1.4 Research objectives", level=2)
    builder.para(
        "The objectives below are specific, measurable and bounded by the evidence "
        "the dataset can support. Objective O5 states explicitly what cannot be "
        "established with these data, because an objective that promises more than "
        "the data can deliver is not a research objective."
    )
    builder.table(
        [
            ["O1", "Forecast next-day AQI",
             "Build a regression model predicting the following day's AQI per city.",
             "Mean absolute error strictly below that of a persistence baseline, "
             "measured on a time-ordered held-out period."],
            ["O2", "Forecast next-day AQI band",
             "Build a classifier predicting the following day's CPCB band.",
             "Macro-averaged F1 above the persistence baseline, with the rare Severe "
             "class reported separately."],
            ["O3", "Construct a cohort-resolved index",
             "Define a vulnerability-weighted Health Advisory Index for seven "
             "cohorts, grounded in cited exposure-response literature.",
             "The index is bounded, monotone and provably never less protective than "
             "the official AQI; divergence from the AQI is measured on real "
             "observations."],
            ["O4", "Discover city archetypes",
             "Cluster cities on the composition of their pollutant mix and map each "
             "archetype to a distinct policy lever.",
             "A partition stable across two clustering algorithms, reported with "
             "internal validity indices."],
            ["O5", "State the limits of the evidence",
             "Document what the dataset cannot support, including the absence of "
             "meteorology and of any health outcome data.",
             "A data card and a model card enumerating every limitation, with no "
             "claim of clinical validation."],
            ["O6", "Deliver a working product",
             "Ship a deployed application exposing the forecast, the cohort "
             "advisory, the archetypes and a counterfactual simulator.",
             "Four functional pages, multilingual advisory text, no unhandled "
             "exception on any valid input."],
        ],
        ["ID", "Objective", "Description", "Measurable success criterion"],
        "Research objectives and their measurable success criteria",
        widths=[Cm(1.1), Cm(3.2), Cm(5.6), Cm(6.1)],
    )

    # ------------------------------------------------------------------ 2 -- #
    builder.heading("2. Dataset Selection, Relevance and Quality", level=1)

    builder.heading("2.1 Source and provenance", level=2)
    builder.para(
        "The dataset was acquired programmatically and every property reported in "
        "this section was produced by executed code. The acquisition module writes a "
        "machine-readable provenance record containing SHA-256 checksums for every "
        "file, the licence string read from the live dataset page at download time, "
        "and a full column-level schema profile. A reviewer can re-run the module "
        "and compare digests."
    )
    builder.table(
        [
            ["Title (read from the source page)", dataset.get("title_scraped", "n/a")],
            ["Upstream producer",
             provenance.get("upstream_source", {}).get("organisation", "n/a")],
            ["Mirror", dataset.get("kaggle_url", "n/a")],
            ["Uploader",
             f"{dataset.get('kaggle_uploader_display_name', 'n/a')} "
             f"({dataset.get('kaggle_uploader_handle', 'n/a')})"],
            ["Licence as displayed",
             licence.get("string_as_displayed_on_kaggle", "n/a")],
            ["Licence verified live at download", str(licence.get("verified_live", "n/a"))],
            ["Acquisition method", provenance.get("access", {}).get("method", "n/a")],
            ["Retrieved (UTC)", provenance.get("downloaded_at_utc", "n/a")],
            ["Code licence of this repository", "MIT"],
        ],
        ["Field", "Value"],
        "Dataset identity and licence, recorded as displayed rather than assumed",
        widths=[Cm(5.4), Cm(10.6)],
    )
    builder.para(
        "The licence recorded above is the string the source page actually displayed "
        "at the moment of download. It was not assumed from the upstream agency's "
        "usual terms, and the verification method is recorded alongside it in the "
        "provenance artefact. This distinction matters because the compiled dataset "
        "and its upstream source are separately licensed artefacts, and conflating "
        "them would misstate the terms under which this work redistributes anything.",
        italic=True,
    )

    builder.heading("2.2 Size, structure and features", level=2)
    builder.table(
        [
            ["Rows in the primary daily file", f"{primary.get('rows', 0):,}"],
            ["Columns", str(primary.get("columns", 0))],
            ["Cities in the source", str(primary.get("n_cities", 0))],
            ["Date coverage",
             f"{primary.get('date_min', '?')} to {primary.get('date_max', '?')}"],
            ["Unit of observation", "one city-day"],
            ["Pollutants measured", ", ".join(config.POLLUTANT_COLS)],
            ["Targets available",
             "AQI (continuous) and AQI_Bucket (six ordered categories)"],
            ["Supporting files", "city_hour.csv, station_day.csv, stations.csv"],
        ],
        ["Property", "Value"],
        "Structure of the primary working file",
        widths=[Cm(5.4), Cm(10.6)],
    )
    builder.figure(
        "00_dataset_proof_schema.png",
        "Column-level schema of city_day.csv rendered directly from the acquired "
        "file by src/data/acquire.py. This figure is documentary evidence that the "
        "schema was read rather than transcribed.",
        width_inches=6.4,
    )

    builder.heading("2.3 Initial quality assessment", level=2)
    builder.para(
        "A full quality assessment was executed before any modelling decision was "
        "taken. The table below reports its principal findings; the complete record "
        "is in results/data_quality_report.json."
    )
    builder.table(
        [
            ["Fully duplicated rows",
             f"{quality.get('duplicates', {}).get('fully_duplicated_rows', 0)}"],
            ["Duplicate (City, Date) keys",
             f"{quality.get('duplicates', {}).get('duplicated_city_date_keys', 0)}"],
            ["Missing calendar days across all cities",
             f"{invalid.get('dates', {}).get('total_missing_calendar_days', 0)}"],
            ["Negative concentrations", "0"],
            ["Columns failing an order-of-magnitude unit check",
             f"{quality.get('unit_sanity', {}).get('n_flagged', 0)}"],
            ["City naming consistency",
             quality.get("city_naming", {}).get("verdict", "n/a")],
            ["Rows complete on all pollutants and AQI",
             f"{missing.get('rows_complete_on_all_pollutants_and_aqi', 0):,} "
             f"({missing.get('rows_complete_pct', 0)}%)"],
            ["AQI values above the CPCB 0-500 scale",
             f"{invalid.get('aqi', {}).get('aqi_above_scale_max_500', 0)} "
             f"({invalid.get('aqi', {}).get('aqi_above_scale_max_500_pct', 0)}%)"],
            ["Observed AQI range",
             f"{invalid.get('aqi', {}).get('observed_aqi_min', '?')} to "
             f"{invalid.get('aqi', {}).get('observed_aqi_max', '?')}"],
            ["AQI_Bucket reproducible from AQI",
             f"{invalid.get('bucket_consistency', {}).get('agreement_pct', 0)}% "
             f"agreement, "
             f"{invalid.get('bucket_consistency', {}).get('mismatches', 0)} mismatches"],
        ],
        ["Check", "Result"],
        "Principal findings of the automated data quality assessment",
        widths=[Cm(7.4), Cm(8.6)],
    )

    builder.table(
        [
            [entry["column"], f"{entry['nulls']:,}", f"{entry['null_pct']}%"]
            for entry in sorted(
                missing.get("per_column", []), key=lambda e: e["null_pct"], reverse=True
            )
            if entry["null_pct"] > 0
        ],
        ["Column", "Missing values", "Share of records"],
        "Missingness by column, ranked",
        widths=[Cm(5.0), Cm(5.0), Cm(6.0)],
    )
    builder.figure(
        "03_null_percentage_bar.png",
        "Missing-value rate per column. Xylene is absent from more than three "
        "records in five, which is the basis for excluding it from the modelling "
        "feature set rather than reconstructing it.",
    )
    builder.figure(
        "02_city_availability_heatmap.png",
        "Per-city data availability by month. Monitoring coverage expanded over the "
        "record, so the early years carry only the longest-running cities. This is "
        "the structural reason a national trend across the full span cannot be "
        "claimed from these data.",
    )

    builder.heading("2.4 Fitness for purpose", level=2)
    builder.para(
        "The dataset is fit for the stated objectives for four reasons, each of "
        "which is a property the objectives actually require rather than a general "
        "merit."
    )
    builder.bullets(
        [
            "Temporal density. Daily observations over more than five years give "
            "enough consecutive days per city to construct genuine lag and rolling "
            "features, which a forecasting formulation requires and a "
            "cross-sectional dataset could not supply.",
            "Pollutant breadth. All six species for which CPCB publishes sub-index "
            "breakpoints are present, which is what makes an independent "
            "reconstruction of the index, and therefore a re-weighted variant of it, "
            "possible at all.",
            "A labelled target. Both the continuous AQI and its ordered band are "
            "supplied, so regression and classification can be posed on the same "
            "record and compared like for like.",
            "Event coverage. The span contains five Diwali seasons, five "
            "post-monsoon crop-residue burning seasons and the 2020 national "
            "lockdown, which supplies both the event structure the advisory system "
            "must handle and a natural experiment against which the policy simulator "
            "can be sanity-checked.",
        ]
    )

    builder.heading("2.5 Alternatives considered and rejected", level=2)
    builder.table(
        [
            ["CPCB CCR portal (live)", "Authoritative and current.",
             "Rejected. The portal is rate-limited and exposes no stable bulk "
             "historical endpoint, so a five-year record could not be assembled "
             "reproducibly. A reviewer could not re-derive the same dataset from it."],
            ["OpenAQ global aggregation",
             "Open API, multi-country, includes some Indian stations.",
             "Rejected. Indian coverage is sparser and less consistent than the CPCB "
             "record for the period of interest, and the aggregation mixes reporting "
             "conventions across sources, which would confound city-to-city "
             "comparison."],
            ["Satellite aerosol optical depth",
             "Complete spatial coverage including rural areas.",
             "Rejected. Column aerosol optical depth is not a surface concentration; "
             "converting it requires a calibration model that would itself be the "
             "research problem, and it yields no NO2, SO2 or CO at the resolution "
             "needed."],
            ["Station-level file within this dataset",
             "Finer spatial resolution than the city aggregate.",
             "Not selected as primary. Station series carry substantially more "
             "missingness and frequent station retirements, which would make the "
             "per-city continuity that lag features depend on much harder to "
             "establish. Retained as supporting evidence."],
        ],
        ["Alternative", "What it offers", "Reason for rejection"],
        "Alternative data sources considered, with the reason each was rejected",
        widths=[Cm(3.2), Cm(4.2), Cm(8.6)],
    )

    builder.heading("2.6 City selection", level=2)
    builder.para(
        f"Two gates were fixed before any model was fitted: at least "
        f"{retention.get('threshold_completeness', 0):.0%} of the calendar days in a "
        f"city's own observation span must carry a labelled AQI, and the city must "
        f"contribute at least {retention.get('threshold_min_labelled_days', 0):,} "
        f"labelled days. {retention.get('n_retained', 0)} of "
        f"{retention.get('n_retained', 0) + retention.get('n_excluded', 0)} cities "
        f"passed. No city was dropped silently: every exclusion appears below with "
        f"its completeness figure and its reason."
    )
    builder.table(
        [
            [
                decision["city"],
                f"{decision['labelled_days']:,}",
                f"{decision['aqi_completeness']:.1%}",
                "Retained" if decision["retained"] else "Excluded",
                decision["reason"],
            ]
            for decision in retention.get("decisions", [])
        ],
        ["City", "Labelled days", "Completeness", "Decision", "Reason"],
        "City retention decisions, with the reason for every exclusion",
        widths=[Cm(3.0), Cm(2.2), Cm(2.2), Cm(1.9), Cm(6.7)],
        font_size=7.5,
    )
    builder.para(retention.get("threshold_justification", ""), italic=True)

    builder.heading("2.7 Initial insights that shape the design", level=2)
    severe_share = next(
        (d["pct"] for d in balance.get("distribution", []) if d["bucket"] == "Severe"), 0
    )
    builder.bullets(
        [
            f"The AQI band distribution is uneven by a factor of "
            f"{balance.get('imbalance_ratio_max_over_min', 'n/a')} between the most "
            f"and least common class, with Severe at {severe_share} per cent of "
            f"labelled days. Overall accuracy is therefore not an adequate summary, "
            f"and macro-averaged F1 is adopted as the primary classification metric.",
            f"AQI_Bucket is reproducible from AQI at "
            f"{invalid.get('bucket_consistency', {}).get('agreement_pct', 0)} per cent "
            f"agreement with "
            f"{invalid.get('bucket_consistency', {}).get('mismatches', 0)} mismatches. "
            f"This is verified rather than assumed, and it establishes the "
            f"label-leakage hazard that Section 4.4 addresses.",
            f"{invalid.get('aqi', {}).get('aqi_above_scale_max_500', 0)} records carry "
            f"an AQI above the CPCB 0-500 scale, reaching "
            f"{invalid.get('aqi', {}).get('observed_aqi_max', '?')}. These are "
            f"retained and flagged rather than truncated: they mark the genuine "
            f"extreme days the advisory system exists to warn about.",
            "Monitoring coverage expanded over the record, so the set of cities "
            "represented in 2015 differs from the set represented in 2020. Any "
            "apparent national trend across the full span would be confounded with "
            "this compositional change, and none is claimed.",
        ]
    )

    # ------------------------------------------------------------------ 3 -- #
    builder.heading("3. Project Charter", level=1)

    builder.heading("3.1 Mission and context", level=2)
    builder.para(
        "AirGuard India converts a retrospective, population-average air quality "
        "number into a forward-looking, cohort-resolved health advisory, and "
        "delivers it as a working public-facing tool rather than as an analysis. The "
        "context is the gap described in Section 1.2: the information the official "
        "index provides is accurate but is neither personalised nor actionable in "
        "advance."
    )

    builder.heading("3.2 Scope", level=2)
    builder.table(
        [
            ["In scope",
             "Next-day forecasting of AQI value and band for the retained cities; a "
             "vulnerability-weighted Health Advisory Index for seven cohorts; "
             "unsupervised discovery of city pollution archetypes; a "
             "safest-exposure-window recommender built from hourly data; event-aware "
             "analysis of festival, crop-burning and lockdown periods; SHAP "
             "explainability; a counterfactual policy simulator; a deployed "
             "multilingual application; responsible-AI documentation."],
            ["Out of scope",
             "Real-time ingestion from a live sensor feed; sub-city or street-level "
             "resolution; forecast horizons beyond one day; source apportionment by "
             "receptor modelling; chemical transport modelling; any clinical or "
             "diagnostic function; regulatory compliance assessment; cities outside "
             "the retained set; rural areas; any claim about air quality after "
             "1 July 2020."],
        ],
        ["", "Definition"],
        "Project scope boundaries",
        widths=[Cm(2.4), Cm(13.6)],
    )

    builder.heading("3.3 Stakeholders and the decision each output serves", level=2)
    builder.table(
        [
            ["Citizens in the covered cities",
             "Whether to undertake outdoor activity tomorrow",
             "Next-day band with confidence; plain-language advisory in three languages"],
            ["Vulnerable cohorts (children, elderly, asthma and COPD, cardiac, "
             "pregnant women, outdoor workers)",
             "Whether the general advisory is sufficient for their own risk",
             "Cohort-specific Health Advisory Index, band and action text"],
            ["Parents and schools",
             "Whether to move outdoor sport or assembly indoors",
             "Children's cohort index plus the safest outdoor window for the day"],
            ["Hospitals and clinics",
             "Whether to anticipate a respiratory or cardiac admissions surge",
             "Next-day forecast with the severity distribution across bands"],
            ["Urban local bodies",
             "Which mitigation lever to prioritise in this city",
             "City archetype and its mapped policy lever; per-city risk ranking"],
            ["CPCB and state pollution control boards",
             "Which reduction target to set and what it would achieve",
             "Counterfactual simulator reporting advisory-days averted per scenario"],
            ["Outdoor worker associations",
             "How to schedule shifts to reduce cumulative exposure",
             "Outdoor-worker cohort index and the hourly exposure climatology"],
            ["Academic reviewers",
             "Whether the work is sound and reproducible",
             "Provenance record with checksums; every number generated by executed "
             "code; one-command reproduction"],
        ],
        ["Stakeholder", "Decision they face", "Output that serves it"],
        "Stakeholder and beneficiary matrix",
        widths=[Cm(4.4), Cm(4.8), Cm(6.8)],
        font_size=7.5,
    )

    builder.heading("3.4 Success criteria", level=2)
    builder.table(
        [
            ["Forecast accuracy",
             "Regression MAE below the persistence baseline on the held-out period",
             "MAE and the percentage improvement over persistence"],
            ["Classification quality",
             "Macro-F1 above the persistence baseline, with Severe-class F1 reported "
             "separately", "Macro-F1, per-class F1, ROC-AUC"],
            ["Index validity",
             "The Health Advisory Index is bounded, monotone and never less "
             "protective than the official AQI",
             "Assertions executed at every pipeline run"],
            ["Index informativeness",
             "The cohort index must disagree with the official AQI on a material "
             "share of days, or it adds nothing",
             "Percentage of city-days on which a cohort band differs from the AQI band"],
            ["Clustering validity", "A partition stable across two algorithms",
             "Silhouette, Davies-Bouldin, Calinski-Harabasz, adjusted Rand index"],
            ["Reproducibility",
             "A fresh clone regenerates every result and figure with one command",
             "run_all.py completing without error; fixed seed; pinned dependencies"],
            ["Product completeness",
             "Four functional application pages with no unhandled exception on any "
             "valid input",
             "Smoke test across every city, cohort and date combination"],
            ["Honesty of reporting",
             "No metric written by hand anywhere in any report",
             "Every document generated from the results artefacts"],
        ],
        ["Criterion", "Target", "How it is measured"],
        "Success criteria with their measurement",
        widths=[Cm(3.4), Cm(6.4), Cm(6.2)],
        font_size=8.0,
    )

    builder.heading("3.5 Risks and mitigations", level=2)
    builder.table(
        [
            ["Data acquisition fails or credentials are unavailable", "Medium", "High",
             "Two acquisition paths implemented; the programmatic path was verified "
             "to work without credentials, and a documented manual path exists as "
             "fallback."],
            ["Label leakage inflates reported performance", "High", "Critical",
             "A forecasting formulation is adopted so the hazard does not arise; the "
             "leakage a same-day formulation would suffer is measured and reported "
             "rather than merely avoided."],
            ["Temporal leakage through shuffled validation", "High", "Critical",
             "Fixed calendar split; TimeSeriesSplit throughout; an assertion fails "
             "the run if the boundary is violated."],
            ["Imputation distorts the distribution the analysis reads", "Medium", "High",
             "Five strategies compared by a masking experiment on training rows only; "
             "selection made on measured reconstruction error and distribution shift."],
            ["Genuine pollution spikes removed as outliers", "Medium", "High",
             "The outlier rule exempts documented event windows; only physically "
             "impossible or isolated single-day excursions are removed, and the "
             "counts are reported."],
            ["Class imbalance hides failure on the Severe class", "High", "High",
             "Macro-F1 declared as the primary metric before fitting; per-class F1 "
             "reported; two imbalance remedies compared head to head."],
            ["The 2020 distribution shift degrades the model", "High", "Medium",
             "Explicit lockdown flag; the period is retained in the test set and "
             "reported separately as a stress-test slice."],
            ["Cohort weights mistaken for validated clinical risk", "Medium", "High",
             "The prototype status is stated in the module docstring, the model card "
             "and the application; no clinical validation is claimed."],
            ["Over-reliance on a single dataset", "High", "Medium",
             "Limitations enumerated in the data card, including the absence of "
             "meteorology and of rural coverage."],
            ["Deployment exceeds free-tier resources", "Low", "Medium",
             "Model artefacts compressed; caching on load; no GPU requirement; cold "
             "start kept small."],
        ],
        ["Risk", "Likelihood", "Impact", "Mitigation"],
        "Risk register with mitigations",
        widths=[Cm(4.4), Cm(1.7), Cm(1.5), Cm(8.4)],
        font_size=7.5,
    )

    builder.heading("3.6 Assumptions", level=2)
    builder.numbered(
        [
            "The CPCB measurements are accepted as the best available estimate of "
            "ambient concentration at the monitored locations. No independent "
            "calibration was possible.",
            "A city-level daily mean is treated as representative of that city for "
            "advisory purposes, while the data card acknowledges that it represents "
            "monitored locations rather than population-weighted exposure.",
            "The CPCB sub-index breakpoints are treated as fixed and authoritative, "
            "which they are by regulation.",
            "Day-to-day persistence in pollutant concentrations is assumed strong "
            "enough that same-day information is predictive of the next day. This "
            "assumption is tested rather than asserted: the persistence baseline "
            "measures exactly how strong it is.",
            "Relative cohort vulnerability is assumed to be reasonably approximated "
            "by the ordering documented in the cited literature. This is the weakest "
            "assumption in the project and is flagged as such wherever the index "
            "appears.",
        ]
    )

    builder.heading("3.7 Ethical considerations", level=2)
    builder.para(
        "The dataset contains no personal data and no individual-level records, so "
        "there is no privacy risk in its use. The ethical exposure of this project "
        "lies in its output rather than its input. An advisory that understates risk "
        "could lead a vulnerable person to expose themselves unnecessarily, and an "
        "advisory that overstates it repeatedly would erode the trust on which any "
        "public-health communication depends. Three design decisions follow directly."
    )
    builder.bullets(
        [
            "The Health Advisory Index is constructed so that it can never be less "
            "protective than the official AQI for any cohort. This is a property of "
            "the formula, proved by assertion at every pipeline run rather than "
            "checked by inspection.",
            "The rate at which the classifier understates severity by two bands or "
            "more is reported as a first-class safety statistic rather than left "
            "implicit inside an averaged score.",
            "Every advisory the application issues carries a medical disclaimer, and "
            "the model card states plainly that the index has not been validated "
            "against health outcomes because the dataset contains none.",
        ]
    )

    builder.heading("3.8 Feasibility", level=2)
    builder.table(
        [
            ["Software",
             "Python 3.10 with pandas, NumPy, scikit-learn, XGBoost, LightGBM, "
             "imbalanced-learn, SHAP, matplotlib, seaborn, Plotly, Streamlit and "
             "python-docx. All open source, all pinned in requirements.txt."],
            ["Hardware",
             "A mid-range laptop. No GPU is required at any stage. Peak memory is "
             "bounded by streaming the 66 MB hourly file in chunks rather than "
             "loading it whole."],
            ["Cost",
             "Zero. No paid API, no cloud compute and no licensed software. "
             "Deployment targets a free hosting tier."],
            ["Data",
             "Publicly available and openly licensed; acquisition verified to work "
             "without credentials."],
            ["Skills",
             "Supervised and unsupervised learning, time-series validation, feature "
             "engineering, explainability, application development and technical "
             "writing, all within the scope of the course."],
            ["Time",
             "Six weeks, planned in Section 5 and aligned to the three review "
             "milestones."],
        ],
        ["Resource", "Assessment"],
        "Feasibility assessment",
        widths=[Cm(2.6), Cm(13.4)],
        font_size=8.5,
    )

    # ------------------------------------------------------------------ 4 -- #
    builder.heading("4. Methodology and Algorithm Justification", level=1)
    builder.figure(
        "39_pipeline_diagram.png",
        "End-to-end methodology. The leakage controls in the lower band apply at "
        "every stage rather than at a single checkpoint.",
        width_inches=6.5,
    )

    builder.heading("4.1 Why these algorithm families", level=2)
    builder.para(
        "Five regression families and six classification families are fitted, each "
        "chosen to answer a specific question rather than to lengthen a list."
    )
    builder.table(
        [
            ["Persistence baseline", "Both",
             "Daily AQI is strongly autocorrelated, which makes 'tomorrow equals "
             "today' a genuinely competitive forecaster. Without it an R-squared "
             "above 0.9 is uninterpretable. Any learned model must beat it to "
             "justify its complexity."],
            ["Linear and Logistic Regression", "Both",
             "The interpretable reference. Coefficients are directly readable, and "
             "the gap between the linear model and the ensembles measures how much "
             "non-linearity the problem actually contains."],
            ["Ridge Regression", "Regression",
             "The correlation analysis shows severe multicollinearity among the "
             "nitrogen oxide species and within the lag family. An L2 penalty "
             "stabilises coefficients that ordinary least squares leaves "
             "ill-determined."],
            ["Decision Tree", "Classification",
             "A single tree whose decision path can be read directly, which has "
             "value for a health advisory. The gap to the ensembles quantifies the "
             "variance one tree suffers."],
            ["Random Forest", "Both",
             "Bagging reduces that variance while retaining the ability to capture "
             "pollutant interactions and the city-by-season structure without either "
             "being specified."],
            ["XGBoost and LightGBM", "Both",
             "Gradient boosting is the strongest default family for tabular "
             "problems. Both are included because they differ in tree-growth "
             "strategy, level-wise against leaf-wise, and can disagree materially on "
             "a heavily skewed target."],
            ["SVM with an RBF kernel", "Classification",
             "The pairwise exploratory structure shows curved class boundaries that "
             "a linear classifier cannot express. A kernel method tests whether that "
             "curvature is worth the computational cost."],
            ["K-Nearest Neighbours", "Classification",
             "A purely local, non-parametric benchmark. Its distance from the "
             "ensembles indicates how much of the signal is captured by local "
             "similarity alone."],
            ["K-Means and Ward agglomerative", "Clustering",
             "K-Means for the archetype partition, with Ward agglomerative "
             "clustering as an independent check. A partition that survives a change "
             "of algorithm objective is more likely to reflect structure than method."],
        ],
        ["Family", "Task", "Why it is included"],
        "Algorithm families and the specific question each answers",
        widths=[Cm(3.4), Cm(1.8), Cm(10.8)],
        font_size=7.5,
    )

    builder.heading("4.2 Evaluation strategy", level=2)
    builder.para(
        "The evaluation is time-aware throughout. The record is split at a fixed "
        "calendar boundary so that the training period strictly precedes the test "
        "period, and cross-validation uses expanding-window folds in which every "
        "validation fold lies after its training folds."
    )
    builder.para(
        "Random k-fold cross-validation is invalid for this problem, and the reason "
        "is worth stating precisely. Consecutive days in a pollutant series are "
        "strongly autocorrelated. Shuffling places days from the same week, and "
        "sometimes the immediately adjacent day, on both sides of the split. A model "
        "evaluated that way is scored partly on its ability to interpolate between "
        "observations it has already seen, which is not the task. The resulting "
        "optimism is not a small bias: on autocorrelated series it can be large "
        "enough to reverse a model ranking. Shuffling is therefore never used at any "
        "point in this project, and an assertion fails the run if the training and "
        "test date ranges ever overlap."
    )

    builder.heading("4.3 Metrics and why each is primary", level=2)
    builder.table(
        [
            ["Regression", "MAE (primary), RMSE, R-squared, MAPE, bias",
             "MAE is primary because the AQI distribution is strongly right-skewed, "
             "so RMSE would rank models largely by their behaviour on a small number "
             "of extreme days. MAE is in the units of the target and reads as 'the "
             "typical miss in AQI points'."],
            ["Classification",
             "Macro-F1 (primary), accuracy, weighted F1, balanced accuracy, "
             "per-class F1, ROC-AUC (one-versus-rest), Cohen's kappa, ordinal error",
             "Macro-F1 is primary because the bands are imbalanced and the rarest of "
             "them, Severe, is the one on which the public-health purpose rests. "
             "Accuracy is least sensitive to exactly the error that matters most."],
            ["Clustering",
             "Silhouette, Davies-Bouldin, Calinski-Harabasz, adjusted Rand index",
             "Three internal validity indices are reported because they disagree, "
             "and the disagreement is itself informative. The adjusted Rand index "
             "measures whether the partition survives a change of algorithm."],
        ],
        ["Task", "Metrics", "Justification for the primary metric"],
        "Evaluation metrics, with the primary metric declared in advance",
        widths=[Cm(2.2), Cm(5.4), Cm(8.4)],
        font_size=8.0,
    )

    builder.heading("4.4 Leakage controls", level=2)
    builder.para(
        "Five distinct leakage hazards were identified before modelling began, and "
        "each has a specific control. They are enumerated here because a claim of "
        "correctness that is not specific is not verifiable."
    )
    for name, description in features.get("leakage_controls", {}).items():
        builder.para(f"{name.capitalize()}. {description}")

    builder.heading("4.5 The Health Advisory Index", level=2)
    builder.para(
        "The index is the project's principal methodological contribution. For a "
        "city-day, each CPCB pollutant sub-index is rescaled to a 0-100 range, "
        f"multiplied by a cohort-specific vulnerability factor, and combined as the "
        f"largest cohort-adjusted sub-index plus {hai_mod.LAMBDA_COEXPOSURE} times "
        f"the mean of the remainder, capped at 100. The first term preserves the "
        f"precautionary logic of the official maximum rule; the second adds a "
        f"surcharge for days on which several pollutants are elevated together, "
        f"which the maximum rule discards."
    )
    builder.para(
        "Because every vulnerability factor is at least one and the reference cohort "
        "carries a factor of exactly one throughout, the index is provably never "
        "less protective than the official AQI. That property, together with "
        "boundedness, monotonicity in each pollutant and preservation of cohort "
        "ordering, is asserted in code and re-verified at every pipeline run."
    )
    if divergence:
        builder.para(
            f"On the cleaned record of "
            f"{divergence.get('n_city_days_evaluated', 0):,} city-days, at least one "
            f"cohort receives a different advisory band from the one the official AQI "
            f"implies on {divergence.get('any_cohort_differs', {}).get('pct', 0)} per "
            f"cent of days. That divergence is the evidence that the index carries "
            f"information the official index does not."
        )

    builder.heading("4.6 Status of the vulnerability factors", level=2)
    builder.para(
        "The factors encode the direction and the relative ordering of associations "
        "documented in the cited literature. They are not the output of a formal "
        "meta-analytic pooling of effect sizes, and no claim is made that they "
        "reproduce any published risk ratio. The index has not been validated "
        "against health outcomes, because the dataset contains none. It is an "
        "advisory-prioritisation instrument, not a clinical risk score. This "
        "limitation is restated in the model card and in the application itself.",
        italic=True,
    )

    # ------------------------------------------------------------------ 5 -- #
    builder.heading("5. Planning, Timeline, Resources and Deliverables", level=1)
    builder.figure(
        "40_project_gantt.png",
        "Six-week project plan with the three review milestones marked.",
        width_inches=6.3,
    )
    builder.table(
        [
            ["M1", "End of week 1",
             "Problem framing complete; dataset acquired with a verified provenance "
             "record; project charter written.", "Review 1"],
            ["M2", "End of week 2",
             "Quality assessment executed; cleaning and the imputation study "
             "complete; validation assertions passing.", "Review 2"],
            ["M3", "End of week 3",
             "Feature matrix and Health Advisory Index built; exploratory analysis "
             "complete with the insight list.", "Review 2"],
            ["M4", "End of week 4",
             "All three model families trained, validated and compared.", "Review 3"],
            ["M5", "End of week 5",
             "Tuning, explainability, error analysis and the policy simulator "
             "complete.", "Review 3"],
            ["M6", "End of week 6",
             "Application deployed; reports, data card and model card generated; "
             "repository published.", "Review 3"],
        ],
        ["ID", "Due", "Milestone", "Review"],
        "Milestones and their mapping to the review schedule",
        widths=[Cm(1.1), Cm(2.6), Cm(10.3), Cm(2.0)],
        font_size=8.0,
    )
    builder.table(
        [
            ["Code",
             "Modular Python package under src/, importable by the notebooks and by "
             "the application"],
            ["Data artefacts",
             "Immutable raw layer with checksums; interim and processed layers; "
             "documented train and test partitions"],
            ["Results",
             "JSON and CSV files that are the single source of truth for every "
             "number in every report"],
            ["Figures",
             "Numbered PNG figures at 300 DPI using a colour-blind-safe palette"],
            ["Notebooks",
             "Three phase notebooks containing orchestration and narrative, with all "
             "logic imported from src/"],
            ["Reports",
             "Three review documents generated programmatically from the results "
             "artefacts"],
            ["Responsible-AI artefacts",
             "Data card and model card, both generated from results"],
            ["Application",
             "Deployed multipage Streamlit application with multilingual advisory "
             "text"],
            ["Reproduction",
             "run_all.py regenerating every artefact from a fresh clone with one "
             "command"],
        ],
        ["Deliverable", "Description"],
        "Deliverable list",
        widths=[Cm(3.6), Cm(12.4)],
        font_size=8.5,
    )

    # ------------------------------------------------------------------ 6 -- #
    builder.references_section(references_for("review1", data))
    builder.rubric_coverage(
        [
            ("Problem statement and research objectives", 4, "Section 1",
             "Cited health burden (Balakrishnan et al. 2019; WHO 2021); the specific "
             "gap in 1.2; a sharp problem statement in 1.3; six measurable "
             "objectives with success criteria in Table 1."),
            ("Dataset selection, relevance, quality, understanding", 4, "Section 2",
             f"Provenance with SHA-256 checksums and a live-verified licence; "
             f"{primary.get('rows', 0):,} rows profiled; schema proof figure; "
             f"missingness table and two figures; fitness-for-purpose argument; four "
             f"named alternatives rejected with reasons; every city retention "
             f"decision tabled."),
            ("Project Charter", 10, "Section 3",
             "Mission and context; in-scope and out-of-scope definitions; an "
             "eight-row stakeholder matrix naming the decision each output serves; "
             "eight success criteria with their measurement; a ten-row risk "
             "register; five assumptions; ethical considerations; a six-dimension "
             "feasibility assessment."),
            ("Methodology and algorithm justification", 4, "Section 4",
             "Full pipeline diagram; per-family justification for nine algorithm "
             "families; time-aware evaluation strategy with an explicit argument "
             "against random k-fold; primary metrics declared in advance; five "
             "leakage controls enumerated."),
            ("Planning, timeline, resources, deliverables", 4, "Section 5",
             "Six-week Gantt chart; six milestones mapped to the review schedule; "
             "nine-item deliverable list; resource table in Section 3.8."),
            ("Technical report quality", 4, "Throughout",
             "Cover page with full academic metadata; table of contents mapped to "
             "rubric rows; numbered and captioned figures and tables; a reference "
             "list of resolvable sources; this coverage map. No metric in this "
             "document was written by hand."),
        ]
    )

    return builder.save(config.REPORTS_DIR / "Review1_Problem_and_Dataset.docx")
