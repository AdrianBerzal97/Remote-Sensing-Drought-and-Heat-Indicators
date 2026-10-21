# -*- coding: utf-8 -*-
"""WB30/60/90 diario y semanal, ERA5-Land DAILY_AGGR, 2015-2025.
Reanudable por lotes de 7 dias. Ejecutar en Spyder con entorno gee.
No confundir potential_evaporation_sum con ET0 FAO56.
"""
from pathlib import Path
import time
import calendar
import ee
import numpy as np
import pandas as pd

PROJECT = 'incendios-491211'
START = pd.Timestamp('2014-10-01')  # margen para WB90 de enero de 2015
END = pd.Timestamp('2025-12-31')
SITES = {
    'Salamanca': 'projects/incendios-491211/assets/Salamanca_Grid',
    'Avila': 'projects/incendios-491211/assets/Avila_Grid',
    'Caceres': 'projects/incendios-491211/assets/Caceres_Grid_Final',
}
OUT = Path(__file__).resolve().parent / 'datos_historicos' / 'WB_revision_final'
PARTS = OUT / 'lotes_descargados'
PARTS.mkdir(parents=True, exist_ok=True)
BATCH_DAYS = 7


def fetch_days(geom, start, end):
    """Consulta intervalos semiabiertos de hasta 7 dias."""
    coll = (ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR')
            .filterDate(start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))
            .select(['total_precipitation_sum', 'potential_evaporation_sum']))

    def feature(im):
        vals = im.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=geom, scale=11132,
            maxPixels=1000000000, tileScale=4)
        return ee.Feature(None, vals).set(
            'date', ee.Date(im.get('system:time_start')).format('YYYY-MM-dd'))

    result = ee.FeatureCollection(coll.map(feature)).getInfo()['features']
    return [f['properties'] for f in result]


def fetch_retry(geom, start, end):
    """Reintentos; si un lote excede el limite, dividirlo en dos."""
    for attempt in range(3):
        try:
            return fetch_days(geom, start, end)
        except Exception as exc:
            msg = str(exc).lower()
            if ('concurrent aggregations' in msg or 'too many' in msg) and (end-start).days > 1:
                middle = start + pd.Timedelta(days=max(1, (end-start).days // 2))
                return fetch_retry(geom, start, middle) + fetch_retry(geom, middle, end)
            if attempt == 2:
                raise
            print('  Reintentando:', str(exc)[:160])
            time.sleep(3 * (attempt+1))
    raise RuntimeError('Error de descarga')


def extract_site(site, geom):
    cursor = START
    while cursor <= END:
        finish = min(cursor + pd.Timedelta(days=BATCH_DAYS), END + pd.Timedelta(days=1))
        fname = PARTS / f'{site}_{cursor:%Y%m%d}_{finish:%Y%m%d}.csv'
        if fname.exists():
            print(f'{site} {cursor:%Y-%m-%d}: lote ya guardado')
        else:
            rows = fetch_retry(geom, cursor, finish)
            df = pd.DataFrame(rows)
            if df.empty:
                # Nunca marcar como completo un intervalo vacio: revisar manualmente.
                raise RuntimeError(f'Sin datos ERA5-Land: {site} {cursor.date()} - {finish.date()}')
            required = ['date', 'total_precipitation_sum', 'potential_evaporation_sum']
            missing = [c for c in required if c not in df.columns]
            if missing:
                raise RuntimeError(f'Faltan columnas en {site}: {missing}')
            df = df[required].sort_values('date')
            df.to_csv(fname, index=False, encoding='utf-8-sig')
            print(f'{site} {cursor:%Y-%m-%d}: guardados {len(df)} dias')
        cursor = finish


def build_outputs():
    daily_all, weekly_all, checks = [], [], []
    for site in SITES:
        files = sorted(PARTS.glob(f'{site}_*.csv'))
        if not files:
            raise RuntimeError(f'No existen lotes para {site}')
        raw = pd.concat([pd.read_csv(p) for p in files], ignore_index=True)
        raw['date'] = pd.to_datetime(raw['date'], errors='coerce')
        duplicates = int(raw.duplicated('date').sum())
        if duplicates:
            raise RuntimeError(f'{site}: {duplicates} fechas duplicadas. Revisar lotes.')
        raw = raw.set_index('date').sort_index().reindex(pd.date_range(START, END, freq='D', name='date'))
        raw['P_mm'] = pd.to_numeric(raw['total_precipitation_sum'], errors='coerce') * 1000
        # ERA5-Land: evaporacion negativa para flujo hacia arriba.
        raw['PET_mm'] = -pd.to_numeric(raw['potential_evaporation_sum'], errors='coerce') * 1000
        raw['WB_mm'] = raw['P_mm'] - raw['PET_mm']
        for days in (30, 60, 90):
            raw[f'WB{days}_mm'] = raw['WB_mm'].rolling(days, min_periods=days).sum()
        raw['site'] = site
        daily = raw.reset_index()
        daily_all.append(daily[['site', 'date', 'P_mm', 'PET_mm', 'WB_mm',
                                'WB30_mm', 'WB60_mm', 'WB90_mm']])
        sundays = pd.date_range('2015-01-01', END, freq='W-SUN')
        weekly = raw.reindex(sundays)[['WB30_mm', 'WB60_mm', 'WB90_mm']].copy()
        weekly.index.name = 'week_end'
        weekly = weekly.reset_index()
        weekly.insert(0, 'site', site)
        weekly_all.append(weekly)
        checks.append({
            'site': site,
            'days_expected': len(raw),
            'days_missing_P_or_PET': int(raw[['P_mm', 'PET_mm']].isna().any(axis=1).sum()),
            'days_P_negative': int((raw['P_mm'] < -0.01).sum()),
            'days_PET_negative': int((raw['PET_mm'] < -0.01).sum()),
            'weeks_expected': len(weekly),
            'weeks_complete_WB30': int(weekly['WB30_mm'].notna().sum()),
            'weeks_complete_WB60': int(weekly['WB60_mm'].notna().sum()),
            'weeks_complete_WB90': int(weekly['WB90_mm'].notna().sum()),
            'min_PET_mm': raw['PET_mm'].min(),
            'max_PET_mm': raw['PET_mm'].max(),
        })
    daily = pd.concat(daily_all, ignore_index=True)
    weekly = pd.concat(weekly_all, ignore_index=True)
    quality = pd.DataFrame(checks)
    daily.to_csv(OUT / '01_WB_diario_2014_2025.csv', index=False, encoding='utf-8-sig')
    weekly.to_csv(OUT / '02_WB_semanal_2015_2025_prevalidacion.csv', index=False, encoding='utf-8-sig')
    quality.to_csv(OUT / '03_controles_preliminares.csv', index=False, encoding='utf-8-sig')
    print('\nRESUMEN DE CONTROL\n', quality.to_string(index=False))
    print('\nArchivos generados en:', OUT)
    print('IMPORTANTE: no considerar definitivos antes de la validacion.')


def main():
    ee.Initialize(project=PROJECT)
    for site, asset in SITES.items():
        print('\n---', site, '---')
        geom = ee.FeatureCollection(asset).geometry()
        extract_site(site, geom)
    build_outputs()


if __name__ == '__main__':
    main()