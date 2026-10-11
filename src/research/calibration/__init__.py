"""Station-calibration study: day-ahead CPCB-style AQI against raw CAMS.

Everything here is offline research code. Nothing in this package runs inside a
user request, writes to the production database, or changes what the live site
serves. Raw inputs are cached as immutable, checksummed files under
`data/research` and every result is written to `results/research`.
"""
