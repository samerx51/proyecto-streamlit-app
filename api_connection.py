import requests
import pandas as pd

def obtener_datos_api():
    url = "https://api-secure.datos.gob.cl/api/v2/catalog/datasets/delitos-2024/records?limit=100"  # ejemplo
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        records = data["records"]
        df = pd.json_normalize(records)
        return df
    else:
        print("Error en la solicitud:", response.status_code)
        return None
