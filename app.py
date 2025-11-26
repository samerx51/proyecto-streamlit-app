# app.py - Dashboard PDI (API + CSV) integrado y robusto
import streamlit as st
import pandas as pd
import os
from io import BytesIO

# IMPORTA TU FUNCIÓN DE api_connection.py
# Debe ser algo así: def get_data(...): -> pd.DataFrame
from api_connection import get_data as get_data_from_api

st.set_page_config(page_title="Estadísticas PDI", layout="wide")
st.title("📊 Análisis Estadísticas Policiales - Chile")

DATA_FOLDER = "data"

# ---------- Helpers ----------
@st.cache_data
def list_csv_files(folder=DATA_FOLDER):
    if not os.path.exists(folder):
        return []
    return sorted([f for f in os.listdir(folder) if f.lower().endswith(".csv")])

@st.cache_data
def load_local_csv(path):
    return pd.read_csv(path, encoding="utf-8", low_memory=False)

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    # Normaliza nombres de columnas a minúsculas y sin espacios para evitar KeyError
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df

def df_to_csv_bytes(df: pd.DataFrame):
    buf = BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return buf.getvalue()

# ---------- Fuente de datos ----------
st.sidebar.header("📁 Fuente de datos")
fuente = st.sidebar.radio("Selecciona fuente", ["API (datos.gob.cl)", "Local (CSV)"])

df = None
error_api = None

if fuente.startswith("API"):
    st.sidebar.info("Se intentará obtener datos desde la API pública (datos.gob.cl)")
    try:
        df_api = get_data_from_api()  # tu función en api_connection.py
        if not isinstance(df_api, pd.DataFrame):
            raise ValueError("La función get_data no devolvió un DataFrame.")
        df = normalize_columns(df_api)
    except Exception as e:
        error_api = e
        st.sidebar.error(f"No se pudo obtener datos desde la API: {e}")
        st.sidebar.warning("Puedes seleccionar 'Local (CSV)' para usar los archivos en /data/")

if df is None and fuente.startswith("Local"):
    archivos = list_csv_files()
    if not archivos:
        st.sidebar.error("No hay archivos CSV en la carpeta /data/. Súbelos al repo.")
    else:
        archivo_sel = st.sidebar.selectbox("Elige un CSV", archivos)
        ruta = os.path.join(DATA_FOLDER, archivo_sel)
        try:
            df_local = load_local_csv(ruta)
            df = normalize_columns(df_local)
        except Exception as e:
            st.sidebar.error(f"Error al leer el CSV: {e}")

# Si por fallo de API queremos ofrecer local igualmente:
if df is None and error_api is not None:
    archivos = list_csv_files()
    if archivos:
        st.sidebar.info("Cargando dataset local como respaldo")
        archivo_sel = st.sidebar.selectbox("CSV (respaldo)", archivos)
        ruta = os.path.join(DATA_FOLDER, archivo_sel)
        try:
            df_local = load_local_csv(ruta)
            df = normalize_columns(df_local)
        except Exception as e:
            st.sidebar.error(f"Error al leer CSV de respaldo: {e}")

# ---------- Interfaz principal ----------
if df is None:
    st.warning("No se ha cargado ningún dataset. Revisa la barra lateral.")
    st.stop()

st.subheader("Datos obtenidos")
st.write(f"Filas: {df.shape[0]}  —  Columnas: {df.shape[1]}")
st.dataframe(df.head(15))

# ---------- Filtros y buscador ----------
st.header("🔎 Buscador y filtros")
cols = list(df.columns)
col_buscar = st.selectbox("Selecciona columna para buscar (texto)", cols, index=0)
valor_buscar = st.text_input("Ingresa texto a buscar (enter para aplicar)")

df_filtrado = df.copy()
if valor_buscar:
    df_filtrado = df_filtrado[df_filtrado[col_buscar].astype(str).str.contains(valor_buscar, case=False, na=False)]

# Si existe columna año (anio) la usamos para filtrar por año -- pero sólo si existe
anio_cols = [c for c in cols if "anio" in c or "año" in c or "year" in c]
if anio_cols:
    c_anio = anio_cols[0]
    años = sorted(df[c_anio].dropna().unique())
    if len(años) > 0:
        año = st.sidebar.selectbox("Selecciona año (si aplica)", ["Todos"] + [str(x) for x in años])
        if año != "Todos":
            df_filtrado = df_filtrado[df_filtrado[c_anio].astype(str) == str(año)]

st.write(f"Resultados encontrados: {len(df_filtrado)}")
st.dataframe(df_filtrado.head(50))

# ---------- Gráficos automáticos ----------
st.header("📊 Gráfico automático (columnas numéricas)")
num_cols = df_filtrado.select_dtypes(include="number").columns.tolist()
if num_cols:
    col_graf = st.selectbox("Selecciona columna numérica para graficar", num_cols)
    st.line_chart(df_filtrado[col_graf])
else:
    st.info("No se detectaron columnas numéricas para graficar en este dataset.")

# ---------- Descargar resultado ----------
st.header("⬇️ Descargar resultados filtrados")
csv_bytes = df_to_csv_bytes(df_filtrado)
st.download_button("Descargar CSV", data=csv_bytes, file_name="resultados_filtrados.csv", mime="text/csv")

st.caption("Si quieres más visualizaciones (barras por región, series temporales, mapa, etc.), dime qué análisis deseas y lo agrego.")
