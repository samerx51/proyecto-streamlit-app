import streamlit as st
import pandas as pd
import requests
import os
from io import BytesIO

# ----------------------
# CONFIG
# ----------------------
st.set_page_config(page_title="Estadísticas Policiales Chile", layout="wide")
st.title("Estadísticas Policiales en Chile — PDI & Seguridad Pública")

# APIs disponibles desde datos.gob.cl
API_DATASETS = {
    "Victimas": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=285a2c22-9301-4456-9e18-9fd8dbb1c6f2",
    "Controles de identidad": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=69b8c48b-1d64-4296-8275-f3d2abfe1f0e",
    "Denuncias": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=c4675051-558b-42d7-ad15-87f4bb6ee458",
    "Delitos y faltas investigadas": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=b9bdcf46-f717-4dd0-8022-52e2ce3f4080",
    "Personas detenidas": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=9afe42af-034f-4859-a479-c3b25eed49b9"
}

DATA_FOLDER = "data"

# ----------------------
# FUNCIONES
# ----------------------
def cargar_api(url):
    try:
        respuesta = requests.get(url)
        respuesta.raise_for_status()
        data = respuesta.json()
        registros = data["result"]["records"]
        return pd.DataFrame(registros)
    except Exception as e:
        st.error(f"Error al conectar con API: {e}")
        return pd.DataFrame()

def cargar_csv_local(path):
    try:
        return pd.read_csv(path, encoding="utf-8", low_memory=False)
    except:
        return pd.read_csv(path, encoding="latin-1", low_memory=False)

def listar_csvs():
    if not os.path.exists(DATA_FOLDER):
        return []
    return sorted([f for f in os.listdir(DATA_FOLDER) if f.endswith(".csv")])

def normalizar_columnas(df):
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    return df
st.header("📌 Exploración inicial de los datos")

st.subheader("Primeras filas")
st.write(df.head())

st.subheader("Información del dataset")
st.write(df.describe(include="all"))

st.subheader("Tipos de datos por columna")
st.write(df.dtypes)

st.subheader("Valores faltantes por columna")
st.write(df.isna().sum())


def convertir_csv(df):
    buffer = BytesIO()
    df.to_csv(buffer, index=False)
    return buffer.getvalue()

# ----------------------
# SIDEBAR - selección de fuente
# ----------------------
st.sidebar.header("Fuente de datos")

fuente = st.sidebar.radio(
    "Seleccionar origen de información:",
    ["API (datos.gob.cl)", "CSV Local (carpeta /data)"]
)

df = None

# ----------------------
# Cargar desde API
# ----------------------
if fuente == "API (datos.gob.cl)":
    dataset = st.sidebar.selectbox("Selecciona un dataset", API_DATASETS.keys())
    url = API_DATASETS[dataset]
    df = cargar_api(url)

# ----------------------
# Cargar desde CSV local
# ----------------------
else:
    archivos = listar_csvs()
    if archivos:
        archivo_sel = st.sidebar.selectbox("Selecciona un archivo CSV", archivos)
        ruta = os.path.join(DATA_FOLDER, archivo_sel)
        df = cargar_csv_local(ruta)
    else:
        st.warning("No hay archivos CSV en la carpeta /data")

# ----------------------
# Validación
# ----------------------
if df is None or df.empty:
    st.stop()

df = normalizar_columnas(df)

# ----------------------
# MOSTRAR TABLA
# ----------------------
st.subheader("📄 Vista previa del dataset")
st.write(f"Filas: {df.shape[0]} — Columnas: {df.shape[1]}")
st.dataframe(df.head(20))

# ----------------------
# FILTROS
# ----------------------
st.header("🔍 Filtros")

columna_filtro = st.selectbox("Selecciona columna para buscar", df.columns)
texto = st.text_input("Texto a buscar")

df_filtrado = df.copy()

if texto:
    df_filtrado = df[df[columna_filtro].astype(str).str.contains(texto, case=False, na=False)]

# Filtro por año si existe
columnas_anio = [c for c in df.columns if "año" in c or "anio" in c or "year" in c]

if columnas_anio:
    col_anio = columnas_anio[0]
    años = sorted(df[col_anio].dropna().unique())
    año_sel = st.sidebar.selectbox("Filtrar por año", ["Todos"] + list(años))
    if año_sel != "Todos":
        df_filtrado = df_filtrado[df_filtrado[col_anio] == año_sel]

st.write(f"Resultados encontrados: {len(df_filtrado)}")
st.dataframe(df_filtrado)

# ----------------------
# GRÁFICO AUTOMÁTICO
# ----------------------
st.header("Visualización")

num_cols = df_filtrado.select_dtypes(include="number").columns.tolist()

if num_cols:
    col_graf = st.selectbox("Selecciona columna numérica para graficar", num_cols)
    st.line_chart(df_filtrado[col_graf])
else:
    st.info("No hay columnas numéricas disponibles para graficar.")

# ----------------------
# DESCARGA
# ----------------------
st.header("⬇️ Descargar datos filtrados")
st.download_button(
    "Descargar CSV",
    data=convertir_csv(df_filtrado),
    file_name="datos_filtrados.csv",
    mime="text/csv"
)

st.caption("Proyecto Streamlit — Seguridad Pública Chile")

