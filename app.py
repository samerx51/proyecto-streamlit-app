import streamlit as st
import pandas as pd
import requests
import os
from io import BytesIO

# -------------------------------
# CONFIG
# -------------------------------
st.set_page_config(page_title="Estadísticas Policiales Chile", layout="wide")
st.title("📊 Estadísticas Policiales en Chile — Dashboard Interactivo")

API_DATASETS = {
    "Victimas": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=285a2c22-9301-4456-9e18-9fd8dbb1c6f2",
    "Controles de identidad": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=69b8c48b-1d64-4296-8275-f3d2abfe1f0e",
    "Denuncias": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=c4675051-558b-42d7-ad15-87f4bb6ee458",
    "Delitos y faltas investigadas": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=b9bdcf46-f717-4dd0-8022-52e2ce3f4080",
    "Personas detenidas": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=9afe42af-034f-4859-a479-c3b25eed49b9"
}

DATA_FOLDER = "data"

# -------------------------------
# FUNCIONES
# -------------------------------
def fetch_api(url):
    try:
        records = []
        offset = 0
        limit = 1000
        while True:
            params = {"limit": limit, "offset": offset}
            resp = requests.get(url, params=params, timeout=20).json()
            batch = resp["result"]["records"]
            if not batch:
                break
            records.extend(batch)
            if len(batch) < limit:
                break
            offset += limit
        return pd.DataFrame(records)
    except:
        return pd.DataFrame()

def load_csv(path):
    try:
        return pd.read_csv(path, encoding="utf-8")
    except:
        return pd.read_csv(path, encoding="latin-1")

def listar_csvs():
    if not os.path.exists(DATA_FOLDER):
        return []
    return sorted([f for f in os.listdir(DATA_FOLDER) if f.endswith(".csv")])

def normalizar(df):
    df.columns = df.columns.str.lower().str.replace(" ", "_")
    return df

# -------------------------------
# SIDEBAR: Fuente
# -------------------------------
st.sidebar.header("📁 Fuente de datos")
fuente = st.sidebar.radio("Selecciona origen:", ["API", "CSV"])

if fuente == "API":
    sel = st.sidebar.selectbox("Dataset API", list(API_DATASETS.keys()))
    df = fetch_api(API_DATASETS[sel])
else:
    archivos = listar_csvs()
    if archivos:
        archivo_sel = st.sidebar.selectbox("CSV local", archivos)
        df = load_csv(os.path.join(DATA_FOLDER, archivo_sel))
    else:
        st.stop()

if df.empty:
    st.error("No se pudo cargar el dataset.")
    st.stop()

df = normalizar(df)

# ---------------------------------------------------------
# 🔧 CONVERSIÓN AUTOMÁTICA COLUMNAS NUM
