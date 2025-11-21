import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Estadísticas PDI", layout="wide")
st.title("📊 Dashboard de Estadísticas Policiales — PDI")

# 📂 Carpeta donde guardas los CSV
DATA_FOLDER = "data"

# Leemos todos los archivos .csv
archivos = [f for f in os.listdir(DATA_FOLDER) if f.endswith(".csv")]

st.sidebar.header("📁 Selección de archivo")
archivo_seleccionado = st.sidebar.selectbox("Elige un dataset", archivos)

# Cargar el CSV seleccionado
df = pd.read_csv(os.path.join(DATA_FOLDER, archivo_seleccionado))

st.subheader(f"Mostrando datos de: `{archivo_seleccionado}`")
st.dataframe(df.head())

# ---------------------------
# 🔍 FILTRADO BÁSICO
# ---------------------------

st.header("🔍 Buscador y Filtros")

columna = st.selectbox("Selecciona una columna para buscar", df.columns)
valor = st.text_input("Ingresa texto a buscar")

if valor:
    resultado = df[df[columna].astype(str).str.contains(valor, case=False, na=False)]
    st.write(f"Resultados encontrados: {len(resultado)}")
    st.dataframe(resultado)

# ---------------------------
# 📊 GRÁFICO AUTOMÁTICO
# ---------------------------

st.header("📊 Gráfico Automático (Columnas numéricas)")
columnas_num = df.select_dtypes(include="number").columns

if len(columnas_num) > 0:
    columna_grafico = st.selectbox("Columna para graficar", columnas_num)

    st.line_chart(df[columna_grafico])
else:
    st.warning("Este dataset no tiene columnas numéricas para graficar.")
