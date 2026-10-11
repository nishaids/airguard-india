# PRIOR ART

Initial targeted review is in prior_art.json. CAMS already offers station-optimised machine-learning MOS using observations and forecast weather. Riccio and Chianese (2024) already combine CAMS correction, meteorology, spatial post-processing and probabilistic calibration. CQR and conformal risk control are established methods. India's Delhi EWS already combines chemistry forecasts, observations and fires. The defensible candidate contribution is an evaluated India-specific operational protocol and cohort advisory trade-off, not API aggregation. Full-text extraction and an exhaustive novelty search remain incomplete; literature_review_complete is false. See linked primary sources below.

- [CAMS European air quality forecasts optimised at observation sites](https://ads.atmosphere.copernicus.eu/datasets/cams-europe-air-quality-forecasts-optimised-at-observation-sites?tab=overview) (operational, current): Direct overlap with atmospheric forecast plus observations plus meteorological correction; combination is not novel

- [Technical note: Accurate, reliable, and high-resolution air quality predictions by improving the Copernicus Atmosphere Monitoring Service using a novel statistical post-processing method](https://acp.copernicus.org/articles/24/1673/2024/acp-24-1673-2024.html) (2024): Strong prior art for CAMS correction, spatial post-processing, predictive uncertainty and threshold exceedances

- [Calibrating the CAMS European multi-model air quality forecasts for regional air pollution monitoring](https://arxiv.org/abs/2201.13355) (2022): Forecast bias and dispersion calibration already studied

- [Probing into the wintertime meteorology and particulate matter (PM2.5 and PM10) forecast over Delhi](https://www.sciencedirect.com/science/article/pii/S1309104222001118) (2022): India atmospheric forecasting with meteorology and fires; existing operational comparator

- [Conformalized Quantile Regression](https://arxiv.org/abs/1905.03222) (2019): CQR is an established method; application must evaluate dependence and conditional coverage

- [Conformal Risk Control](https://research.google/pubs/conformal-risk-control/) (2024): Controlling under-warning is related to known risk-control theory; H2 novelty unestablished

- [Online conformal prediction with decaying step sizes](https://proceedings.mlr.press/v235/angelopoulos24a.html) (2024): Dependence-aware calibration research comparator; no implemented claim
