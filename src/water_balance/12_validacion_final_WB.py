# -*- coding: utf-8 -*-
"""Validación reproducible WB ERA5-Land, sin conexión a Earth Engine.
Uso: python 12_validacion_final_WB.py --input CARPETA --output CARPETA
Política: preservar datos originales; truncar a cero P y PET negativos
para la serie operativa; documentar todas las correcciones y sensibilidad.
No representa una validación independiente de ERA5-Land ni PET FAO-56.
"""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

DAILY='01_WB_diario_2014_2025.csv'
WEEKLY='02_WB_semanal_2015_2025_prevalidacion.csv'
SITES=['Salamanca','Avila','Caceres']
START='2014-10-01'; END='2025-12-31'
SUNDAYS=pd.date_range('2015-01-01','2025-12-31',freq='W-SUN')
COLS=['WB30_mm','WB60_mm','WB90_mm']

def run(inp,out):
    out.mkdir(parents=True,exist_ok=True)
    original=pd.read_csv(inp/DAILY,parse_dates=['date'])
    prior=pd.read_csv(inp/WEEKLY,parse_dates=['week_end'])
    errors=[]; changes=[]; cleaned=[]; weeks=[]; comparisons=[]; summary=[]
    expected=pd.date_range(START,END,freq='D')
    if original.duplicated(['site','date']).any(): raise ValueError('Fechas diarias duplicadas')
    if prior.duplicated(['site','week_end']).any(): raise ValueError('Semanas duplicadas')
    if set(original.site)!=set(SITES) or set(prior.site)!=set(SITES): raise ValueError('Zonas incompletas')
    for site in SITES:
        d=original[original.site==site].sort_values('date').copy().set_index('date')
        if len(d)!=len(expected) or not d.index.equals(expected): raise ValueError(f'{site}: calendario diario incompleto')
        if d[['P_mm','PET_mm']].isna().any().any(): raise ValueError(f'{site}: faltan P o PET')
        raw_wb=d.P_mm-d.PET_mm
        for name, calc in [('WB_mm',raw_wb)]+[(f'WB{n}_mm',raw_wb.rolling(n,min_periods=n).sum()) for n in (30,60,90)]:
            old=d[name]; diff=(old-calc).abs()
            bad=diff>1e-7
            if bad.any(): errors.append({'site':site,'variable':name,'n_errors':int(bad.sum()),'max_diff':float(diff.max())})
        for var in ('P_mm','PET_mm'):
            neg=d[d[var]<0]
            for date,r in neg.iterrows():
                changes.append({'site':site,'date':date.date().isoformat(),'variable':var,'original_mm':r[var],'corrected_mm':0.0,'delta_mm':-r[var]})
        d['P_original_mm']=d['P_mm'];d['PET_original_mm']=d['PET_mm']
        d['P_mm']=d['P_mm'].clip(lower=0);d['PET_mm']=d['PET_mm'].clip(lower=0)
        d['WB_mm']=d.P_mm-d.PET_mm
        for n in (30,60,90):d[f'WB{n}_mm']=d.WB_mm.rolling(n,min_periods=n).sum()
        cleaned.append(d.reset_index()[['site','date','P_original_mm','PET_original_mm','P_mm','PET_mm','WB_mm']+COLS])
        w=d.loc[SUNDAYS,COLS].reset_index().rename(columns={'index':'week_end'})
        w.insert(0,'site',site);weeks.append(w)
        old=prior[prior.site==site].set_index('week_end').reindex(SUNDAYS)
        if old[COLS].isna().any().any():raise ValueError(f'{site}: semanas originales incompletas')
        for n in (30,60,90):
            raw=raw_wb.rolling(n,min_periods=n).sum().loc[SUNDAYS]
            e=(raw-old[f'WB{n}_mm']).abs()
            if (e>1e-7).any(): errors.append({'site':site,'variable':f'WB{n}_mm original semanal','n_errors':int((e>1e-7).sum()),'max_diff':float(e.max())})
            delta=w[f'WB{n}_mm'].to_numpy()-old[f'WB{n}_mm'].to_numpy()
            comparisons.append(pd.DataFrame({'site':site,'week_end':SUNDAYS,'window_days':n,'WB_original_mm':old[f'WB{n}_mm'].to_numpy(),'WB_corrected_mm':w[f'WB{n}_mm'].to_numpy(),'delta_mm':delta}))
        summary.append({'site':site,'days':len(d),'weeks':len(w),'negative_P_corrected':int((d.P_original_mm<0).sum()),'negative_PET_corrected':int((d.PET_original_mm<0).sum())})
    final=pd.concat(weeks,ignore_index=True)
    comparison=pd.concat(comparisons,ignore_index=True)
    report=pd.DataFrame(summary)
    for n in (30,60,90):
        x=comparison[comparison.window_days==n]
        report[f'weeks_changed_WB{n}']=report.site.map(x.groupby('site').delta_mm.apply(lambda v:int((v.abs()>1e-9).sum())))
        report[f'max_abs_delta_WB{n}_mm']=report.site.map(x.groupby('site').delta_mm.apply(lambda v:float(v.abs().max())))
    pd.concat(cleaned).to_csv(out/'01_WB_diario_depurado_2014_2025.csv',index=False,encoding='utf-8-sig')
    final.to_csv(out/'02_WB_semanal_definitivo_2015_2025.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(changes,columns=['site','date','variable','original_mm','corrected_mm','delta_mm']).to_csv(out/'03_correcciones_diarias.csv',index=False,encoding='utf-8-sig')
    comparison.to_csv(out/'04_sensibilidad_correcciones_semanales.csv',index=False,encoding='utf-8-sig')
    report.to_csv(out/'05_resumen_validacion.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(errors,columns=['site','variable','n_errors','max_diff']).to_csv(out/'06_incidencias_recalculo.csv',index=False,encoding='utf-8-sig')
    if errors:raise RuntimeError(f'Existen {len(errors)} grupos de discrepancias. Revisar 06_incidencias_recalculo.csv')
    print(report.to_string(index=False));print('Validación aritmética correcta. Archivos:',out)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,default=Path(__file__).resolve().parent);p.add_argument('--output',type=Path,default=Path(__file__).resolve().parent/'WB_validacion_final');a=p.parse_args();run(a.input,a.output)