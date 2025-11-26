from api_connection import get_data
import streamlit as st

st.title("Análisis Estadísticas Policiales - Chile")

df = get_data()

st.sidebar.header("Filtros")
año = st.sidebar.selectbox("Selecciona año", df["anio"].unique())
region = st.sidebar.multiselect("Región", df["region"].unique())

df_filtrado = df[
    (df["año"] == año) &
    (df["region"].isin(region) if region else True)
]

st.subheader("Datos filtrados")
st.dataframe(df_filtrado)

st.subheader("Casos por tipo de delito")
st.bar_chart(df_filtrado.groupby("delito")["casos"].sum())
