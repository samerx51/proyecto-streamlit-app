from api_connection import get_data
import streamlit as st

st.title("Análisis Estadísticas Policiales - Chile")

df = get_data()

st.write("Datos obtenidos desde la API:")
st.dataframe(df)
