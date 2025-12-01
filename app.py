import streamlit as st
import pandas as pd
import requests

st.title("📊 Proyecto Estadísticas Policiales PDI")

# ------------------------------
# 1. CONFIGURACIÓN DE APIS Y CSV
# ------------------------------

API_DATASETS = {
    "Delitos Violentos": "https://api-pdi/delitos_violentos",
    "Delitos Económicos": "https://api-pdi/delitos_economicos",
    "Delitos Sexuales": "https://api-pdi/delitos_sexuales",
}

CSV_DATASETS = {
    "Delitos 2022": "delitos_2022.csv",
    "Delitos 2023": "delitos_2023.csv",
    "Delitos 2024": "delitos_2024.csv",
}

# ------------------------------
# 2. SELECTOR DE FUENTE DE DATOS
# ------------------------------

st.sidebar.header("Opciones")

fuente = st.sidebar.radio(
    "Selecciona la fuente de datos:",
    ["API", "CSV"]
)

if fuente == "API":
    dataset = st.sidebar.selectbox("Selecciona API", list(API_DATASETS.keys()))
else:
    dataset = st.sidebar.selectbox("Selecciona CSV", list(CSV_DATASETS.keys()))

# ------------------------------
# 3. CARGA DE DATOS
# ------------------------------

def cargar_api(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return pd.DataFrame(response.json())
    except Exception as e:
        st.error(f"Error cargando API: {e}")
        return pd.DataFrame()

def cargar_csv(file):
    try:
        return pd.read_csv(file)
    except Exception as e:
        st.error(f"Error cargando CSV: {e}")
        return pd.DataFrame()

# Cargar datos final según selección
if fuente == "API":
    df = cargar_api(API_DATASETS[dataset])
else:
    df = cargar_csv(CSV_DATASETS[dataset])

st.success("Datos cargados correctamente ✔️")

# Mostrar dataset cargado
st.subheader("Vista general del dataset cargado")
st.write(df)

# ------------------------------
# 3.1 EXPLORACIÓN INICIAL
# ------------------------------

st.header("📌 Exploración inicial de los datos")

st.subheader("Primeras filas")
st.write(df.head())

st.subheader("Información del dataset")
st.write(df.describe(include="all"))

st.subheader("Tipos de datos por columna")
st.write(df.dtypes)

st.subheader("Valores faltantes por columna")
st.write(df.isna().sum())


