# -*- coding: utf-8 -*-
"""LST Landsat 8/9 C2 L2: mosaico diario, cobertura y p90 semanal.
Requiere earthengine-api, pandas, numpy. No modifica los archivos previos.
"""
from pathlib import Path
import ee
import numpy as np
import pandas as pd

PROJECT = 'incendios-491211'
START_DATE = '2014-12-15'  # margen para primeras ventanas de 2015
END_DATE = '2026-01-01'    # exclusivo
OUT = Path(__file__).resolve().parent / 'datos_historicos' / 'LST_revision_final'
OUT.mkdir(parents=True, exist_ok=True)
SITES = {
    'Salamanca': 'projects/incendios-491211/assets/Salamanca_Grid',
    'Avila': 'projects/incendios-491211/assets/Avila_Grid',
    'Caceres': 'projects/incendios-491211/assets/Caceres_Grid_Final',
}
THRESHOLDS = (0.05, 0.10, 0.20)


def prepare(im):
    qa = im.select('QA_PIXEL')
    good = qa.bitwiseAnd(1).eq(0)
    for bit in (1, 2, 3, 4, 5):
        good = good.And(qa.bitwiseAnd(1 << bit).eq(0))
    good = good.And(im.select('QA_RADSAT').eq(0))
    # PROCESSING_LEVEL L2SP garantiza banda ST procesada; máscara ST_B10 nativa.
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
    # Menos nubosas al final: en mosaic() tienen prioridad en solapamientos.
    mosaic = subset.sort('CLOUD_COVER', False).mosaic().select('LST_C')
    mean = mosaic.reduceRegion(
        reducer=ee.Reducer.mean(), geometry=geom, scale=30,
        maxPixels=1e9, tileScale=4).get('LST_C')
    area_img = ee.Image.pixelArea().rename('area').updateMask(mosaic.mask())
    valid_area = ee.Number(ee.Dictionary(area_img.reduceRegion(
        reducer=ee.Reducer.sum(), geometry=geom, scale=30,
        maxPixels=1e9, tileScale=4)).get('area', 0))
    return ee.Feature(None, {
        'site': site, 'date': d.format('YYYY-MM-dd'),
        'LST_C': mean, 'valid_area_m2': valid_area,
        'total_area_m2': total_area,
        'coverage_fraction': valid_area.divide(total_area).min(1),
        'n_scenes': subset.size()
    })


def main():
    ee.Initialize(project=PROJECT)
    daily_parts = []
    for site, asset in SITES.items():
        geom = ee.FeatureCollection(asset).geometry()
        total_area = geom.area(maxError=1)
        coll = make_collection(geom)
        # Procesar por año para limitar el tamaño de cada petición.
        for year in range(2014, 2026):
            start = max(f'{year}-01-01', START_DATE)
            end = min(f'{year+1}-01-01', END_DATE)
            subset = coll.filterDate(start, end)
            # Fechas únicas disponibles, sin descargar imágenes.
            dates = ee.List(subset.aggregate_array('system:time_start')).map(
                lambda t: ee.Date(t).format('YYYY-MM-dd')).distinct().sort()
            n = dates.size().getInfo()
            if n:
                fc = ee.FeatureCollection(dates.map(
                    lambda d: daily_feature(d, subset, geom, site, total_area)))
                rows = [f['properties'] for f in fc.getInfo()['features']]
            else:
                rows = []
            frame = pd.DataFrame(rows, columns=[
                'site', 'date', 'LST_C', 'valid_area_m2',
                'total_area_m2', 'coverage_fraction', 'n_scenes'])
            daily_parts.append(frame)
            print(f'{site} {year}: {len(frame)} fechas')
    daily = pd.concat(daily_parts, ignore_index=True)
    daily['date'] = pd.to_datetime(daily['date'], errors='coerce')
    for col in ('LST_C', 'valid_area_m2', 'total_area_m2',
                'coverage_fraction', 'n_scenes'):
        daily[col] = pd.to_numeric(daily[col], errors='coerce')
    daily = daily.sort_values(['site', 'date']).reset_index(drop=True)
    daily.to_csv(OUT / '01_LST_diario_mosaico.csv', index=False, encoding='utf-8-sig')

    sundays = pd.date_range('2015-01-04', '2025-12-28', freq='W-SUN')
    weekly_rows = []
    for site in SITES:
        dsite = daily[daily['site'] == site]
        for sunday in sundays:
            # Ventana inclusiva de 14 días: domingo y 13 días previos.
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
    print('\nFinalizado. Resultados en:', OUT)
    print(summary.to_string(index=False))


if __name__ == '__main__':
    main()