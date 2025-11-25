import requests
import pandas as pd

API_URL = "https://datos.gob.cl/api/3/action/datastore_search"
RESOURCE_ID = "4aa6ff22-e93f-42e8-8fc7-d5016b61a89f"

def get_police_data(limit=5000):
    params = {
        "resource_id": RESOURCE_ID,
        "limit": limit
    }

    response = requests.get(API_URL, params=params)

    if response.status_code != 200:
        raise Exception(f"Error API: {response.status_code}")

    data = response.json()

    records = data["result"]["records"]
    
    df = pd.DataFrame(records)
    return df

if __name__ == "__main__":
    df = get_police_data()
    print(df.head())
