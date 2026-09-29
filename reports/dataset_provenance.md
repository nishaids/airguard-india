# Dataset Provenance Record

> This document is generated automatically by `src/data/acquire.py` from the
> dataset as actually downloaded. Every checksum, row count and licence string
> below was produced by executed code, not transcribed by hand. The
> machine-readable equivalent is `data/raw/PROVENANCE.json`.

**Generated (UTC):** 2026-09-28T17:29:24Z

## 1. Identity

| Field | Value |
| --- | --- |
| Dataset title (scraped) | Air Quality Data in India (2015 - 2020) |
| Kaggle URL | <https://www.kaggle.com/datasets/rohanrao/air-quality-data-in-india> |
| Kaggle slug | `rohanrao/air-quality-data-in-india` |
| Uploader handle | `rohanrao` |
| Uploader display name | Vopani |
| Uploader profile | <https://www.kaggle.com/rohanrao> |
| Last modified on Kaggle | 2020-07-28T12:33:10.347Z |
| Local version directory | `C:\Users\Nishanth R\.cache\kagglehub\datasets\rohanrao\air-quality-data-in-india\versions\12` |
| Access method | Path A - programmatic download via kagglehub (anonymous) |

## 2. Licence (recorded as displayed, not assumed)

| Field | Value |
| --- | --- |
| Licence string on Kaggle | **CC0: Public Domain** |
| Licence URL | <https://creativecommons.org/publicdomain/zero/1.0/> |
| Verified live at download time | True |
| Verification method | Licence string read verbatim from the schema.org JSON-LD block embedded in the live Kaggle dataset page. |
| Page checked | <https://www.kaggle.com/datasets/rohanrao/air-quality-data-in-india> |
| Licence of the code in this repository | MIT (see LICENSE) |

## 3. Provenance chain

1. **Measurement.** Central Pollution Control Board (CPCB), Ministry of Environment, Forest and Climate Change, Government of India operates the Continuous Ambient Air Quality Monitoring Station (CAAQMS) network and publishes the readings at <https://cpcb.nic.in/> and through its public portal <https://app.cpcbccr.com/AQI_India/>.
2. **Compilation and mirroring.** Vopani (`rohanrao`) compiled the station readings into station-level and city-level daily and hourly tables and published them on Kaggle at <https://www.kaggle.com/datasets/rohanrao/air-quality-data-in-india>.
3. **Retrieval for this project.** Path A - programmatic download via kagglehub (anonymous), on 2026-09-28T17:29:24Z. Files were copied unmodified into `data/raw/`.

Attribution basis for step 1: Stated in the Acknowledgements section of the Kaggle dataset description: 'The data has been made publicly available by the Central Pollution Control Board: https://cpcb.nic.in/ which is the official portal of Government of India.'

## 4. Files acquired, with checksums

| File | Size (MB) | Rows | Cols | Retained in `data/raw/` | SHA-256 |
| --- | --- | --- | --- | --- | --- |
| `city_day.csv` | 2.57 | 29,531 | 16 | yes | `0d84b21c3e4878bbad8df362f2ab05f61ad959538dddf5918e714077ed3c1847` |
| `city_hour.csv` | 65.65 | 707,875 | 16 | yes | `fae474062ec6b10af7c5b2ac4e32f5c240a0ef80835ee3a50332fec06e2190a4` |
| `station_day.csv` | 8.63 | 108,035 | 16 | yes | `f07787eb4c36c53b07763f591ee29fa01fbaa4d18df1a470447d04def79677b9` |
| `station_hour.csv` | 219.68 | 2,589,083 | 16 | no | `26a423c66fe9763064d580ffb007150375cfa2056e62b29d52b1b7857af54fde` |
| `stations.csv` | 0.01 | 230 | 5 | yes | `ce2b7081c3e3c89145613eb724d7d2149ef79c6e16f36bb8a835747a673ed410` |

Files not copied into `data/raw/`: `station_hour.csv`. These are checksummed at the download location and are not used by any analysis in this project; excluding them keeps the repository within a practical size.

## 5. Primary working file: `city_day.csv`

* Rows: **29,531**
* Columns: **16**
* Date coverage: **2015-01-01 to 2020-07-01**
* Cities: **26**

### 5.1 Column-level schema

