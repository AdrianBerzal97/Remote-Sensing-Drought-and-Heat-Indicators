# -*- coding: utf-8 -*-
"""NDMI Landsat 8/9 Collection 2 L2, 2015-2025.
IMPORTANTE: el NDMI original 2024-25 se obtuvo con Sentinel-2 SR.
Esta serie Landsat es una alternativa consistente para 2015-25; NO es idéntica.
"""
import os
import ee
import pandas as pd
from pathlib import Path

PROJECT = 'incendios-491211'
START_DATE = '2014-12-15'  # margen para ventana óptica inicial
END_DATE = '2026-01-01'  # fin exclusivo
OUTPUT_FOLDER = Path(__file__).resolve().parent / 'datos_historicos'
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
SITES = {
    'Salamanca': 'projects/incendios-491211/assets/Salamanca_Grid',
    'Avila': 'projects/incendios-491211/assets/Avila_Grid',
    'Caceres': 'projects/incendios-491211/assets/Caceres_Grid_Final',
}

def mask_and_indices(image, satellite):
    qa = image.select('QA_PIXEL')
    good = qa.bitwiseAnd(1 << 0).eq(0)  # fill
    for bit in (1, 2, 3, 4, 5):
        good = good.And(qa.bitwiseAnd(1 << bit).eq(0))
    good = good.And(image.select('QA_RADSAT').eq(0))
    nir = image.select('SR_B5').multiply(0.0000275).add(-0.2)
    swir = image.select('SR_B6').multiply(0.0000275).add(-0.2)
    red = image.select('SR_B4').multiply(0.0000275).add(-0.2)
    valid = nir.gt(0).And(swir.gt(0)).And(red.gt(0))
    ndmi = nir.subtract(swir).divide(nir.add(swir)).rename('NDMI')
    ndvi = nir.subtract(red).divide(nir.add(red)).rename('NDVI')
    return image.addBands([ndmi, ndvi]).updateMask(good.And(valid)).set('satellite', satellite)

def collection(geom):
    out = ee.ImageCollection([])
    for code, label in [('LC08', 'Landsat_8'), ('LC09', 'Landsat_9')]:
        c = (ee.ImageCollection(f'LANDSAT/{code}/C02/T1_L2')
             .filterDate(START_DATE, END_DATE).filterBounds(geom)
             .filter(ee.Filter.lt('CLOUD_COVER', 60))
             .map(lambda im, lab=label: mask_and_indices(im, lab)))
        out = out.merge(c)
    return out.sort('system:time_start')

def main():
    ee.Initialize(project=PROJECT)
    for site, asset in SITES.items():
        geom = ee.FeatureCollection(asset).geometry()
        coll = collection(geom)
        def extract(im):
            vals = im.select(['NDMI','NDVI']).reduceRegion(
                reducer=ee.Reducer.mean(), geometry=geom, scale=30, maxPixels=1e9)
            count = im.select('NDMI').reduceRegion(
                reducer=ee.Reducer.count(), geometry=geom, scale=30, maxPixels=1e9)
            return ee.Feature(None, vals).set({
                'date': ee.Date(im.get('system:time_start')).format('YYYY-MM-dd'),
                'site': site, 'satellite': im.get('satellite'),
                'valid_pixels': count.get('NDMI'), 'image_id': im.id()})
        # Exportación por año para evitar transferencias masivas getInfo()
        for year in range(2014, 2026):
            start = max(f'{year}-01-01', START_DATE)
            end = min(f'{year+1}-01-01', END_DATE)
            fc = ee.FeatureCollection(coll.filterDate(start, end).map(extract))
            records = [f['properties'] for f in fc.getInfo()['features']]
            path = OUTPUT_FOLDER / f'{site}_indices_{year}.csv'
            pd.DataFrame(records, columns=['site','date','satellite','image_id','valid_pixels','NDVI','NDMI']).to_csv(path,index=False,encoding='utf-8-sig')
            print(site,year,len(records),path)
    print('Extracción NDMI completada. Revisar disponibilidad y comparación con Sentinel-2.')

if __name__ == '__main__': main()


