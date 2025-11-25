# app.py
import streamlit as st
import os
import pandas as pd

from api_connection import fetch_from_api_to_df
from utils.data_processing import load_all_csvs, normalize_column_names, basic_clean

st.set_page_config(page_title="Estadísticas PDI", layout="wide")
st.title("📊 Dashboard de Estadísticas Policiales — PDI")

DATA_FOLDER = "data"

# --- Cargar CSVs disponibles ---
csvs = load_all_csvs(DATA_FOLDER)
archivos = list(csvs.keys())

st.sidebar.header("📁 Selección de datos")
fuente = st.sidebar.radio("Fuente", ["CSV local", "Cargar desde API (demo)"])

if fuente == "CSV local":
    archivo_seleccionado = st.sidebar.selectbox("Elige un dataset", archivos)
    df = csvs[archivo_seleccionado].copy()
    df = normalize_column_names(df)
else:
    st.sidebar.info("Ejemplo de carga desde API público (ejecuta solo si configuras la URL)")
    api_url = st.sidebar.text_input("API URL (GET)", "")
    if st.sidebar.button("Cargar desde API"):
        if api_url:
            try:
                df = fetch_from_api_to_df(api_url)
            except Exception as e:
                st.sidebar.error(f"Error al consultar API: {e}")
                df = pd.DataFrame()
        else:
            st.sidebar.warning("Ingresa una URL válida.")
    else:
        st.info("Para usar la opción API, pega una URL pública y presiona 'Cargar desde API'.")
        df = pd.DataFrame()

# Si el df está vacío mostramos mensaje
if df is None or df.empty:
    st.warning("No hay datos cargados. Selecciona un CSV o carga una API.")
    st.stop()

# Limpieza básica (opcional)
st.sidebar.header("Limpieza rápida")
if st.sidebar.checkbox("Normalizar nombres de columnas", value=True):
    df = normalize_column_names(df)

# Mostrar esquema
st.subheader(f"Mostrando datos: {len(df)} filas — columnas: {list(df.columns)}")
st.dataframe(df.head(10))

# Buscador rápido
st.header("🔍 Buscador y filtros")
columna = st.selectbox("Selecciona una columna para buscar", df.columns)
valor = st.text_input("Ingresa texto a buscar (usa parte del texto)")

if valor:
    mask = df[columna].astype(str).str.contains(valor, case=False, na=False)
    resultado = df[mask]
    st.write(f"Resultados encontrados: {len(resultado)}")
    st.dataframe(resultado)
    st.download_button("📥 Descargar resultados filtrados (CSV)", resultado.to_csv(index=False), file_name="resultados_filtrados.csv")
else:
    st.write("Ingresa un texto para filtrar.")

# Gráficos básicos (si hay columnas numéricas)
st.header("📊 Gráficos automáticos")
num_cols = df.select_dtypes(include="number").columns.tolist()
if num_cols:
    col_graf = st.selectbox("Columna numérica para graficar", num_cols)
    st.line_chart(df[col_graf])
else:
    st.info("No se encontraron columnas numéricas para graficar en este dataset.")
