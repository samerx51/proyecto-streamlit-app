from api_connection import get_data
import streamlit as st

st.title("Análisis Estadísticas Policiales - Chile")

df = get_data()

st.write("Datos obtenidos desde la API:")
st.dataframe(df)

# Filtro por región
region = st.sidebar.selectbox(
    "Selecciona región",
    df["REGION UNIDAD PDI"].unique()
)

df_filtrado = df[df["REGION UNIDAD PDI"] == region]

st.write(f"Datos filtrados para la región: {region}")
st.dataframe(df_filtrado)
