import streamlit as st
import pandas as pd
import requests
import os

st.set_page_config(page_title="Estadísticas PDI", layout="wide")
st.title("📊 Plataforma Interactiva — Estadísticas Policiales en Chile")

# ================================
# 🔧 CONFIGURACIÓN
# ================================
API_DATASETS = {
    "Delitos y faltas investigadas": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=b9bdcf46-f717-4dd0-8022-52e2ce3f4080",
    "Denuncias": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=c4675051-558b-42d7-ad15-87f4bb6ee458",
}

DATA_FOLDER = "data"

# ================================
# 🔧 FUNCIONES
# ================================
@st.cache_data
def fetch_api(url: str, page_limit: int = 1000):
    records = []
    offset = 0
    while True:
        resp = requests.get(url, params={"limit": page_limit, "offset": offset}, timeout=20)
        data = resp.json()
        batch = data.get("result", {}).get("records", [])
        if not batch:
            break
        records.extend(batch)
        offset += len(batch)
        if len(batch) < page_limit:
            break
    return pd.DataFrame(records)

def listar_csvs(folder="data"):
    if not os.path.exists(folder):
        return []
    return [f for f in os.listdir(folder) if f.lower().endswith(".csv")]

def normalizar(df):
    df.columns = (
        df.columns
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("á", "a")
        .str.replace("é", "e")
        .str.replace("í", "i")
        .str.replace("ó", "o")
        .str.replace("ú", "u")
        .str.replace("ñ", "n")
    )
    return df

def detectar_numericas(df):
    """Convierte columnas numéricas que vengan como texto"""
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="ignore")
    return df

# ================================
# 📁 SELECCIÓN DE FUENTE
# ================================
st.sidebar.header("Fuente de datos")
fuente = st.sidebar.radio("Selecciona origen:", ["API", "CSV local"])

df = pd.DataFrame()

if fuente == "API":
    dataset = st.sidebar.selectbox("Dataset disponible", list(API_DATASETS.keys()))
    if dataset:
        with st.spinner("Descargando datos..."):
            df = fetch_api(API_DATASETS[dataset])

else:
    archivos = listar_csvs()
    if not archivos:
        st.sidebar.error("No hay CSV dentro de /data")
    else:
        archivo_sel = st.sidebar.selectbox("Selecciona CSV", archivos)
        df = pd.read_csv(f"data/{archivo_sel}", low_memory=False)

# ================================
# 🔍 VALIDACIÓN
# ================================
if df.empty:
    st.warning("No se cargaron datos")
    st.stop()

df = normalizar(df)
df = detectar_numericas(df)
df = df.fillna(0)

st.success("Datos cargados correctamente ✔")

# ================================
# 👀 EXPLORACIÓN SIMPLE
# ================================
st.subheader("👀 Vista rápida del dataset")
st.dataframe(df.head(20), use_container_width=True)

# ================================
# 🏆 RANKING CATEGÓRICO
# ================================
st.header("🏆 Ranking — Categorías más frecuentes")

# Buscar columnas categóricas útiles
categoricas = [
    c for c in df.colum
