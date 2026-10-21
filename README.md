# Remote Sensing Drought and Heat Indicators

Python workflows for NDMI, land surface temperature (LST), and climatic water balance using Landsat 8/9, ERA5-Land, and Google Earth Engine.

The supplied scripts cover areas labelled Salamanca, Avila and Caceres, mainly over 2015–2025.

- **NDMI/NDVI:** Landsat extraction, exploratory quality diagnostics and 14-day weekly windows.
- **LST:** daily mosaics, weekly 90th percentiles, coverage sensitivity and internal consistency checks.
- **Water balance:** ERA5-Land precipitation and potential evaporation, rolling 30/60/90-day balances, resumable downloads and arithmetic checks.

See [methodological notes](docs/methodology.md) for scientific and technical limitations.

## Requirements

Install packages listed in `requirements.txt`. Google Earth Engine scripts require an authorized Earth Engine project and accessible geometries; original asset identifiers and some local Windows paths need configuring.


## Observed LST outputs (2015–2025)

The following **aggregated values come from the author's actual CSV outputs** (uploaded October 2026), not from synthetic examples. Original CSVs are **not** published in this repository. These are workflow and arithmetic quality checks, not independent validation of satellite surface temperature.

![Weekly LST availability by study area](docs/lst_weekly_availability.svg)

At the **10% minimum coverage threshold**, the weekly output contains 574 Sunday windows for each of three study areas:

| Area | Available weeks | Availability | Available weeks with one qualifying day | Missing weeks |
|---|---:|---:|---:|---:|
| Ávila | 424 / 574 | 73.9% | 188 | 150 |
| Cáceres | 465 / 574 | 81.0% | 195 | 109 |
| Salamanca | 454 / 574 | 79.1% | 235 | 120 |
| **Total** | **1,343 / 1,722** | **78.0%** | **618** | **379** |

The daily LST mosaic output has **1,476 records**. The definitive weekly output has **1,722 records** (including missing weeks). Sensitivity analysis considered coverage thresholds of **5%, 10% and 20%**.

### Recorded quality-control findings

- **0** invalid daily dates, invalid weekly dates, duplicate daily or weekly keys, out-of-range coverage fractions, or discrepancies in weekly recalculation.
- **0** discrepancies against the original sensitivity summary; the two supplied sensitivity-summary CSVs agree.
- **688** instances where valid area exceeded total area beyond the script's **0.1% tolerance**. This is a geometric/scale concern requiring investigation; fractions reported within [0, 1] do **not** resolve it.
- **4** flagged daily temperatures above 55 °C passing the 10% coverage threshold, all in Salamanca. The extreme-temperature audit also lists three subzero values in Ávila that **do not** pass that threshold. Flags indicate review, not automatic invalidation.
- **618** weekly values at 10% coverage derive from **only one qualifying day**; interpret their 90th-percentile label cautiously. **379** weekly windows have no qualifying observations; missing values should not be treated as zero.

**Source files examined locally:** `01_LST_diario_mosaico.csv`, `01_LST_semanal_definitivo_2015_2025.csv`, `02_LST_semanal_sensibilidad.csv`, `02_resumen_sensibilidad_validado.csv`, `03_incidencias_recalculo.csv`, `03_resumen_sensibilidad(1).csv`, `04_cobertura_anual.csv`, `05_cobertura_mensual.csv`, `06_temperaturas_extremas_diarias.csv`, `07_controles_validacion.csv`, and `08_coincidencia_semanal_NDMI_LST.csv`. No individual observations or private geometries are included here.

## Data and validation

No raw data, private Earth Engine assets, synthetic results or fabricated figures are included. The uploaded scripts have not been executed against the original data as part of this repository setup. ERA5-Land potential evaporation is **not** FAO-56 ET0; the scripts' internal checks are not independent validation.
