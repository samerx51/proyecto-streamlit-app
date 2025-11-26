from api_connection import get_data
import streamlit as st

st.title("Análisis Estadísticas Policiales - Chile")

df = get_data()

# Estandarizar nombres de columnas
df = df.rename(columns={"AÑO": "anio", "Year": "anio", "fecha": "anio"})

# Mostrar dataset completo
st.write("Datos obtenidos desde la API:")
st.dataframe(df)

# Filtros
st.sidebar.header("Filtros")

if "anio" in df.columns:
    anio = st.sidebar.selectbox("Selecciona año", sorted(df["anio"].unique()))
    df = df[df["anio"] == anio]
else:
    st.sidebar.error("La columna 'anio' no existe en el DataFrame")

# Mostrar resultados filtrados
st.subheader("Datos filtrados")
st.dataframe(df)
