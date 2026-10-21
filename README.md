# Remote Sensing Drought and Heat Indicators

Python workflows for NDMI, land surface temperature (LST), and climatic water balance using Landsat 8/9, ERA5-Land, and Google Earth Engine.

The supplied scripts cover areas labelled Salamanca, Avila and Caceres, mainly over 2015–2025.

- **NDMI/NDVI:** Landsat extraction, exploratory quality diagnostics and 14-day weekly windows.
- **LST:** daily mosaics, weekly 90th percentiles, coverage sensitivity and internal consistency checks.
- **Water balance:** ERA5-Land precipitation and potential evaporation, rolling 30/60/90-day balances, resumable downloads and arithmetic checks.

See [methodological notes](docs/methodology.md) for scientific and technical limitations.

## Requirements

Install packages listed in `requirements.txt`. Google Earth Engine scripts require an authorized Earth Engine project and accessible geometries; original asset identifiers and some local Windows paths need configuring.

## Data and validation

No raw data, private Earth Engine assets, synthetic results or fabricated figures are included. The uploaded scripts have not been executed against the original data as part of this repository setup. ERA5-Land potential evaporation is **not** FAO-56 ET0; the scripts' internal checks are not independent validation.
