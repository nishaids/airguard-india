# Manual ADS setup still required

1. Sign in or register at the [Copernicus Atmosphere Data Store](https://ads.atmosphere.copernicus.eu/).
2. Open [CAMS global atmospheric composition forecasts](https://ads.atmosphere.copernicus.eu/datasets/cams-global-atmospheric-composition-forecasts?tab=download)
   and manually accept its Terms of Use. Credential configuration alone does
   not accept the dataset terms.
3. Obtain the personal access token using the [ADS API setup page](https://ads.atmosphere.copernicus.eu/how-to-api).
   Store it privately in your user-home `.cdsapirc`, outside this repository:

   ```yaml
   url: https://ads.atmosphere.copernicus.eu/api
   key: <PERSONAL-ACCESS-TOKEN>
   ```

4. The official setup currently specifies `cdsapi>=0.7.7`. When the token and
   accepted terms exist, install a pinned compatible client into the research
   environment and verify one small genuine forecast request first.

Use operational **forecast** runs, not analysis or reanalysis. Preserve run
initialisation, lead, valid time, retrieval time, request payload, checksums,
units and the evidence/bound that the run was available by 20:00 IST. Do not
select a later run because its error is lower. The study's previous-day 00 UTC
run policy and gas mass-mixing-ratio conversions need validation against actual
ADS metadata, including pressure/temperature from the same forecast where
needed. Archive import must not change the locked final-test dates or expose
their scores for selection.

No token value is needed in chat. No credentials, terms or paid resources have
been configured by this continuation. The inherited Open-Meteo CAMS cache is
preserved with its proxy label and is excluded from the primary experiment.
