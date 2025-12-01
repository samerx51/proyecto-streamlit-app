import streamlit as st
import pandas as pd
import requests
import os
from io import BytesIO
from typing import Dict

# --------------------------------------
# CONFIGURACIÓN GENERAL
# --------------------------------------
st.set_page_config(page_title="Estadísticas Policiales Chile", layout="wide")
st.title("📊 Panel Interactivo — Estadísticas Policiales en Chile")

# --------------------------------------
# CONFIG: APIs disponibles
# --------------------------------------
API_DATASETS: Dict[str, str] = {
    "Victimas": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=285a2c22-9301-4456-9e18-9fd8dbb1c6f2",
    "Controles de identidad": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=69b8c48b-1d64-4296-8275-f3d2abfe1f0e",
    "Denuncias": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=c4675051-558b-42d7-ad15-87f4bb6ee458",
    "Delitos y faltas investigadas": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=b9bdcf46-f717-4dd0-8022-52e2ce3f4080",
    "Personas detenidas": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=9afe42af-034f-4859-a479-c3b25eed49b9"
}

DATA_FOLDER = "data"

# --------------------------------------
# FUNCIONES DE CARGA
# --------------------------------------
@st.cache_data(show_spinner=False)
def fetch_api(url: str, limit: int = 1000) -> pd.DataFrame:
    """Descarga todos los registros desde la API con paginación."""
    registros = []
    offset = 0

    try:
        while True:
            params = {"limit": limit, "offset": offset}
            resp = requests.get(url, params=params)
            data = resp.json()["result"]["records"]

            if not data:
                break

            registros.extend(data)
            offset += len(data)

            if len(data) < limit:
                break

        return pd.DataFrame(registros)

    except:
        return pd.DataFrame()

def load_csv_local(path: str) -> pd.DataFrame:
    try:
        return pd.read_csv(path, encoding="utf-8", low_memory=False)
    except:
        return pd.read_csv(path, encoding="latin-1", low_memory=False)

def list_csvs():
    if not os.path.exists(DATA_FOLDER):
        return []
    return [f for f in os.listdir(DATA_FOLDER) if f.endswith(".csv")]

def normalize_cols(df: pd.DataFrame):
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df

def df_to_csv(df):
    buf = BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()

# --------------------------------------
# SIDEBAR: Selección de datos
# --------------------------------------
st.sidebar.header("📁 Selección de datos")

source = st.sidebar.radio("Fuente:", ["API (datos.gob.cl)", "CSV local"])

df = pd.DataFrame()
dataset_name = None

if source == "API (datos.gob.cl)":
    dataset_name = st.sidebar.selectbox("Dataset disponible", list(API_DATASETS.keys()))
    if dataset_name:
        url = API_DATASETS[dataset_name]
        with st.spinner("Descargando datos desde API..."):
            df = fetch_api(url)

else:
    archivos = list_csvs()
    if archivos:
        dataset_name = st.sidebar.selectbox("Archivo CSV", archivos)
        df = load_csv_local(os.path.join(DATA_FOLDER, dataset_name))
    else:
        st.sidebar.warning("No hay archivos CSV en /data.")

if df.empty:
    st.warning("No se pudieron cargar datos.")
    st.stop()

df = normalize_cols(df)
df = df.fillna(0)

# --------------------------------------
# DASHBOARD PRINCIPAL
# --------------------------------------
st.header("📌 Vista rápida del dataset")
st.dataframe(df.head(20))

# Identificar columnas útiles
num_cols = df.select_dtypes(include="number").columns.tolist()
text_cols = df.select_dtypes(include="object").columns.tolist()

# --------------------------------------
# FILTROS
# --------------------------------------
st.subheader("🔎 Filtros")

col1, col2 = st.columns(2)

with col1:
    col_text = st.selectbox("Columna para búsqueda", text_cols)
    text_filter = st.text_input("Buscar texto")

with col2:
    year_cols = [c for c in df.columns if "año" in c or "anio" in c or "year" in c]
    selected_year = None
    if year_cols:
        ycol = year_cols[0]
        years = sorted(df[ycol].unique())
        selected_year = st.selectbox("Filtrar por año", ["Todos"] + list(years))

df_filtered = df.copy()

if text_filter:
    df_filtered = df_filtered[df_filtered[col_text].astype(str).str.contains(text_filter, case=False)]

if selected_year and selected_year != "Todos":
    df_filtered = df_filtered[df_filtered[ycol] == selected_year]

st.write(f"Resultados: {len(df_filtered)} filas")
st.dataframe(df_filtered.head(50))

# --------------------------------------
# SECCIÓN DE GRÁFICOS INTERACTIVOS
# --------------------------------------
st.header("📊 Gráficos interactivos")

if num_cols:
    graf_col = st.selectbox("Selecciona columna numérica", num_cols)
    tipo_graf = st.radio("Tipo de gráfico", ["Línea", "Barras"])

    if tipo_graf == "Línea":
        st.line_chart(df_filtered[graf_col])
    else:
        st.bar_chart(df_filtered[graf_col])
else:
    st.info("No hay columnas numéricas para graficar.")

# --------------------------------------
# 🔥 NUEVA SECCIÓN: TOP DELITOS / TOP CATEGORÍAS
# --------------------------------------
st.header("🔝 Ranking — categorías más frecuentes")

cat_cols = ["delito", "tipo_delito", "comuna", "categoria", "region"]
col_cat = None

for c in cat_cols:
    if c in df.columns:
        col_cat = c
        break

if col_cat:
    top = df[col_cat].value_counts().head(10)
    st.subheader(f"Top categorías según '{col_cat}'")
    st.bar_chart(top)
else:
    st.info("No hay columnas categóricas estándar (tipo_delito/comuna/etc).")

# --------------------------------------
# 🔥 NUEVA SECCIÓN: TENDENCIA ANUAL
# --------------------------------------
if year_cols:
    st.header("📈 Tendencia anual")
    ycol = year_cols[0]
    df[ycol] = pd.to_numeric(df[ycol], errors="coerce").fillna(0).astype(int)
    tendencia = df.groupby(ycol)[num_cols].sum()
    st.line_chart(tendencia.sum(axis=1))

# --------------------------------------
# DESCARGA
# --------------------------------------
st.header("⬇️ Descargar datos filtrados")
st.download_button(
    "Descargar CSV",
    data=df_to_csv(df_filtered),
    file_name=f"{dataset_name}_filtrado.csv",
    mime="text/csv"
)
