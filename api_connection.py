import requests
import pandas as pd

API_URL = "https://datos.gob.cl/api/3/action/datastore_search"
RESOURCE_ID = "18b1d53d-7e52-4a1e-bf8e-55b206389757"

def get_police_data(limit=5000):
    """
    Obtiene datos policiales desde la API oficial de datos.gob.cl
    Retorna un DataFrame de pandas.
    """
    params = {
        "resource_id": RESOURCE_ID,
        "limit": limit
    }

    response = requests.get(API_URL, params=params)

    # Manejo de errores
    if response.status_code != 200:
        raise Exception(f"Error en la solicitud: {response.status_code}")

    data = response.json()

    if not data.get("success"):
        raise Exception("Error en respuesta del servidor")

    records = data["result"]["records"]
    return pd.DataFrame(records)

