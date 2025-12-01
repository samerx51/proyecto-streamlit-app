import streamlit as st
import pandas as pd
import requests
import os
from io import BytesIO
from typing import Dict, Any

st.set_page_config(page_title="Estadísticas Policiales Chile", layout="wide")
st.title("📊 Estadísticas Policiales en Chile — PDI & datos.gob.cl")

# ----------------------------
# CONFIG: APIs - reemplaza/añade si necesitas
# ----------------------------
API_DATASETS: Dict[str, str] = {
    "Victimas": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=285a2c22-9301-4456-9e18-9fd8dbb1c6f2",
    "Controles de identidad": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=69b8c48b-1d64-4296-8275-f3d2abfe1f0e",
    "Denuncias": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=c4675051-558b-42d7-ad15-87f4bb6ee458",
    "Delitos y faltas investigadas": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=b9bdcf46-f717-4dd0-8022-52e2ce3f4080",
    "Personas detenidas": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=9afe42af-034f-4859-a479-c3b25eed49b9"
}

DATA_FOLDER = "data"

# ----------------------------
# UTIL: funciones de carga
# ----------------------------
@st.cache_data(show_spinner=False)
def fetch_api_all_records(base_url: str, page_limit: int = 1000) -> pd.DataFrame:
    """
    Descarga todos los registros de una API tipo CKAN/datastore_search
    usando paginación con 'limit' y 'offset'.
    """
    records = []
    offset = 0
    params = {"limit": page_limit, "offset": offset}
    try:
        # extraer resource_id si la URL ya lo trae; base_url puede contener params
        while True:
            params["offset"] = offset
            resp = requests.get(base_url, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            batch = data.get("result", {}).get("records", [])
            if not batch:
                break
            records.extend(batch)
            offset += len(batch)
            # seguridad: si el batch es menor que page_limit, terminamos
            if len(batch) < page_limit:
                break
        df = pd.DataFrame(records)
        return df
    except Exception as e:
        # devolvemos DataFrame vacío en caso de fallo (la app mostrará la advertencia)
        st.error(f"Error descargando datos desde la API: {e}")
        return pd.DataFrame()

@st.cache_data
def load_csv_local(path: str) -> pd.DataFrame:
    # intenta utf-8, si falla intenta latin-1
    try:
        return pd.read_csv(path, encoding="utf-8", low_memory=False)
    except Exception:
        return pd.read_csv(path, encoding="latin-1", low_memory=False)

def listar_csvs(folder: str = DATA_FOLDER):
    if not os.path.exists(folder):
        return []
    return sorted([f for f in os.listdir(folder) if f.lower().endswith(".csv")])

def normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df

def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return buf.getvalue()

# ----------------------------
# BARRA LATERAL: escoger fuente
# ----------------------------
st.sidebar.header("📁 Fuente de datos")
fuente = st.sidebar.radio("Origen de datos:", ("API (datos.gob.cl)", "CSV local (carpeta /data)"))

df = pd.DataFrame()
dataset_name = None

if fuente == "API (datos.gob.cl)":
    st.sidebar.info("Selecciona el dataset de datos.gob.cl (cuando selecciones, se descargan los registros).")
    dataset_name = st.sidebar.selectbox("Dataset (API)", list(API_DATASETS.keys()))
    if dataset_name:
        url = API_DATASETS[dataset_name]
        with st.spinner(f"Descargando datos desde API: {dataset_name} ..."):
            df = fetch_api_all_records(url, page_limit=1000)

else:
    st.sidebar.info("Selecciona un CSV que hayas subido a la carpeta /data/")
    archivos = listar_csvs()
    if not archivos:
        st.sidebar.warning("No hay archivos CSV en /data/. Súbelos a GitHub y espera a que el deploy se actualice.")
    else:
        archivo_sel = st.sidebar.selectbox("CSV local", archivos)
        if archivo_sel:
            ruta = os.path.join(DATA_FOLDER, archivo_sel)
            df = load_csv_local(ruta)
            dataset_name = archivo_sel

# ----------------------------
# Validación y normalización
# ----------------------------
if df is None or (isinstance(df, pd.DataFrame) and df.empty):
    st.warning("No se cargaron datos desde la fuente seleccionada. Revisa la barra lateral.")
    st.stop()

df = normalizar_columnas(df)

# ----------------------------
# EXPLORACIÓN INICIAL (esto te permite ver exactamente las columnas)
# ----------------------------
st.header("📌 Exploración inicial de los datos")
st.subheader("Primeras filas")
st.write(df.head(10))

st.subheader("Nombres de columnas")
st.write(list(df.columns))

st.subheader("Información del dataset (describe)")
# mostramos describe solo si hay columnas numéricas o mixtas
with st.expander("Ver resumen estadístico (describe)"):
    try:
        st.write(df.describe(include="all").T)
    except Exception as e:
        st.write("No se pudo generar describe:", e)

st.subheader("Tipos de datos por columna")
st.write(df.dtypes)

st.subheader("Valores faltantes por columna")
st.write(df.isna().sum())

# ----------------------------
# BUSCADOR Y FILTROS
# ----------------------------
st.header("🔎 Buscador y filtros")

cols = list(df.columns)
# columna para búsqueda de texto
col_buscar = st.selectbox("Columna para buscar (texto)", cols, index=0)
texto = st.text_input("Texto a buscar (filtra en la columna seleccionada)")

df_filtrado = df.copy()
if texto:
    df_filtrado = df_filtrado[df_filtrado[col_buscar].astype(str).str.contains(texto, case=False, na=False)]

# filtrado por año si existe columna 'año' o 'anio' o 'year'
anio_cols = [c for c in cols if "año" in c or "anio" in c or "year" in c]
if anio_cols:
    c_anio = anio_cols[0]
    años = sorted(df[c_anio].dropna().unique())
    if len(años) > 0:
        año_sel = st.sidebar.selectbox("Filtrar por año", ["Todos"] + [str(x) for x in años])
        if año_sel != "Todos":
            df_filtrado = df_filtrado[df_filtrado[c_anio].astype(str) == año_sel]

st.write(f"Resultados (filtrados): {len(df_filtrado)}")
st.dataframe(df_filtrado.head(200))

# ----------------------------
# GRÁFICOS AUTOMÁTICOS Y ANÁLISIS
# ----------------------------
st.header("📊 Visualizaciones rápidas")

# si existen columnas numéricas, permitir graficar
num_cols = df_filtrado.select_dtypes(include="number").columns.tolist()
if num_cols:
    col_graf = st.selectbox("Columna numérica para graficar", num_cols)
    tipo_graf = st.selectbox("Tipo de gráfico", ["Línea", "Barras"])
    if tipo_graf == "Línea":
        st.line_chart(df_filtrado[col_graf])
    else:
        st.bar_chart(df_filtrado[col_graf])
else:
    st.info("No se detectaron columnas numéricas para graficar. Si tus datos vienen en columnas por mes (enero,febrero,...), puedes pivotearlos — dime si quieres que agregue esa transformación.")

# ----------------------------
# DESCARGA
# ----------------------------
st.header("⬇️ Descargar datos filtrados")
csv_bytes = df_to_csv_bytes(df_filtrado)
st.download_button("Descargar CSV filtrado", data=csv_bytes, file_name=f"{(dataset_name or 'dataset')}_filtrado.csv", mime="text/csv")

# ----------------------------
# AYUDA / NOTAS
# ----------------------------
st.markdown("---")
st.info(
    "Notas:\n"
    "- Si al conectar la API ves columnas como 'enero','febrero', etc., eso significa que el dataset está en formato ancho (meses como columnas). "
    "Si quieres ver los tipos de delitos por fila (formato largo), puedo agregar una transformación (melt/pivot) para normalizar. "
)
st.caption("Si quieres que convierta columnas por mes a formato largo (tipo_delito, mes, valor), escribe: 'pivot meses' y lo agrego.")
