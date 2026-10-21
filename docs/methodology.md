# Methodological notes

This repository groups eight author-provided Python scripts for NDMI/NDVI, Landsat land surface temperature (LST), and ERA5-Land climatic water balance (WB) for areas labelled Salamanca, Avila and Caceres.

## NDMI
Landsat 8/9 Collection 2 Level 2 indices are extracted and inspected for missing values, duplicates, valid pixel counts and potential outliers. Weekly output uses a 14-day lookback. The scripts explicitly describe relative valid-pixel counts as exploratory, not true geometric coverage. Selecting one scene per day is not the same as creating a pixel mosaic. The Landsat NDMI series is not interchangeable with an earlier Sentinel-2 series.

## LST
Landsat 8/9 surface temperature is converted to degrees Celsius, masked using quality bands, and mosaicked by day. Weekly 90th percentiles are calculated across qualifying daily mean LST values within 14-day windows. Sensitivity thresholds of 0.05, 0.10 and 0.20 are evaluated. The final audit recomputes weekly summaries from daily CSV files; this is an internal consistency check, not independent satellite validation.

## Climatic water balance
ERA5-Land DAILY_AGGR precipitation and potential evaporation are used to derive P minus PET and rolling 30-, 60- and 90-day balances. ERA5-Land potential evaporation is **not** FAO-56 reference evapotranspiration. The final validation script retains original values and documents its operational rule for clipping negative P and PET to zero; this is a methodological decision, not independent validation.

## Limitations and prerequisites
- Google Earth Engine scripts refer to the author's project and private or access-controlled FeatureCollection asset paths. Users must supply their own authorized project and geometries.
- Some scripts contain local Windows paths that need adapting.
- Extraction scripts require Earth Engine authorization, the `earthengine-api` Python package and other dependencies.
- No original datasets, Earth Engine assets, computed statistics or output figures are included here.
- Scripts have not been executed or verified against the author's data as part of this repository setup.
