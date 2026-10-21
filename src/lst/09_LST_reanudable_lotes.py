# -*- coding: utf-8 -*-
"""LST Landsat 8/9: extracción reanudable en lotes pequeños y p90 semanal.
Ejecutar con F5 en Spyder (entorno gee). No requiere volver a autenticar.
"""
from pathlib import Path
import time
import ee
import numpy as np
import pandas as pd

PROJECT = 'incendios-491211'
START_DATE = '2014-12-15'
END_DATE = '2026-01-01'
OUT = Path(__file__).resolve().parent / 'datos_historicos' / 'LST_revision_final'
PARTS = OUT / 'lotes_diarios'
PARTS.mkdir(parents=True, exist_ok=True)
SITES = {
    'Salamanca': 'projects/incendios-491211/assets/Salamanca_Grid',
    'Avila': 'projects/incendios-491211/assets/Avila_Grid',
    'Caceres': 'projects/incendios-491211/assets/Caceres_Grid_Final',
}
THRESHOLDS = (0.05, 0.10, 0.20)
# Una fecha por petición evita el error de demasiadas agregaciones simultáneas.
# Cada fecha queda guardada: si falla, la próxima ejecución continúa.
MAX_RETRIES = 4


def prepare(im):
    qa = im.select('QA_PIXEL')
    good = qa.bitwiseAnd(1).eq(0)
    for bit in (1, 2, 3, 4, 5):
        good = good.And(qa.bitwiseAnd(1 << bit).eq(0))
    good = good.And(im.select('QA_RADSAT').eq(0))
    st = im.select('ST_B10')
    lst = st.multiply(0.00341802).add(149).subtract(273.15).rename('LST_C')
    return lst.updateMask(good).copyProperties(im, ['system:time_start', 'CLOUD_COVER'])


def make_collection(geom):
    merged = ee.ImageCollection([])
    for code in ('LC08', 'LC09'):
        sub = (ee.ImageCollection(f'LANDSAT/{code}/C02/T1_L2')
               .filterDate(START_DATE, END_DATE)
               .filterBounds(geom)
               .filter(ee.Filter.eq('PROCESSING_LEVEL', 'L2SP'))
               .filter(ee.Filter.lt('CLOUD_COVER', 60))
               .map(prepare))
        merged = merged.merge(sub)
    return merged


def daily_feature(day, coll, geom, site, total_area):
    d = ee.Date(day)
    subset = coll.filterDate(d, d.advance(1, 'day'))
    mosaic = subset.sort('CLOUD_COVER', False).mosaic().select('LST_C')
    # Reducir media y área válida en una única agregación.
    area = ee.Image.pixelArea().updateMask(mosaic.mask()).rename('valid_area_m2')
    stacked = mosaic.addBands(area)
    reduced = stacked.reduceRegion(
        reducer=ee.Reducer.mean().forEachBand(mosaic).combine(
            reducer2=ee.Reducer.sum().forEachBand(area), sharedInputs=False),
        geometry=geom, scale=30, maxPixels=1e9, tileScale=8)
    # Los nombres de la reducción combinada son LST_C_mean y valid_area_m2_sum.
    return ee.Feature(None, {
        'site': site, 'date': d.format('YYYY-MM-dd'),
        'LST_C': reduced.get('LST_C_mean'),
        'valid_area_m2': reduced.get('valid_area_m2_sum'),
        'total_area_m2': total_area,
        'n_scenes': subset.size(),
    })


def fetch_one(day, coll, geom, site, total_area):
    # Método más conservador: una sola fecha, dos reducciones dentro de la misma petición.
    d = ee.Date(day)
    subset = coll.filterDate(d, d.advance(1, 'day'))
    mosaic = subset.sort('CLOUD_COVER', False).mosaic().select('LST_C')
    values = mosaic.reduceRegion(ee.Reducer.mean(), geom, 30,
                                 maxPixels=int(1e9), tileScale=8)
    valid_area = ee.Image.pixelArea().rename('area').updateMask(mosaic.mask()).reduceRegion(
        ee.Reducer.sum(), geom, 30, maxPixels=int(1e9), tileScale=8)
    feature = ee.Feature(None, {
        'site': site, 'date': day, 'LST_C': values.get('LST_C'),
        'valid_area_m2': valid_area.get('area'),
        'total_area_m2': total_area, 'n_scenes': subset.size(),
    })
    return feature.getInfo()['properties']


def safe_get(func, description):
    for attempt in range(MAX_RETRIES):
        try:
            return func()
        except ee.EEException as exc:
            if attempt == MAX_RETRIES - 1:
                raise RuntimeError(f'Error en {description}: {exc}') from exc
            wait = 5 * (2 ** attempt)
            print(f'  Reintento {attempt + 1} para {description}, espera {wait}s: {exc}')
            time.sleep(wait)


def get_dates(coll, start, end):
    subset = coll.filterDate(start, end)
    dates = ee.List(subset.aggregate_array('system:time_start')).map(
        lambda t: ee.Date(t).format('YYYY-MM-dd')).distinct().sort()
    return safe_get(lambda: dates.getInfo(), f'fechas {start} a {end}')


