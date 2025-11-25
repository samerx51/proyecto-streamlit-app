# api_connection.py
"""
Módulo simple para realizar consultas GET a APIs REST y devolver JSON/pandas.DataFrame.
Diseñado para uso didáctico en el proyecto: permite conectar APIs públicas
(de forma genérica) y transformarlas en DataFrames para análisis.
"""

import requests
import pandas as pd
from typing import Optional, Dict, Any

def fetch_json(url: str, params: Optional[Dict[str,Any]] = None, headers: Optional[Dict[str,str]] = None, timeout: int = 10):
    """
    Realiza GET a `url` con params y headers opcionales. Devuelve el JSON (parsed).
    Lanza excepción si el status no es 200.
    """
    resp = requests.get(url, params=params, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()

def json_to_df(json_obj, path_to_records: Optional[str] = None) -> pd.DataFrame:
    """
    Convierte un JSON a DataFrame.
    - Si el JSON contiene una clave con la lista de registros, indicar path_to_records (ej: 'result.records').
    - Si json_obj ya es una lista de dicts, lo convierte directamente.
    """
    if path_to_records:
        # path tipo 'result.records' -> lo convertimos en navegación
        cur = json_obj
        for key in path_to_records.split('.'):
            cur = cur.get(key, {})
        records = cur
    else:
        # si es dict con única lista interna trátalo automáticamente
        if isinstance(json_obj, dict):
            # busca la primera lista que parezca registros
            lists = [v for v in json_obj.values() if isinstance(v, list)]
            records = lists[0] if lists else []
        else:
            records = json_obj

    return pd.DataFrame(records)

# Ejemplo de función preparada para API tipo datos.gob.cl u otras que devuelvan 'records'
def fetch_from_api_to_df(url: str, params: Optional[Dict[str,Any]] = None, records_path: Optional[str] = None) -> pd.DataFrame:
    json_data = fetch_json(url, params=params)
    df = json_to_df(json_data, path_to_records=records_path)
    return df
