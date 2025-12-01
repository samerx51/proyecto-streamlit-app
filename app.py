import streamlit as st
import pandas as pd
import requests
import os
from io import BytesIO

# ---------------------------------------------------------
# CONFIGURACIÓN GENERAL
# ---------------------------------------------------------
st.set_page_config(page_title="Estadísticas Policiales Chile", layout="wide")
st.title("📊 Plataforma Interactiva — Estadísticas Policiales (PDI / datos.gob.cl)")

API_DATASETS = {
    "Victimas": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=285a2c22-9301-4456-9e18-9fd8dbb1c6f2",
    "Controles de identidad": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=69b8c48b-1d64-4296-8275-f3d2abfe1f0e",
    "Denuncias": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=c4675051-558b-42d7-ad15-87f4bb6ee458",
    "Delitos y faltas investigadas": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=b9bdcf46-f717-4dd0-8022-52e2ce3f4080",
    "Personas detenidas": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=9afe42af-034f-4859-a479-c3b25eed49b9"
}

DATA_FOLDER = "data"

# ---------------------------------------------------------
# FUNCIONES
# ---------------------------------------------------------
@st.cache_data
def fetch_api(url):
    """Descargar todos los registros de la API (con paginación)."""
    records = []
    offset = 0
    while True:
        resp = requests.get(url, params={"limit": 1000, "offset": offset})
        data = resp.json()
        batch = data.get("result", {}).get("records", [])
        if not batch:
            break
        records.extend(batch)
        offset += 1000
    return pd.DataFrame(records)

def load_local_csv(path):
    try:
        return pd.read_csv(path, encoding="utf-8", low_memory=False)
    except:
        return pd.read_csv(path, encoding="latin-1", low_memory=False)

def normalize(df: pd.DataFrame):
    df.columns = df.columns.str.lower().str.strip().str.replace(" ", "_")
    return df

def convert_months(df: pd.DataFrame):
    meses = ["enero","febrero","marzo","abril","mayo","junio","julio",
             "agosto","septiembre","octubre","noviembre","diciembre"]

    for m in meses:
        if m in df.columns:
            df[m] = pd.to_numeric(df[m], errors="coerce").fillna(0)

    return df

def list_csv():
    if not os.path.exists(DATA_FOLDER):
        return []
    return [f for f in os.listdir(DATA_FOLDER) if f.endswith(".csv")]

# ---------------------------------------------------------
# SIDEBAR - fuente de datos
# ---------------------------------------------------------
st.sidebar.header("📁 Fuente de datos")

source = st.sidebar.radio("Origen de datos", ["API (datos.gob.cl)", "CSV local"])

df = None

if source == "API (datos.gob.cl)":
    dataset = st.sidebar.selectbox("Selecciona dataset", list(API_DATASETS.keys()))
    df = fetch_api(API_DATASETS[dataset])
else:
    archivos = list_csv()
    if archivos:
        archivo = st.sidebar.selectbox("Selecciona CSV", archivos)
        df = load_local_csv(os.path.join(DATA_FOLDER, archivo))
    else:
        st.warning("No hay archivos CSV en /data.")

if df is None or df.empty:
    st.stop()

# ---------------------------------------------------------
# TRATAMIENTO Y NORMALIZACIÓN
# ---------------------------------------------------------
df = normalize(df)
df = df.fillna(0)
df = convert_months(df)

# Identificar tipos de columnas
num_cols = df.select_dtypes(include="number").columns.tolist()
cat_cols = df.select_dtypes(include="object").columns.tolist()

# ---------------------------------------------------------
# SECCIÓN 1 — Vista previa rápida
# ---------------------------------------------------------
st.subheader("📌 Vista rápida del dataset")
st.dataframe(df.head(20), use_container_width=True)

# ---------------------------------------------------------
# SECCIÓN 2 — Gráficos interactivos
# ---------------------------------------------------------
st.header("📈 Gráficos interactivos")

if num_cols:
    col = st.selectbox("Selecciona columna numérica", num_cols)
    tipo = st.radio("Tipo de gráfico", ["Línea", "Barras"], horizontal=True)

    if tipo == "Línea":
        st.line_chart(df[col])
    else:
        st.bar_chart(df[col])
else:
    st.warning("No existen columnas numéricas para graficar.")

# ---------------------------------------------------------
# SECCIÓN 3 — Ranking de delitos / categorías
# ---------------------------------------------------------
st.header("📊 Ranking de categorías más frecuentes")

if cat_cols:
    col_cat = st.selectbox("Selecciona columna categórica", cat_cols)
    ranking = df[col_cat].value_counts().head(10)

    st.write("Top 10 categorías")
    st.bar_chart(ranking)
else:
    st.info("No se detectaron columnas categóricas en este dataset.")

# ---------------------------------------------------------
# SECCIÓN 4 — Análisis anual si existe columna año
# ---------------------------------------------------------
anio_cols = [c for c in df.columns if "año" in c or "anio" in c or "year" in c]

if anio_cols:
    col_anio = anio_cols[0]
    df[col_anio] = pd.to_numeric(df[col_anio], errors="coerce").fillna(0)

    st.header("📅 Tendencia anual")
    anuales = df.groupby(col_anio)[num_cols].sum()
    st.line_chart(anuales.sum(axis=1))
else:
    st.info("El dataset no contiene columna de año.")

# ---------------------------------------------------------
# SECCIÓN 5 — Exportar datos filtrados
# ---------------------------------------------------------
st.header("⬇️ Descargar datos")
csv_bytes = df.to_csv(index=False).encode("utf-8")
st.download_button(
    "Descargar CSV",
    data=csv_bytes,
    file_name="datos_filtrados.csv",
    mime="text/csv"
)