| Column | Dtype | Non-null | Nulls | Null % | Min / Cardinality | Max / Top-5 |
| --- | --- | --- | --- | --- | --- | --- |
| `City` | object | 29,531 | 0 | 0.00 | 26 unique | Ahmedabad (2,009), Bengaluru (2,009), Chennai (2,009), Mumbai (2,009), Lucknow (2,009) |
| `Date` | datetime64[ns] | 29,531 | 0 | 0.00 | 2009 unique | 2020-03-14 00:00:00 (26), 2020-04-10 00:00:00 (26), 2020-04-11 00:00:00 (26), 2020-04-12 00:00:00 (26), 2020-04-13 00:00:00 (26) |
| `PM2.5` | float64 | 24,933 | 4,598 | 15.57 | 0.04 | 949.99 |
| `PM10` | float64 | 18,391 | 11,140 | 37.72 | 0.01 | 1,000.00 |
| `NO` | float64 | 25,949 | 3,582 | 12.13 | 0.02 | 390.68 |
| `NO2` | float64 | 25,946 | 3,585 | 12.14 | 0.01 | 362.21 |
| `NOx` | float64 | 25,346 | 4,185 | 14.17 | 0.00 | 467.63 |
| `NH3` | float64 | 19,203 | 10,328 | 34.97 | 0.01 | 352.89 |
| `CO` | float64 | 27,472 | 2,059 | 6.97 | 0.00 | 175.81 |
| `SO2` | float64 | 25,677 | 3,854 | 13.05 | 0.01 | 193.86 |
| `O3` | float64 | 25,509 | 4,022 | 13.62 | 0.01 | 257.73 |
| `Benzene` | float64 | 23,908 | 5,623 | 19.04 | 0.00 | 455.03 |
| `Toluene` | float64 | 21,490 | 8,041 | 27.23 | 0.00 | 454.85 |
| `Xylene` | float64 | 11,422 | 18,109 | 61.32 | 0.00 | 170.37 |
| `AQI` | float64 | 24,850 | 4,681 | 15.85 | 13.00 | 2,049.00 |
| `AQI_Bucket` | object | 24,850 | 4,681 | 15.85 | 6 unique | Moderate (8,829), Satisfactory (8,224), Poor (2,781), Very Poor (2,337), Good (1,341) |

The same table is rendered at 300 DPI as `reports/figures/00_dataset_proof_schema.png`.

### 5.2 Per-city coverage

| City | Records | AQI non-null | First date | Last date |
| --- | --- | --- | --- | --- |
| Ahmedabad | 2,009 | 1,334 | 2015-01-01 | 2020-07-01 |
| Aizawl | 113 | 111 | 2020-03-11 | 2020-07-01 |
| Amaravati | 951 | 841 | 2017-11-24 | 2020-07-01 |
| Amritsar | 1,221 | 1,126 | 2017-02-27 | 2020-07-01 |
| Bengaluru | 2,009 | 1,910 | 2015-01-01 | 2020-07-01 |
| Bhopal | 289 | 278 | 2019-09-17 | 2020-07-01 |
| Brajrajnagar | 938 | 713 | 2017-12-07 | 2020-07-01 |
| Chandigarh | 304 | 299 | 2019-09-02 | 2020-07-01 |
| Chennai | 2,009 | 1,884 | 2015-01-01 | 2020-07-01 |
| Coimbatore | 386 | 344 | 2019-06-12 | 2020-07-01 |
| Delhi | 2,009 | 1,999 | 2015-01-01 | 2020-07-01 |
| Ernakulam | 162 | 153 | 2020-01-22 | 2020-07-01 |
| Gurugram | 1,679 | 1,453 | 2015-11-27 | 2020-07-01 |
| Guwahati | 502 | 495 | 2019-02-16 | 2020-07-01 |
| Hyderabad | 2,006 | 1,880 | 2015-01-04 | 2020-07-01 |
| Jaipur | 1,114 | 1,094 | 2017-06-14 | 2020-07-01 |
| Jorapokhar | 1,169 | 771 | 2017-04-20 | 2020-07-01 |
| Kochi | 162 | 158 | 2020-01-22 | 2020-07-01 |
| Kolkata | 814 | 754 | 2018-04-10 | 2020-07-01 |
| Lucknow | 2,009 | 1,893 | 2015-01-01 | 2020-07-01 |
| Mumbai | 2,009 | 775 | 2015-01-01 | 2020-07-01 |
| Patna | 1,858 | 1,459 | 2015-06-01 | 2020-07-01 |
| Shillong | 310 | 205 | 2019-08-27 | 2020-07-01 |
| Talcher | 925 | 698 | 2017-12-20 | 2020-07-01 |
| Thiruvananthapuram | 1,112 | 1,052 | 2017-06-16 | 2020-07-01 |
| Visakhapatnam | 1,462 | 1,171 | 2016-07-01 | 2020-07-01 |

## 6. Station metadata (`stations.csv`)

* Columns: `StationId`, `StationName`, `City`, `State`, `Status`
* Monitoring stations: **230**
* Cities represented: **127**
* States represented: **21**

## 7. Open-data compliance statement

The measurements analysed in this project were produced by the Central Pollution Control Board (CPCB), Government of India, and released into the public domain by that agency. They were obtained for this work from the Kaggle mirror maintained by Rohan Rao, whose dataset page declares the licence recorded verbatim in the 'license' block above. That declaration places the compiled dataset in the public domain, which permits unrestricted reproduction, redistribution, adaptation and commercial or academic reuse without a requirement of permission. No authentication, paid subscription or scraping of access-controlled pages was involved: the archive was retrieved through the publicly documented Kaggle dataset API. Use in this project is therefore fully compliant with the terms under which the data was published. Attribution to CPCB and to the Kaggle uploader is nevertheless given throughout this repository as a matter of academic practice. The raw files in data/raw/ are treated as immutable: no script in this repository writes to that directory except the acquisition module, and every transformation is written to data/interim/ or data/processed/.

## 8. How to re-verify this record

```bash
python -m src.data.acquire            # regenerate PROVENANCE.json
python -c "from src.data.acquire import sha256_of; from pathlib import Path; print(sha256_of(Path('data/raw/city_day.csv')))"
```

The printed digest must equal the `city_day.csv` SHA-256 in the table above.
