# ADS manual setup reference

**12 October 2026 update:** the user completed setup, `cdsapi==0.7.7` imports
in `.venv-live`, the credential file exists, and ADS accepted the one tiny
forecast request. The original 134-byte GRIB file has now passed checksum,
forecast/run/lead/valid-time, PM2.5 and 3×3 grid/value inspection. Development
archive acquisition is active. No additional manual setup is currently indicated.
See [CAMS_ADS_ACTIVATION.md](CAMS_ADS_ACTIVATION.md). The instructions below are
retained as setup reference, not a request to reveal or reconfigure the token.

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

No token value is needed in chat. Credentials and terms were configured by the
user; the agent has not changed them. The inherited Open-Meteo CAMS cache is
preserved with its proxy label and is excluded from the primary experiment.
