# Script guide (English)

The eight Python scripts in this repository were supplied by the author. Their original filenames, comments, console messages, and processing logic have been preserved to maintain traceability. This guide describes their purposes in English.

## NDMI

- [Historical Landsat NDMI extraction and diagnostics](../src/ndmi/01_descarga_NDMI_historico+Diagnostico.py): Extracts Landsat 8/9 NDMI/NDVI data using Google Earth Engine and includes exploratory diagnostic processing. **Important:** this original file contains two concatenated workflows; inspect its execution order before running it.
- [Weekly NDMI filtering](../src/ndmi/05_depuracion_NDMI_semanal.py): Applies exploratory relative-pixel thresholds and calculates the 14-day minimum NDMI on weekly Sunday dates. Choosing the scene with the most valid pixels is not a spatial mosaic.

## Land surface temperature (LST)

- [Daily LST mosaics and weekly aggregation](../src/lst/08_LST_mosaico_diario_y_semanal.py): Uses Landsat 8/9 Collection 2 Level 2 surface temperature and computes weekly 90th-percentile summaries.
- [Resumable LST processing](../src/lst/09_LST_reanudable_lotes.py): Performs LST extraction in resumable batches with retries and checkpoints.
- [Final LST consistency checks](../src/lst/10_validacion_final_LST.py): Recomputes weekly summaries and reports arithmetic discrepancies, coverage concerns, and temperature flags.

## Climatic water balance (WB)

- [Historical ERA5-Land extraction](../src/water_balance/03_descarga_WB_historico.py): Retrieves precipitation and potential evaporation and calculates daily P − PET and rolling water-balance sums.
- [Resumable weekly ERA5-Land processing](../src/water_balance/11_WB_ERA5Land_reanudable_semanal.py): Uses resumable extraction batches and computes Sunday rolling 30-, 60-, and 90-day balances.
- [Final WB consistency checks](../src/water_balance/12_validacion_final_WB.py): Recalculates balances, records negative-value corrections, and evaluates their effects on rolling summaries.

## Reproducibility and limitations

These scripts reference an Earth Engine project, access-controlled geometries, and some author-specific local paths. They require configuration and authorization before running in another environment. The code has not been independently executed or verified during repository preparation.

The original scripts are kept unchanged rather than silently translating code comments, variable names, or output labels, which could reduce traceability to the author's existing CSV outputs. See the [README](../README.md) and [methodology](methodology.md) for observed results and scientific caveats.
