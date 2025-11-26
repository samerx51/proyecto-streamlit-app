import requests
import pandas as pd

# API de datos.gob.cl (delitos / denuncias)
API_URL = "https://datos.gob.cl/api/3/action/datastore_search?resource_id=18b1d53d-7e52-4a1e-bf8e-55b206389757&limit=20000"

def obtener_datos_delitos():
    response = requests.get(API_URL)
    data = response.json()

    records = data["result"]["records"]

    df = pd.DataFrame(records)

    # Normalizamos tipos
    df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce")
    df["mes"] = pd.to_numeric(df["mes"], errors="coerce")

    return df


def filtrar_por_region_y_mes(df, region):
    df_region = df[df["region"] == region]
    df_final = df_region.groupby("mes")["cantidad"].sum().reset_index()
    return df_final
