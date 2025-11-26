import streamlit as st
import matplotlib.pyplot as plt
from grafico import obtener_datos_delitos, filtrar_por_region_y_mes

st.title("Estadísticas Policiales de Chile")
st.write("Visualización de delitos por región y por mes usando datos reales de datos.gob.cl")

# Obtener datos desde la API
df = obtener_datos_delitos()

# Selector de región
regiones = sorted(df["region"].unique())
region_seleccionada = st.selectbox("Selecciona una región", regiones)

# Filtrar datos
df_filtrado = filtrar_por_region_y_mes(df, region_seleccionada)

# Mostrar DataFrame
st.write("Datos filtrados:")
st.dataframe(df_filtrado)

# Gráfico
plt.figure(figsize=(10,5))
plt.plot(df_filtrado["mes"], df_filtrado["cantidad"])
plt.xlabel("Mes")
plt.ylabel("Cantidad de delitos")
plt.title(f"Delitos por mes - Región {region_seleccionada}")
st.pyplot(plt)
