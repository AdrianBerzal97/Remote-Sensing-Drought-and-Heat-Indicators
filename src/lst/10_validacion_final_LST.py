# -*- coding: utf-8 -*-
"""Auditoría reproducible de LST semanal 2015-2025, sin Earth Engine.
Colocar este script junto a los tres CSV recibidos, o ajustar BASE.
"""
from pathlib import Path
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
OUT = BASE / 'LST_validacion_final'
OUT.mkdir(parents=True, exist_ok=True)
DAILY = BASE / '01_LST_diario_mosaico.csv'
WEEKLY = BASE / '02_LST_semanal_sensibilidad.csv'
SUMMARY = BASE / '03_resumen_sensibilidad(1).csv'
if not SUMMARY.exists():
    SUMMARY = BASE / '03_resumen_sensibilidad.csv'
SITES = ['Avila', 'Caceres', 'Salamanca']
THRESHOLDS = [0.05, 0.10, 0.20]
SUNDAYS = pd.date_range('2015-01-04', '2025-12-28', freq='W-SUN')
ATOL = 1e-8


def main():
    d = pd.read_csv(DAILY, encoding='utf-8-sig')
    w = pd.read_csv(WEEKLY, encoding='utf-8-sig')
    s = pd.read_csv(SUMMARY, encoding='utf-8-sig')
    d['date'] = pd.to_datetime(d['date'], errors='coerce')
    w['week_end'] = pd.to_datetime(w['week_end'], errors='coerce')
    for c in ['LST_C','valid_area_m2','total_area_m2','coverage_fraction','n_scenes']:
        d[c] = pd.to_numeric(d[c], errors='coerce')
    for c in ['coverage_threshold','LST_p90_C','n_valid_days','min_coverage_used','mean_coverage_used','n_scenes_used']:
        w[c] = pd.to_numeric(w[c], errors='coerce')
    alerts=[]
    def alert(kind, count, detail):
        alerts.append({'control':kind,'n_incidencias':int(count),'detalle':detail})
    alert('Fechas diarias inválidas', d['date'].isna().sum(), 'Fechas que no pueden interpretarse')
    alert('Fechas semanales inválidas', w['week_end'].isna().sum(), 'Fechas que no pueden interpretarse')
    alert('Duplicados diarios', d.duplicated(['site','date']).sum(), 'Misma zona y fecha')
    alert('Duplicados semanales', w.duplicated(['site','week_end','coverage_threshold']).sum(), 'Misma zona, domingo y umbral')
    alert('Coberturas fuera de 0-1', ((d.coverage_fraction < 0) | (d.coverage_fraction > 1)).sum(), 'Fracción de cobertura fuera de rango')
    alert('LST presente sin cobertura', (d.LST_C.notna() & (d.coverage_fraction <= 0)).sum(), 'LST con cobertura nula')
    alert('LST ausente con cobertura positiva', (d.LST_C.isna() & (d.coverage_fraction > 0)).sum(), 'Datos contradictorios')
    alert('Área válida superior al área total', (d.valid_area_m2 > d.total_area_m2 * 1.001).sum(), 'Posible discrepancia geométrica / escala; tolerancia 0,1 %')
    expected = pd.MultiIndex.from_product([SITES,SUNDAYS,THRESHOLDS], names=['site','week_end','coverage_threshold'])
    observed = pd.MultiIndex.from_frame(w[['site','week_end','coverage_threshold']])
    alert('Filas semanales ausentes', len(expected.difference(observed)), 'Combinaciones zona-domingo-umbral')
    alert('Filas semanales adicionales', len(observed.difference(expected)), 'Combinaciones no esperadas')
    checks=[]
    extremes=[]
    for site in SITES:
        ds=d[d.site==site].sort_values('date')
        for sunday in SUNDAYS:
            subset=ds[(ds.date >= sunday-pd.Timedelta(days=13)) & (ds.date <= sunday)]
            for t in THRESHOLDS:
                valid=subset[(subset.coverage_fraction >= t) & subset.LST_C.notna()]
                p90=float(np.percentile(valid.LST_C.to_numpy(),90)) if len(valid) else np.nan
                n=len(valid)
                mincov=float(valid.coverage_fraction.min()) if n else np.nan
                meancov=float(valid.coverage_fraction.mean()) if n else np.nan
                nscenes=int(valid.n_scenes.sum()) if n else 0
                match=w[(w.site==site)&(w.week_end==sunday)&(np.isclose(w.coverage_threshold,t))]
                if len(match)!=1:
                    checks.append({'site':site,'week_end':sunday.date().isoformat(),'threshold':t,'incidencia':'Número de filas distinto de 1','diferencia_p90':np.nan})
                    continue
                row=match.iloc[0]
                comparisons=[('LST_p90_C',p90),('n_valid_days',n),('min_coverage_used',mincov),('mean_coverage_used',meancov),('n_scenes_used',nscenes)]
                for field,value in comparisons:
                    old=row[field]
                    ok=(pd.isna(old) and pd.isna(value)) or (pd.notna(old) and pd.notna(value) and np.isclose(old,value,atol=ATOL,rtol=0))
                    if not ok:
                        checks.append({'site':site,'week_end':sunday.date().isoformat(),'threshold':t,'incidencia':field,'valor_csv':old,'valor_recalculado':value,'diferencia_p90':abs(old-value) if field=='LST_p90_C' and pd.notna(old) and pd.notna(value) else np.nan})
    alert('Discrepancias de recálculo',len(checks),'Comparación de cinco campos semanales con datos diarios')
    chk=pd.DataFrame(checks,columns=['site','week_end','threshold','incidencia','valor_csv','valor_recalculado','diferencia_p90'])
    chk.to_csv(OUT/'03_incidencias_recalculo.csv',index=False,encoding='utf-8-sig')
    w10=w[np.isclose(w.coverage_threshold,0.10)].copy().sort_values(['site','week_end'])
    w10['year']=w10.week_end.dt.year
    w10['one_day_flag']=w10.n_valid_days.eq(1)
    w10.to_csv(OUT/'01_LST_semanal_definitivo_2015_2025.csv',index=False,encoding='utf-8-sig')
    byyear=w10.groupby(['site','year']).agg(total_weeks=('week_end','size'),valid_weeks=('LST_p90_C','count'),one_day_weeks=('one_day_flag','sum'),mean_valid_days=('n_valid_days','mean')).reset_index()
    byyear['availability_pct']=100*byyear.valid_weeks/byyear.total_weeks
    byyear.to_csv(OUT/'04_cobertura_anual.csv',index=False,encoding='utf-8-sig')
    bymonth=w10.assign(month=w10.week_end.dt.month).groupby(['site','month']).agg(total_weeks=('week_end','size'),valid_weeks=('LST_p90_C','count'),one_day_weeks=('one_day_flag','sum')).reset_index()
    bymonth['availability_pct']=100*bymonth.valid_weeks/bymonth.total_weeks
    bymonth.to_csv(OUT/'05_cobertura_mensual.csv',index=False,encoding='utf-8-sig')
    sens=w.groupby(['site','coverage_threshold']).agg(total_weeks=('week_end','size'),valid_weeks=('LST_p90_C','count'),one_day_weeks=('n_valid_days',lambda v:int((v==1).sum()))).reset_index()
    sens['missing_weeks']=sens.total_weeks-sens.valid_weeks
    sens['valid_fraction']=sens.valid_weeks/sens.total_weeks
    sens.to_csv(OUT/'02_resumen_sensibilidad_validado.csv',index=False,encoding='utf-8-sig')
    # Reconciliación contra el resumen aportado
    joined=sens.merge(s,on=['site','coverage_threshold'],suffixes=('_calc','_original'),how='outer',indicator=True)
    differences=0
    for field in ['total_weeks','valid_weeks','one_day_weeks','missing_weeks','valid_fraction']:
        differences+=int((~np.isclose(joined[field+'_calc'],joined[field+'_original'],equal_nan=True,atol=ATOL,rtol=0)).sum())
    alert('Discrepancias con resumen original',differences,'Cinco columnas por combinación zona-umbral')
    extremes=d[d.LST_C.notna()].copy()
    extremes['apto_10pct']=extremes.coverage_fraction.ge(0.10)
    extremes['extremo_revisar']=extremes.LST_C.lt(0)|extremes.LST_C.gt(55)
    extremes=extremes[extremes.extremo_revisar].sort_values(['site','date'])
    extremes.to_csv(OUT/'06_temperaturas_extremas_diarias.csv',index=False,encoding='utf-8-sig')
    alert('Extremos diarios aptos con 10 %',int(extremes.apto_10pct.sum()),'LST inferior a 0°C o superior a 55°C; revisión, no exclusión automática')
    alert('Semanas de un único día (10 %)',int(w10.one_day_flag.sum()),'Indicador de incertidumbre, no error')
    alert('Semanas sin datos (10 %)',int(w10.LST_p90_C.isna().sum()),'No imputar con cero')
    pd.DataFrame(alerts).to_csv(OUT/'07_controles_validacion.csv',index=False,encoding='utf-8-sig')
    print('VALIDACIÓN TERMINADA')
    print('Días:',len(d),'Filas semanales:',len(w),'Semanas al 10 %:',len(w10))
    print('Recalculo, incidencias:',len(checks),'Resumen, discrepancias:',differences)
    print(sens.to_string(index=False))
    print('Extremos diarios aptos al 10 %:',int(extremes.apto_10pct.sum()))
    print('Semanas un solo día al 10 %:',int(w10.one_day_flag.sum()))
    print('Resultados:',OUT)

if __name__=='__main__':
    main()