# ============================================================
# DIAGNÓSTICO HISTÓRICO NDMI - ÁVILA, SALAMANCA Y CÁCERES
# ============================================================

from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# 1. CONFIGURACIÓN
# CAMBIA ESTA RUTA por la carpeta que contiene tus CSV.
CARPETA_DATOS = Path(r"E:\Index\Scripts\scripts_historicos_2015_2025\scripts_historicos_2015_2025\datos_historicos")

CARPETA_SALIDA = CARPETA_DATOS / "diagnostico_NDMI"
CARPETA_SALIDA.mkdir(parents=True, exist_ok=True)

ZONAS = ["Avila", "Salamanca", "Caceres"]
ANIO_INICIO = 2015
ANIO_FIN = 2025

# Umbrales exploratorios de alerta (NO son criterios
# científicamente calibrados de exclusión).
UMBRAL_PIXELES_RELATIVO = 0.10
UMBRAL_NDMI_EXTREMO = 0.60

resumen_anual = []
registros = []
archivos_ausentes = []

# 2. LECTURA DE LOS CSV ANUALES
for zona in ZONAS:
    for anio in range(ANIO_INICIO, ANIO_FIN + 1):

        archivo = CARPETA_DATOS / f"{zona}_indices_{anio}.csv"

        if not archivo.exists():
            archivos_ausentes.append({
                "site": zona,
                "year": anio,
                "archivo": archivo.name
            })
            print(f"NO ENCONTRADO: {archivo.name}")
            continue

        df = pd.read_csv(archivo, encoding="utf-8-sig")

        columnas = [
            "date", "satellite", "image_id",
            "valid_pixels", "NDVI", "NDMI"
        ]

        for col in columnas:
            if col not in df.columns:
                df[col] = np.nan

        df["date"] = pd.to_datetime(
            df["date"], errors="coerce"
        )

        for col in ["valid_pixels", "NDVI", "NDMI"]:
            df[col] = pd.to_numeric(
                df[col], errors="coerce"
            )

        df["site"] = zona
        df["year"] = anio
        df["source_file"] = archivo.name

        registros.append(df)

        resumen_anual.append({
            "site": zona,
            "year": anio,
            "imagenes": len(df),
            "NDMI_validos": df["NDMI"].notna().sum(),
            "NDMI_ausentes": df["NDMI"].isna().sum(),
            "NDVI_ausentes": df["NDVI"].isna().sum(),
            "pixeles_cero": df["valid_pixels"].eq(0).sum(),
            "pixeles_mediana": df["valid_pixels"].median(),
            "pixeles_maximo": df["valid_pixels"].max(),
            "NDMI_min": df["NDMI"].min(),
            "NDMI_media": df["NDMI"].mean(),
            "NDMI_max": df["NDMI"].max(),
            "fechas_invalidas": df["date"].isna().sum(),
            "ids_duplicados": df["image_id"].dropna().duplicated().sum()
        })

if not registros:
    raise RuntimeError(
        "No se encontraron CSV. Comprueba CARPETA_DATOS."
    )

datos = pd.concat(registros, ignore_index=True)
resumen = pd.DataFrame(resumen_anual)

# 3. DIAGNÓSTICO DE COBERTURA
# Usamos como referencia exploratoria el máximo número
# de píxeles válidos observado dentro de cada zona.
# NO equivale a la cobertura real del polígono.
max_pixeles = datos.groupby("site")["valid_pixels"].transform("max")

datos["fraccion_relativa_pixeles"] = (
    datos["valid_pixels"] / max_pixeles.replace(0, np.nan)
)

datos["alerta_pocos_pixeles"] = (
    datos["fraccion_relativa_pixeles"]
    < UMBRAL_PIXELES_RELATIVO
)

# 4. DIAGNÓSTICO DE VALORES EXTREMOS
datos["alerta_NDMI_extremo"] = (
    datos["NDMI"].abs() > UMBRAL_NDMI_EXTREMO
)

# Atípicos estadísticos por zona, según regla 1.5 x IQR
datos["alerta_IQR"] = False

