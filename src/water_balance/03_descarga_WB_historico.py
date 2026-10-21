# -*- coding: utf-8 -*-
"""ERA5-Land DAILY_AGGR, P y potencial_evaporation_sum, 2014-2025.
La evaporación potencial de ERA5-Land NO es ET0 FAO56.
Se usa el signo opuesto según convenio del producto, como script original.
"""
import ee
import pandas as pd
from pathlib import Path
PROJECT='incendios-491211'
START_DATE='2014-10-01' # calentamiento WB90
END_DATE='2026-01-01'
OUTPUT_FOLDER=Path(__file__).resolve().parent/'datos_historicos'
OUTPUT_FOLDER.mkdir(parents=True,exist_ok=True)
SITES={'Salamanca':'projects/incendios-491211/assets/Salamanca_Grid',
       'Avila':'projects/incendios-491211/assets/Avila_Grid',
       'Caceres':'projects/incendios-491211/assets/Caceres_Grid_Final'}

def main():
    ee.Initialize(project=PROJECT)
    for site,asset in SITES.items():
        geom=ee.FeatureCollection(asset).geometry()
        coll=ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR').filterDate(START_DATE,END_DATE)
        yearly=[]
        for year in range(2014,2026):
            start=max(f'{year}-01-01',START_DATE)
            end=min(f'{year+1}-01-01',END_DATE)
            def extract(im):
                vals=im.select(['total_precipitation_sum','potential_evaporation_sum']).reduceRegion(
                    reducer=ee.Reducer.mean(),geometry=geom,scale=11132,maxPixels=1e9)
                return ee.Feature(None,vals).set('date',ee.Date(im.get('system:time_start')).format('YYYY-MM-dd'))
            fc=ee.FeatureCollection(coll.filterDate(start,end).map(extract))
            rows=[f['properties'] for f in fc.getInfo()['features']]
            df=pd.DataFrame(rows)
            if not df.empty:
                df['date']=pd.to_datetime(df['date'])
                df['P_mm']=pd.to_numeric(df['total_precipitation_sum'],errors='coerce')*1000
                df['PET_mm']=-pd.to_numeric(df['potential_evaporation_sum'],errors='coerce')*1000
                df['site']=site
                yearly.append(df[['site','date','P_mm','PET_mm']])
            print(site,year,len(rows))
        if not yearly: continue
        data=pd.concat(yearly,ignore_index=True).sort_values('date')
        data=data.drop_duplicates('date').set_index('date').asfreq('D').reset_index()
        data['site']=site
        data['WB']=data['P_mm']-data['PET_mm']
        for days in (30,60,90):
            # Sólo ventanas completas, sin asumir cero cuando faltan días
            data[f'WB_{days}d']=data['WB'].rolling(days,min_periods=days).sum()
        path=OUTPUT_FOLDER/f'{site}_balance_hidrico_diario_2014_2025.csv'
        data.to_csv(path,index=False,encoding='utf-8-sig')
        print('Guardado',path)

if __name__=='__main__': main()