def extract():
    ee.Initialize(project=PROJECT)
    for site, asset in SITES.items():
        geom = ee.FeatureCollection(asset).geometry()
        total_area = geom.area(maxError=1)
        coll = make_collection(geom)
        for year in range(2014, 2026):
            for month in range(1, 13):
                start = max(f'{year}-{month:02d}-01', START_DATE)
                next_year = year + (month == 12)
                next_month = 1 if month == 12 else month + 1
                end = min(f'{next_year}-{next_month:02d}-01', END_DATE)
                if start >= end:
                    continue
                path = PARTS / f'{site}_{year}_{month:02d}.csv'
                dates = get_dates(coll, start, end)
                cols = ['site', 'date', 'LST_C', 'valid_area_m2',
                        'total_area_m2', 'coverage_fraction', 'n_scenes']
                if path.exists():
                    existing = pd.read_csv(path, dtype={'date': str})
                    if not set(cols).issubset(existing.columns):
                        raise ValueError(f'Archivo parcial con columnas incorrectas: {path}')
                    existing = existing[cols].drop_duplicates('date', keep='last')
                else:
                    existing = pd.DataFrame(columns=cols)
                completed = set(existing['date'].dropna().astype(str))
                missing = [d for d in dates if d not in completed]
                if not missing:
                    print(f'{site} {year}-{month:02d}: completo ({len(dates)} fechas)')
                    continue
                print(f'{site} {year}-{month:02d}: {len(missing)} pendientes de {len(dates)}')
                rows = existing.to_dict('records')
                for day in missing:
                    row = safe_get(lambda d=day: fetch_one(d, coll, geom, site, total_area),
                                   f'{site} {day}')
                    area = row.get('valid_area_m2')
                    total = row.get('total_area_m2')
                    row['coverage_fraction'] = (min(1.0, float(area) / float(total))
                                                if area is not None and total else 0.0)
                    rows.append(row)
                    # Guardar inmediatamente cada día; escritura atómica.
                    frame = pd.DataFrame(rows, columns=cols).sort_values('date')
                    tmp = path.with_suffix('.tmp')
                    frame.to_csv(tmp, index=False, encoding='utf-8-sig')
                    tmp.replace(path)
                print(f'  Guardadas {len(rows)} fechas en {path.name}')


def build_weekly():
    cols = ['site', 'date', 'LST_C', 'valid_area_m2',
            'total_area_m2', 'coverage_fraction', 'n_scenes']
    paths = sorted(PARTS.glob('*.csv'))
    if not paths:
        raise RuntimeError('No hay archivos diarios para generar la serie semanal.')
    daily = pd.concat([pd.read_csv(p) for p in paths], ignore_index=True)
    daily = daily[cols].drop_duplicates(['site', 'date'], keep='last')
    daily['date'] = pd.to_datetime(daily['date'], errors='coerce')
    for col in cols[2:]:
        daily[col] = pd.to_numeric(daily[col], errors='coerce')
    daily = daily.sort_values(['site', 'date']).reset_index(drop=True)
    daily.to_csv(OUT / '01_LST_diario_mosaico.csv', index=False, encoding='utf-8-sig')
    sundays = pd.date_range('2015-01-04', '2025-12-28', freq='W-SUN')
    weekly_rows = []
    for site in SITES:
        dsite = daily[daily['site'] == site]
        for sunday in sundays:
            window = dsite[(dsite['date'] >= sunday - pd.Timedelta(days=13)) &
                           (dsite['date'] <= sunday)]
            for threshold in THRESHOLDS:
                valid = window[(window['coverage_fraction'] >= threshold) &
                               window['LST_C'].notna()]
                weekly_rows.append({
                    'site': site, 'week_end': sunday.date().isoformat(),
                    'coverage_threshold': threshold,
                    'LST_p90_C': float(np.percentile(valid['LST_C'], 90)) if len(valid) else np.nan,
                    'n_valid_days': len(valid),
                    'min_coverage_used': valid['coverage_fraction'].min() if len(valid) else np.nan,
                    'mean_coverage_used': valid['coverage_fraction'].mean() if len(valid) else np.nan,
                    'n_scenes_used': int(valid['n_scenes'].sum()) if len(valid) else 0,
                })
    weekly = pd.DataFrame(weekly_rows)
    weekly.to_csv(OUT / '02_LST_semanal_sensibilidad.csv', index=False, encoding='utf-8-sig')
    summary = (weekly.groupby(['site', 'coverage_threshold'])
               .agg(total_weeks=('week_end', 'size'),
                    valid_weeks=('LST_p90_C', 'count'),
                    one_day_weeks=('n_valid_days', lambda x: int((x == 1).sum())))
               .reset_index())
    summary['missing_weeks'] = summary['total_weeks'] - summary['valid_weeks']
    summary['valid_fraction'] = summary['valid_weeks'] / summary['total_weeks']
    summary.to_csv(OUT / '03_resumen_sensibilidad.csv', index=False, encoding='utf-8-sig')
    print('\nFINALIZADO. Resultados:', OUT)
    print(summary.to_string(index=False))


def main():
    extract()
    build_weekly()


if __name__ == '__main__':
    main()