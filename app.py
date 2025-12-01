import streamlit as st
import pandas as pd
import plotly.express as px

# -----------------------------------------------------------
# Cargar Datos
# -----------------------------------------------------------

@st.cache_data
def cargar_datos():
    ruta = "estadisticas_pdi.csv"  # <-- Ajusta el nombre si tu archivo se llama distinto
    df = pd.read_csv(ruta)
    return df

df = cargar_datos()

# -----------------------------------------------------------
# Configuración de la página
# -----------------------------------------------------------

st.set_page_config(
    page_title="Estadísticas Policiales PDI",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ Dashboard de Estadísticas Policiales – PDI")
st.write("Análisis interactivo basado en datos reales de la Policía de Investigaciones de Chile.")

# -----------------------------------------------------------
# Sidebar – Filtros
# -----------------------------------------------------------

st.sidebar.header("🔍 Filtros")

# Filtrar por región si existe la columna
if "REGIÓN" in df.columns:
    regiones = st.sidebar.multiselect(
        "Seleccionar Región",
        sorted(df["REGIÓN"].dropna().unique()),
        default=None
    )
    if regiones:
        df = df[df["REGIÓN"].isin(regiones)]

# Filtrar por año si existe la columna
if "AÑO" in df.columns:
    años = st.sidebar.multiselect(
        "Seleccionar Año",
        sorted(df["AÑO"].dropna().unique()),
        default=None
    )
    if años:
        df = df[df["AÑO"].isin(años)]

# -----------------------------------------------------------
# Sección Estadísticas Generales
# -----------------------------------------------------------

st.subheader("📊 Estadísticas Generales")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Total de Registros", len(df))

# Campos comunes para sumar si existen
campos_suma = ["DETENIDOS", "DENUNCIAS", "INCAUTACIONES"]

for campo in campos_suma:
    if campo not in df.columns:
        df[campo] = 0

with col2:
    st.metric("Total de Detenidos", int(df["DETENIDOS"].sum()))

with col3:
    st.metric("Total de Denuncias", int(df["DENUNCIAS"].sum()))

# -----------------------------------------------------------
# Gráfico 1: Denuncias por Región
# -----------------------------------------------------------

if "REGIÓN" in df.columns and "DENUNCIAS" in df.columns:
    st.subheader("📍 Denuncias por Región")
    graf1 = px.bar(
        df.groupby("REGIÓN")["DENUNCIAS"].sum().reset_index(),
        x="REGIÓN",
        y="DENUNCIAS",
        title="Denuncias Totales por Región"
    )
    st.plotly_chart(graf1, use_container_width=True)

# -----------------------------------------------------------
# Gráfico 2: Evolución de Detenidos por Año
# -----------------------------------------------------------

if "AÑO" in df.columns and "DETENIDOS" in df.columns:
    st.subheader("📈 Evolución de Detenidos por Año")
    graf2 = px.line(
        df.groupby("AÑO")["DETENIDOS"].sum().reset_index(),
        x="AÑO",
        y="DETENIDOS",
        markers=True,
        title="Detenidos Totales por Año"
    )
    st.plotly_chart(graf2, use_container_width=True)

# -----------------------------------------------------------
# Tabla Explorable
# -----------------------------------------------------------

st.subheader("📄 Tabla de Datos")
st.dataframe(df, use_container_width=True)

# -----------------------------------------------------------
# Análisis Automático: Columnas Numéricas y Categóricas
# -----------------------------------------------------------

st.subheader("📌 Análisis Automático de Columnas")

numericas = df.select_dtypes(include=["int64", "float64"]).columns.tolist()

categoricas = [
    col for col in df.columns
    if df[col].dtype == "object" and df[col].nunique() <= 50
]  # <-- AQUÍ estaba el error | AHORA CERRADO COMPLETAMENTE ✔✔✔

st.write("### Columnas Numéricas")
st.write(numericas)

st.write("### Columnas Categóricas")
st.write(categoricas)

# -----------------------------------------------------------
# Selector de Análisis
# -----------------------------------------------------------

st.subheader("📊 Análisis Personalizado")

col_x = st.selectbox("Seleccionar variable X", df.columns)
col_y = st.selectbox("Seleccionar variable Y", df.columns)

if st.button("Generar Gráfico"):
