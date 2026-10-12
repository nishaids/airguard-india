# Fair competitor comparison

Unknown means not audited, not absent. No commercial competitor ranking is claimed. Sources: [CPCB](https://airquality.cpcb.gov.in/AQI_India/), [OpenAQ](https://docs.openaq.org/), [CAMS](https://ads.atmosphere.copernicus.eu/datasets/cams-global-atmospheric-composition-forecasts), and the project’s primary-source literature matrix.

| System | Primary function | Measured data? | Forecast? | Indian AQI? | Station calibration? | Uncertainty? | Vulnerability advisory? | Temporal validation? | Spatial validation? | AirGuard difference |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CPCB portal | Official monitoring/index reporting | Yes | Do not assume all portal products | Yes | Not audited here | Not audited here | Public guidance exists | Not evaluated here | Not evaluated here | AirGuard adds an explicitly non-official next-day integration |
| OpenAQ | Measurement access/aggregation | Upstream | API is principally observations | Raw concentrations, not AirGuard index | No AirGuard calibration | Not this project’s intervals | Not a clinical advisory service | Not a forecasting comparison | Not a forecasting comparison | AirGuard adds QC/index/forecast evaluation |
| CAMS | Atmospheric composition forecasts | Assimilation sources; output modelled | Yes | Pollutant output; AirGuard transforms index | Independent CAMS evaluation exists | Product dependent; not audited | Not AirGuard cohort policy | Independent operational verification | Independent operational verification | AirGuard tests India station post-processing |
| Common AQI/weather apps | Consumer information | Provider dependent | Some do | Product dependent | Unknown without specific audit | Product dependent | Some do | Usually not disclosed publicly | Usually not disclosed publicly | No blanket superiority claim |
| Conventional ML research | Forecasting experiments | Study dependent | Yes | Some Indian studies | Often | Some studies | Some studies | Study dependent | Study dependent | AirGuard binds split/QC/artifacts to its deployed prototype |


Evidence checkpoint: measured dataset `4761a5da60dde059b1c7bbfc5403e32d26c983f80e3fc22683eba8a13119821d`; preliminary run `287c87db04a6b29459374c4d50637f943c04dfe10d9072d7e296b74ad1d45a3f`; protocol `e24b664747029a7611efcf4fb19b8cfdf8b12762d379927698fa6e98777d67e8`. Primary CAMS development/final/prospective performance must never be inferred from this non-CAMS run. See [claim ledger](CLAIM_EVIDENCE_MATRIX.md) and [results sheet](ONE_PAGE_RESULTS.md).
