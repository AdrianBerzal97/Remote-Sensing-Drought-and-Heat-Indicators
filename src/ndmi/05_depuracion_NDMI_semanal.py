# -*- coding: utf-8 -*-
"""Depuración exploratoria de NDMI y agregación semanal 2015-2025.

Lee 02_datos_diagnosticados.csv generado por el diagnóstico anterior.
No altera datos originales. Usa cobertura relativa, NO cobertura geométrica real.
En días con varias escenas, elige provisionalmente la de más píxeles
válidos (no equivale a mosaicar píxeles). Reemplazar por mosaico en GEE
para un producto espacial definitivo.
"""
from pathlib import Path
import numpy as np
import pandas as pd

CARPETA_DATOS = Path(r"E:\Index\Scripts\scripts_historicos_2015_2025\scripts_historicos_2015_2025\datos_historicos")
ENTRADA = CARPETA_DATOS / 'diagnostico_NDMI' / '02_datos_diagnosticados.csv'
SALIDA = CARPETA_DATOS / 'NDMI_semanal_depurado'
SALIDA.mkdir(parents=True, exist_ok=True)

UMBRAL_RELATIVO = 0.10  # Exploratorio; comparar en sensibilidad con 0.05, 0.20
FECHA_INICIO = '2015-01-04'  # Primer domingo de 2015
FECHA_FIN = '2025-12-28'     # Último domingo de 2025

df = pd.read_csv(ENTRADA, sep=';', decimal=',', encoding='utf-8-sig')
for c in ['NDMI', 'valid_pixels', 'fraccion_relativa_pixeles']:
    df[c] = pd.to_numeric(df[c], errors='coerce')
df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.normalize()

# Motivos de exclusión; se conservan todas las filas en el registro.
df['motivo_exclusion'] = ''
df.loc[df['date'].isna(), 'motivo_exclusion'] += 'fecha_invalida;'
df.loc[df['NDMI'].isna(), 'motivo_exclusion'] += 'NDMI_ausente;'
df.loc[df['NDMI'].notna() & ~df['NDMI'].between(-1, 1), 'motivo_exclusion'] += 'NDMI_fuera_rango;'
df.loc[df['valid_pixels'].fillna(0) <= 0, 'motivo_exclusion'] += 'sin_pixeles_validos;'
df.loc[df['fraccion_relativa_pixeles'].isna() | (df['fraccion_relativa_pixeles'] < UMBRAL_RELATIVO), 'motivo_exclusion'] += 'cobertura_relativa_baja;'
df['apto'] = df['motivo_exclusion'].eq('')

# Selección provisional de una escena por día y zona.
validos = df[df['apto']].copy()
validos = validos.sort_values(['site', 'date', 'valid_pixels', 'image_id'], ascending=[True, True, False, True])
validos['elegida_en_fecha'] = ~validos.duplicated(['site', 'date'], keep='first')
seleccion = validos[validos['elegida_en_fecha']].copy()

df['elegida_en_fecha'] = False
df.loc[seleccion.index, 'elegida_en_fecha'] = True

domingos = pd.date_range(FECHA_INICIO, FECHA_FIN, freq='W-SUN')
filas = []
for zona in sorted(df['site'].dropna().unique()):
    zona_diaria = seleccion[seleccion['site'] == zona].copy()
    for domingo in domingos:
        inicio = domingo - pd.Timedelta(days=13)
        ventana = zona_diaria[(zona_diaria['date'] >= inicio) & (zona_diaria['date'] <= domingo)]
        filas.append({
            'site': zona,
            'week_end_sunday': domingo.date().isoformat(),
            'window_start': inicio.date().isoformat(),
            'window_end': domingo.date().isoformat(),
            'NDMI_min_14d': ventana['NDMI'].min() if len(ventana) else np.nan,
            'n_dias_validos_14d': len(ventana),
            'n_escenas_aceptadas_14d': len(validos[(validos['site'] == zona) & (validos['date'] >= inicio) & (validos['date'] <= domingo)]),
            'sin_datos_14d': len(ventana) == 0,
            'metodo_duplicados': 'escena_con_mas_pixeles_validos',
            'umbral_cobertura_relativa': UMBRAL_RELATIVO
        })

semanal = pd.DataFrame(filas)
resumen = df.groupby('site').agg(
    escenas_originales=('NDMI', 'size'),
    escenas_aptas=('apto', 'sum'),
    fechas_seleccionadas=('elegida_en_fecha', 'sum')
).reset_index()
resumen_semanal = semanal.groupby('site').agg(
    semanas=('sin_datos_14d', 'size'),
    semanas_sin_datos=('sin_datos_14d', 'sum')
).reset_index()
resumen = resumen.merge(resumen_semanal, on='site')

for nombre, tabla in [
    ('01_registro_depuracion.csv', df),
    ('02_escenas_diarias_seleccionadas.csv', seleccion),
    ('03_NDMI_semanal_14dias.csv', semanal),
    ('04_resumen_depuracion.csv', resumen)
]:
    tabla.to_csv(SALIDA / nombre, sep=';', decimal=',', index=False, encoding='utf-8-sig')

print('\nRESUMEN DE DEPURACIÓN')
print(resumen.to_string(index=False))
print('\nResultados guardados en:', SALIDA)
print('NOTA: selección diaria provisional; para resultado espacial definitivo, mosaicar escenas en GEE.')