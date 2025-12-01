import streamlit as st
import pandas as pd
import requests
import os
from io import BytesIO

# -----------------------------------------------------
# CONFIG
# -----------------------------------------------------
st.set_page_config(page_title="Estadísticas Policiales Chile", layout="wide")
st.title("📊 Estadísticas Policiales — Chile")

API_DATASETS = {
    "Victimas": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=285a2c22-9301-4456-9e18-9fd8dbb1c6f2",
    "Controles de identidad": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=69b8c48b-1d64-4296-8275-f3d2abfe1f0e",
    "Denuncias": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=c4675051-558b-42d7-ad15-87f4bb6ee458",
    "Delitos y faltas investigadas": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=b9bdcf46-f717-4dd0-8022-52e2ce3f4080",
    "Personas detenidas": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=9afe42af-034f-4859-a479-c3b25eed49b9"
}

DATA_FOLDER = "data"

# -----------------------------------------------------
# FUNCIONES
# -----------------------------------------------------
def cargar_api(url):
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()
        return pd.DataFrame(data["result"]["records"])
    except:
        return pd.DataFrame()

def cargar_csv(path):
    try:
        return pd.read_csv(path, encoding="utf-8", low_memory=False)
    except:
        return pd.read_csv(path, encoding="latin-1", low_memory=False)

def limpiar_columnas(df):
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace(".", "_")
    )
    return df

def convertir_numericas(df):
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="ignore")
    return df

def detectar_categoricas(df):
    posibles = ["delito", "tipo", "comuna", "region", "categoria"]
    return [c for c in df.columns if any(x in c for x in posibles)]

def detectar_numericas(df):
    cols = df.select_dtypes(include="number").columns.tolist()
    return [c for c in cols if c != "_id"]

# -----------------------------------------------------
# SIDEBAR
# -----------------------------------------------------
st.sidebar.header("Fuente de datos")
fuente = st.sidebar.radio("Selecciona origen", ["API", "CSV local"])

df = pd.DataFrame()

if fuente == "API":
    dataset = st.sidebar.selectbox("Dataset API", list(API_DATASETS.keys()))
    df = cargar_api(API_DATASETS[dataset])

else:
    archivos = [f for f in os.listdir(DATA_FOLDER) if f.endswith(".csv")]
    if archivos:
        archivo = st.sidebar.selectbox("CSV local", archivos)
        df = cargar_csv(os.path.join(DATA_FOLDER, archivo))
    else:
        st.warning("No hay CSV en /data")

# -----------------------------------------------------
# VALIDACIÓN
# -----------------------------------------------------
if df.empty:
    st.stop()

# -----------------------------------------------------
# LIMPIEZA BÁSICA
# -----------------------------------------------------
df = limpiar_columnas(df)
df = df.fillna(0)
df = convertir_numericas(df)

# -----------------------------------------------------
# EXPLORACIÓN
# -----------------------------------------------------
st.subheader("📌 Vista previa")
st.dataframe(df.head(20))

# -----------------------------------------------------
# RANKING AUTOMÁTICO
# -----------------------------------------------------
st.header("🏆 Ranking — Categorías más frecuentes")

categoricas = detectar_categoricas(df)

if categoricas:
    col_cat = st.selectbox("Columna categórica", categoricas)
    st.write(df[col_cat].value_counts().head(10))
else:
    st.warning("No se detectaron columnas categóricas relevantes.")

# -----------------------------------------------------
# GRÁFICOS INTERACTIVOS
# -----------------------------------------------------
st.header("📈 Gráficos interactivos")

numericas = detectar_numericas(df)

if len(numericas) == 0:
    st.error("⚠ No hay columnas numéricas (excepto _id).")
else:
    col_num = st.selectbox("Selecciona columna numérica", numericas)

    tipo = st.selectbox("Tipo de gráfico", ["Línea", "Barras", "Pie"])

    if tipo == "Línea":
        st.line_chart(df[col_num])

    elif tipo == "Barras":
        st.bar_chart(df[col_num])

    else:
        st.write(df[col_num].value_counts())
        st.pyplot()

# -----------------------------------------------------
# DESCARGA
# -----------------------------------------------------
st.header("⬇ Descargar datos filtrados")
csv = df.to_csv(index=False).encode("utf-8")
st.download_button("Descargar CSV", csv, "datos_limpios.csv")
