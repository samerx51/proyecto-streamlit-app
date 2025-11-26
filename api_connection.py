import requests
import pandas as pd

API_URL = "https://datos.gob.cl/api/3/action/datastore_search"
RESOURCE_ID = "18b1d53d-7e52-4a1e-bf8e-55b206389757"

def get_data(limit=5000):
    params = {
        "resource_id": RESOURCE_ID,
        "limit": limit
    }

    response = requests.get(API_URL, params=params)

    if response.status_code != 200:
        raise Exception(f"Error en petición: {response.status_code}")

    data = response.json()

    if not data.get("success", False):
        raise Exception("La API no devolvió datos exitosamente")

    records = data["result"]["records"]
    df = pd.DataFrame(records)

    return df
