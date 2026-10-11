# Software, data and hosted services

AirGuard source code uses the repository's MIT licence. This does not relicense
third-party observations, forecast products, geographic tiles or publications.
The operational project remains non-commercial. Provider quotas and licence
restrictions apply independently of the software licence.

| Material | Attribution / release condition |
|---|---|
| Open-Meteo weather and CAMS-derived air-quality data | Open-Meteo and CAMS/Copernicus attribution; derived AirGuard estimates identified. Free hosted API restricted to non-commercial use; see [terms](https://open-meteo.com/en/terms). |
| OpenAQ observations | OpenAQ plus named upstream owner/provider. Preserve each station's licence metadata; see [terms](https://docs.openaq.org/about/terms). |
| CPCB/data.gov.in | CPCB and data.gov.in, subject to [Government Open Data Licence India](https://www.data.gov.in/government-open-data-license-india). This release has no successful CPCB network response. |
| NASA FIRMS | NASA FIRMS/LANCE and satellite product attribution; [data-use FAQ](https://firms.modaps.eosdis.nasa.gov/faq/). Hotspots are context, not AQI observations. |
| OSM raster tiles | Visible OpenStreetMap contributors attribution; [tile policy](https://operations.osmfoundation.org/policies/tiles/). Load only on explicit map opening; no offline tile download or bulk prefetch. |
| GeoNames search | GeoNames and Open-Meteo attribution. |
| Historical Kaggle export | Preserve original acquisition provenance. Historical records cannot establish today's conditions or archive forecast availability. |
| Population grids / archived CAMS / ERA5 | Not redistributed by this release. Exact product version, licence, terms and hashes required before experiments. |

MapLibre GL is an installed pinned dependency; npm's package licence metadata
and transitive notices remain applicable. Commercial deployment requires a
provider licence review and an appropriate Open-Meteo plan.
