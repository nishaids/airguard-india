# Datasets in one page

Measured: OpenAQ-hosted CPCB-provider station readings, with original upstream identity, times, units and quality flags. Modelled: genuine operational CAMS forecasts from ADS; GFS weather forecasts via Open-Meteo previous runs. Satellite context: NASA FIRMS fire detections, not measured breathing-zone pollutant concentrations. Derived: CPCB-style station AQI, feature summaries, categories and QC decisions.

QC v3.1 rejects exact zeros, flagged/under-covered bins, unsupported units and six-hour stuck sequences. Spikes and PM2.5>PM10 are flagged and kept. Daily targets require >=16 hourly bins per pollutant, >=3 pollutants including particulate, complete CO/O3 eight-hour windows. Current-catalogue survivorship and unknown OpenAQ ingestion times are limitations. Research data are not synthetic; offline fault fixtures are synthetic and labelled tests.


Evidence checkpoint: measured dataset `4761a5da60dde059b1c7bbfc5403e32d26c983f80e3fc22683eba8a13119821d`; preliminary run `287c87db04a6b29459374c4d50637f943c04dfe10d9072d7e296b74ad1d45a3f`; protocol `e24b664747029a7611efcf4fb19b8cfdf8b12762d379927698fa6e98777d67e8`. Primary CAMS development/final/prospective performance must never be inferred from this non-CAMS run. See [claim ledger](CLAIM_EVIDENCE_MATRIX.md) and [results sheet](ONE_PAGE_RESULTS.md).
