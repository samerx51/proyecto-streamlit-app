import streamlit as st
import pandas as pd
import requests
import os
from io import BytesIO
from typing import Dict
import plotly.express as px

st.set_page_config(page_title="Estadísticas Policiales Chile", layout="wide")
st.title("📊 Estadísticas Policiales — Análisis Interactivo")

# -----------------------------------------------------------
# CONFIG: APIs
# -----------------------------------------------------------
API_DATASETS: Dict[str, str] = {
    "Victimas": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=285a2c22-9301-4456-9e18-9fd8dbb1c6f2",
    "Controles de identidad": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=69b8c48b-1d64-4296-8275-f3d2abfe1f0e",
    "Denuncias": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=c4675051-558b-42d7-ad15-87f4bb6ee458",
    "Delitos y faltas investigadas": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=b9bdcf46-f717-4dd0-8022-52e2ce3f4080",
    "Personas detenidas": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=9afe42af-034f-4859-a479-c3b25eed49b9"
}

DATA_FOLDER = "data"

# -----------------------------------------------------------
# FUNCIONES
# -----------------------------------------------------------
@st.cache_data(show_spinner=True)
def fetch_api_all_records(url: str, page_limit: int = 1000) -> pd.DataFrame:
    """ Descarga todos los registros desde API CKAN. """
    records = []
    offset = 0

    while True:
        resp = requests.get(url, params={"limit": page_limit, "offset": offset}, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        batch = data.get("result", {}).get("records", [])
        if not batch:
            break

        records.extend(batch)
        offset += len(batch)

        if len(batch) < page_limit:
            break

    df = pd.DataFrame(records)
    return df


@st.cache_data
def load_csv_local(path: str) -> pd.DataFrame:
    try:
        return pd.read_csv(path, encoding="utf-8")
    except:
        return pd.read_csv(path, encoding="latin-1")


def listar_csvs(folder: str = DATA_FOLDER):
    if not os.path.exists(folder):
        return []
    return sorted([f for f in os.listdir(folder) if f.endswith(".csv")])


def normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_").replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u").replace("ñ","n")
                  for c in df.columns]
    return df


def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return buf.getvalue()

# -----------------------------------------------------------
# SIDEBAR — SELECCIÓN DE DATOS
# -----------------------------------------------------------
st.sidebar.header("📁 Fuente de datos")

modo = st.sidebar.radio("Seleccionar origen:", ["API", "CSV"])

df = pd.DataFrame()
dataset_name = None

if modo == "API":
    dataset_name = st.sidebar.selectbox("Dataset API", list(API_DATASETS.keys()))
    if dataset_name:
        with st.spinner("Descargando datos desde API..."):
            df = fetch_api_all_records(API_DATASETS[dataset_name])

else:
    archivos = listar_csvs()
    if archivos:
        archivo_sel = st.sidebar.selectbox("CSV disponible", archivos)
        if archivo_sel:
            df = load_csv_local(os.path.join(DATA_FOLDER, archivo_sel))
            dataset_name = archivo_sel
    else:
        st.sidebar.warning("No hay CSV en carpeta /data")

# -----------------------------------------------------------
# VALIDACIÓN
# -----------------------------------------------------------
if df.empty:
    st.warning("No se cargaron datos. Selecciona una fuente válida.")
    st.stop()

df = normalizar_columnas(df)
df = df.fillna(0)

# -----------------------------------------------------------
# DETECCIÓN DE COLUMNAS
# -----------------------------------------------------------
num_cols = [c for c in df.select_dtypes(include="number").columns if c != "_id"]
cat_cols = df.select_dtypes(include="object").columns.tolist()

# -----------------------------------------------------------
# EXPLORACIÓN RÁPIDA
# -----------------------------------------------------------
st.subheader("📌 Vista previa")
st.dataframe(df.head(20), use_container_width=True)

# -----------------------------------------------------------
# RANKING DE CATEGORÍAS
# -----------------------------------------------------------
st.subheader("🏆 Ranking — Categorías más frecuentes")

cols_candidatas = ["delito", "tipo_delito", "comuna", "region", "categoria"]

col_rank = None
for c in cols_candidatas:
    if c in df.columns:
        col_rank = c
        break

if col_rank:
    conteo = df[col_rank].value_counts().head(10)
    fig = px.bar(conteo, x=conteo.index, y=conteo.values,
                 title=f"Top categorías en '{col_rank}'")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No se encontraron columnas categóricas estándar.")

# -----------------------------------------------------------
# GRÁFICOS INTERACTIVOS
# -----------------------------------------------------------
st.subheader("📊 Gráficos interactivos")

if num_cols:
    colnum = st.selectbox("Selecciona columna numérica", num_cols)

    fig2 = px.line(df, y=colnum, title=f"Tendencia de {colnum}")
    st.plotly_chart(fig2, use_container_width=True)

else:
    st.info("No se detectan columnas numéricas útiles.")

# -----------------------------------------------------------
# ANÁLISIS ANUAL
# -----------------------------------------------------------
anio_cols = [c for c in df.columns if "año" in c or "anio" in c or "year" in c]

if anio_cols and num_cols:
    col_a = anio_cols[0]
    df[col_a] = pd.to_numeric(df[col_a], errors="coerce").fillna(0).astype(int)

    anual = df.groupby(col_a)[num_cols].sum()

    st.subheader("📈 Tendencia anual (suma total)")
    fig3 = px.line(anual.sum(axis=1), title="Casos totales por año")
    st.plotly_chart(fig3, use_container_width=True)

# -----------------------------------------------------------
# DESCARGAR
# -----------------------------------------------------------
st.subheader("⬇️ Descargar datos")
st.download_button("Descargar CSV", df_to_csv_bytes(df),
                   file_name=f"{dataset_name}_procesado.csv",
                   mime="text/csv")
