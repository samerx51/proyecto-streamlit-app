# utils/data_processing.py
import os
import pandas as pd
from typing import List

def list_csv_files(data_folder: str = "data") -> List[str]:
    return [f for f in os.listdir(data_folder) if f.lower().endswith(".csv")]

def load_csv(path: str, encoding: str = "utf-8", **kwargs) -> pd.DataFrame:
    return pd.read_csv(path, encoding=encoding, low_memory=False, **kwargs)

def load_all_csvs(data_folder: str = "data") -> dict:
    """
    Carga todos los CSVs de data_folder y devuelve dict nombre->DataFrame
    """
    files = list_csv_files(data_folder)
    dfs = {}
    for f in files:
        full = os.path.join(data_folder, f)
        try:
            dfs[f] = load_csv(full)
        except Exception as e:
            print(f"Error cargando {f}: {e}")
    return dfs

def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza nombres: minusculas, espacios->_, quita acentos básicos
    """
    df = df.copy()
    new_cols = []
    for c in df.columns:
        c2 = str(c).strip().lower().replace(" ", "_")
        # reemplazo básico de acentos
        c2 = (c2.replace("á","a").replace("é","e").replace("í","i")
                  .replace("ó","o").replace("ú","u").replace("ñ","n"))
        new_cols.append(c2)
    df.columns = new_cols
    return df

def try_parse_dates(df: pd.DataFrame, date_cols: list):
    df = df.copy()
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df

def coerce_numeric(df: pd.DataFrame, numeric_cols: list):
    df = df.copy()
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

def basic_clean(df: pd.DataFrame, date_cols: list = [], numeric_cols: list = []):
    df = normalize_column_names(df)
    if date_cols:
        df = try_parse_dates(df, date_cols)
    if numeric_cols:
        df = coerce_numeric(df, numeric_cols)
    return df
def resumen_general(df: pd.DataFrame) -> pd.DataFrame:
    """Entrega conteo, promedio, mínimo, máximo y desviación estándar."""
    return df.describe(include="all").transpose()


def delitos_mas_frecuentes(df: pd.DataFrame, col_delito: str, col_total: str, n: int = 10):
    """Devuelve los delitos más reportados."""
    if col_delito not in df.columns or col_total not in df.columns:
        return pd.DataFrame()
    return (
        df.groupby(col_delito)[col_total]
        .sum()
        .sort_values(ascending=False)
        .head(n)
        .reset_index()
    )


def ranking_por_region(df: pd.DataFrame, col_region: str, col_total: str):
    """Ordena regiones según cantidad de delitos."""
    if col_region not in df.columns or col_total not in df.columns:
        return pd.DataFrame()
    return (
        df.groupby(col_region)[col_total]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )


def evolucion_anual(df: pd.DataFrame, col_anio: str, col_total: str):
    """Crea serie temporal anual."""
    if col_anio not in df.columns or col_total not in df.columns:
        return pd.DataFrame()
    return (
        df.groupby(col_anio)[col_total]
        .sum()
        .sort_values()
        .reset_index()
    )

