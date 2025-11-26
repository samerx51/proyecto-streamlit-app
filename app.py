import streamlit as st
from api_connection import get_data

st.title("Estadísticas Policiales en Chile - PDI ✅")

st.write("Datos obtenidos desde datos.gob.cl usando API CKAN")

try:
    df = get_data()
    st.success("✅ Datos cargados correctamente desde la API")

    st.write("### Vista previa de los datos")
    st.dataframe(df)

except Exception as e:
    st.error(f"Error al obtener datos: {e}")