for zona in ZONAS:
    mascara = datos["site"] == zona
    valores = datos.loc[mascara, "NDMI"].dropna()

    if len(valores) < 4:
        continue

    q1 = valores.quantile(0.25)
    q3 = valores.quantile(0.75)
    iqr = q3 - q1

    if iqr > 0:
        limite_inf = q1 - 1.5 * iqr
        limite_sup = q3 + 1.5 * iqr

        datos.loc[mascara, "alerta_IQR"] = (
            (datos.loc[mascara, "NDMI"] < limite_inf) |
            (datos.loc[mascara, "NDMI"] > limite_sup)
        )

# 5. COMPROBAR DUPLICADOS
datos["fecha_duplicada"] = datos.duplicated(
    subset=["site", "date"],
    keep=False
)

datos["imagen_duplicada"] = datos.duplicated(
    subset=["site", "image_id"],
    keep=False
)

# 6. TABLA DE OBSERVACIONES QUE REQUIEREN REVISIÓN
alertas = datos[
    datos["alerta_pocos_pixeles"] |
    datos["alerta_NDMI_extremo"] |
    datos["alerta_IQR"] |
    datos["fecha_duplicada"] |
    datos["imagen_duplicada"] |
    datos["date"].isna()
].copy()

# 7. RESUMEN POR SATÉLITE
satelites = (
    datos.groupby(["site", "year", "satellite"], dropna=False)
    .agg(
        imagenes=("NDMI", "size"),
        NDMI_validos=("NDMI", "count"),
        NDMI_media=("NDMI", "mean")
    )
    .reset_index()
)

# 8. EXPORTAR RESULTADOS
resumen.to_csv(
    CARPETA_SALIDA / "01_resumen_anual.csv",
    sep=";", decimal=",", index=False,
    encoding="utf-8-sig"
)

datos.to_csv(
    CARPETA_SALIDA / "02_datos_diagnosticados.csv",
    sep=";", decimal=",", index=False,
    encoding="utf-8-sig"
)

alertas.to_csv(
    CARPETA_SALIDA / "03_observaciones_a_revisar.csv",
    sep=";", decimal=",", index=False,
    encoding="utf-8-sig"
)

satelites.to_csv(
    CARPETA_SALIDA / "04_resumen_satelites.csv",
    sep=";", decimal=",", index=False,
    encoding="utf-8-sig"
)

pd.DataFrame(archivos_ausentes).to_csv(
    CARPETA_SALIDA / "05_archivos_ausentes.csv",
    sep=";", index=False, encoding="utf-8-sig"
)

# 9. GRÁFICOS
for zona in ZONAS:
    z = datos[datos["site"] == zona].sort_values("date")

    if z.empty:
        continue

    fig, ax = plt.subplots(figsize=(12, 5))

    ax.scatter(
        z["date"], z["NDMI"],
        s=15, alpha=0.7, label="NDMI observado"
    )

    revisables = z[
        z["alerta_pocos_pixeles"] |
        z["alerta_NDMI_extremo"] |
        z["alerta_IQR"]
    ]

    ax.scatter(
        revisables["date"],
        revisables["NDMI"],
        s=45, marker="x",
        label="Observación a revisar"
    )

    ax.set_title(f"NDMI histórico - {zona}")
    ax.set_xlabel("Fecha")
    ax.set_ylabel("NDMI")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()

    fig.savefig(
        CARPETA_SALIDA / f"06_NDMI_{zona}.png",
        dpi=180
    )
    plt.close(fig)

# 10. RESUMEN EN CONSOLA
print("\n" + "=" * 60)
print("DIAGNÓSTICO HISTÓRICO NDMI FINALIZADO")
print("=" * 60)

print("\nResumen anual:")
print(
    resumen[
        ["site", "year", "imagenes",
         "NDMI_validos", "NDMI_ausentes",
         "NDMI_min", "NDMI_max"]
    ].to_string(index=False)
)

print("\nTotal de observaciones:", len(datos))
print("NDMI válidos:", datos["NDMI"].notna().sum())
print("NDMI ausentes:", datos["NDMI"].isna().sum())
print("Observaciones con alertas:", len(alertas))
print("Archivos ausentes:", len(archivos_ausentes))

print("\nResultados guardados en:")
print(CARPETA_SALIDA)