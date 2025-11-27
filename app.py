import streamlit as st
import pandas as pd
import requests

# 1️⃣ Diccionario con APIs — va SIEMPRE ARRIBA
API_DATASETS = {
    "Victimas": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=285a2c22-9301-4456-9e18-9fd8dbb1c6f2",
    "Controles de identidad": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=69b8c48b-1d64-4296-8275-f3d2abfe1f0e",
    "Denuncias": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=c4675051-558b-42d7-ad15-87f4bb6ee458",
    "Delitos y faltas investigadas": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=b9bdcf46-f717-4dd0-8022-52e2ce3f4080",
    "Personas detenidas": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=9afe42af-034f-4859-a479-c3b25eed49b9"
}

# 2️⃣ Función para cargar datos desde la API
def cargar_datos(url):
    respuesta = requests.get(url)

    if respuesta.status_code == 200:
        data = respuesta.json()
        registros = data["result"]["records"]
        return pd.DataFrame(registros)
    else:
        st.error("No se pudieron obtener los datos desde la API")
        return pd.DataFrame()

# 3️⃣ INTERFAZ STREAMLIT
st.title("📊 Estadísticas Policiales en Chile")

# Selector de delito
delito_seleccionado = st.selectbox(
    "Selecciona un tipo de delito:",
    list(API_DATASETS.keys())
)

# Obtener URL correspondiente
url = API_DATASETS[delito_seleccionado]

# Llamada a la API
df = cargar_datos(url)

# Mostrar datos
st.subheader(f"Datos sobre {delito_seleccionado}")
st.dataframe(df)

