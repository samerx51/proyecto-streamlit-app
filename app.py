# app.py - Versión mejorada enfocada en gráficos interactivos y filtros
import streamlit as st
import pandas as pd
import requests
import os
from io import BytesIO
from typing import Dict, Any
import plotly.express as px

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
    """Descarga todos los registros de una API tipo CKAN/datastore_search con paginación."""
    records = []
    offset = 0
    params = {"limit": page_limit, "offset": offset}
    try:
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
            if len(batch) < page_limit:
                break
        return pd.DataFrame(records)
    except Exception as e:
        st.error(f"Error descargando datos desde la API: {e}")
        return pd.DataFrame()

@st.cache_data
def load_csv_local(path: str) -> pd.DataFrame:
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

# Lista de meses en español (normalizados)
MESES = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]

# ----------------------------
# BARRA LATERAL: escoger fuente y opciones de visualización
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
# Validación básica
# ----------------------------
if df is None or (isinstance(df, pd.DataFrame) and df.empty):
    st.warning("No se cargaron datos desde la fuente seleccionada. Revisa la barra lateral.")
    st.stop()

# Normalizar nombres de columnas
df = normalizar_columnas(df)

# ----------------------------
# Conversión y limpieza inicial
# ----------------------------
# Rellenar NA con 0 (lo pediste)
df = df.fillna(0)

# Intentar convertir columnas que parezcan numéricas
for c in df.columns:
    if df[c].dtype == object:
        # quitar puntos/espacios extras en números y comas decimales
        sample = df[c].astype(str).head(20).str.replace(r"[^\d\-,\.]", "", regex=True)
        # si la mayoría parecen números, convertir
        n_nums = sample.str.replace(",", "").str.replace("-", "").str.isnumeric().sum()
        if n_nums >= 3:
            df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", ""), errors='coerce').fillna(0)

# ----------------------------
# EXPLORACIÓN INICIAL (minimizada, porque quieres menos texto)
# ----------------------------
st.subheader("Vista previa")
st.dataframe(df.head(8))

# Mostrar lista de columnas (útil para que veas nombres exactos)
with st.expander("Columnas (ver)"):
    st.write(list(df.columns))

# ----------------------------
# Detectar columnas meses y opción de pivot
# ----------------------------
cols = list(df.columns)
month_cols = [c for c in cols if any(m in c for m in MESES)]

# Opción de pivot (ancho -> largo) para datasets que vengan por meses
pivot_opt = False
if month_cols:
    pivot_opt = st.sidebar.checkbox("Transformar columnas por mes a formato largo (pivot/melt)", value=True)

# ----------------------------
# Detectar columna categórica (mejor heurística)
# ----------------------------
possible_cat_names = ["delito","tipo_delito","categoria","categoria_delito","comuna","region","nombre_delito"]
cat_col = None
for name in possible_cat_names:
    if name in df.columns:
        cat_col = name
        break

# Si no encontramos, buscar la columna con más valores únicos y tipo object (pero no _id)
if cat_col is None:
    object_cols = [c for c in df.columns if df[c].dtype == object and c != "_id"]
    if object_cols:
        # elegimos la que tenga más valores únicos (pero no demasiados)
        uniq_counts = {c: df[c].nunique() for c in object_cols}
        cand = sorted(uniq_counts.items(), key=lambda x: x[1])
        # tomar la primera con unico <= 200 (evitar columnas identificadoras)
        for c, u in cand:
            if u <= 200:
                cat_col = c
                break

# ----------------------------
# Transformación pivot si aplica
# ----------------------------
df_display = df.copy()
if pivot_opt and month_cols:
    id_vars = [c for c in df.columns if c not in month_cols]
    df_display = df.melt(id_vars=id_vars, value_vars=month_cols, var_name="mes", value_name="valor_mes")
    # normalizar mes y valor
    df_display["mes"] = df_display["mes"].astype(str).str.strip().str.lower()
    df_display["valor_mes"] = pd.to_numeric(df_display["valor_mes"], errors="coerce").fillna(0)
    # si no hay cat_col originalmente, intentar asignar uno razonable
    if cat_col is None:
        # buscar alguna columna con pocos valores únicos
        for c in id_vars:
            if df[c].nunique() <= 200 and c != "_id":
                cat_col = c
                break

# ----------------------------
# Ranking — categorías más frecuentes
# ----------------------------
st.header("🏆 Ranking — Categorías más frecuentes")
if cat_col:
    try:
        if pivot_opt and month_cols:
            rank = df_display.groupby(cat_col)["valor_mes"].sum().sort_values(ascending=False)
        else:
            # sumar columnas numéricas por categoría si existen
            num_cols = df.select_dtypes(include="number").columns.tolist()
            if num_cols:
                rank = df.groupby(cat_col)[num_cols].sum().sum(axis=1).sort_values(ascending=False)
            else:
                rank = df[cat_col].value_counts()
        st.bar_chart(rank.head(10))
        st.write(rank.head(10))
    except Exception as e:
        st.error(f"Error generando ranking: {e}")
else:
    st.info("No se encontraron columnas claramente categóricas (tipo_delito/comuna/region).")

# ----------------------------
# Gráficos interactivos
# ----------------------------
st.header("📊 Gráficos interactivos")

# Preparo lista de columnas numéricas útiles (excluyo _id)
numeric_cols = [c for c in df_display.select_dtypes(include="number").columns if c != "_id"]
if numeric_cols:
    sel_num = st.selectbox("Selecciona columna numérica", numeric_cols)
    # Si pivot aplicado, hay 'valor_mes' y 'mes' que permiten hacer series por mes
    if pivot_opt and month_cols:
        # gráfico por categoría y mes
        if cat_col:
            cat_choice = st.selectbox("Selecciona categoría (para series)", [None] + sorted(df_display[cat_col].unique().tolist()))
            if cat_choice:
                sub = df_display[df_display[cat_col] == cat_choice]
            else:
                sub = df_display
            fig = px.line(sub.groupby("mes")[sel_num].sum().reindex(MESES).fillna(0).reset_index(), x="mes", y=sel_num, title=f"{sel_num} por mes")
            st.plotly_chart(fig, use_container_width=True)
        else:
            # solo serie por mes
            ser = df_display.groupby("mes")[sel_num].sum().reindex(MESES).fillna(0).reset_index()
            fig = px.line(ser, x="mes", y=sel_num, title=f"{sel_num} por mes")
            st.plotly_chart(fig, use_container_width=True)
    else:
        # sin pivot: gráfico simple por filas (ej. totales por columna)
        fig = px.histogram(df_display, x=sel_num, nbins=30, title=f"Distribución de {sel_num}")
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No se detectan columnas numéricas útiles. (Si tus datos están en columnas por mes, activa la opción 'pivot' en la barra lateral.)")

# Gráfico extra creativo: Treemap de top categorías (si existe)
if cat_col and (pivot_opt and month_cols or (df.select_dtypes(include="number").any().any())):
    st.subheader("🌳 Treemap — Distribución por categoría")
    try:
        if pivot_opt and month_cols:
            treemap_df = df_display.groupby(cat_col)["valor_mes"].sum().reset_index().sort_values("valor_mes", ascending=False).head(100)
            fig = px.treemap(treemap_df, path=[cat_col], values="valor_mes", title="Treemap — Top categorías")
            st.plotly_chart(fig, use_container_width=True)
        else:
            # sumar todas las columnas numéricas por categoría
            num_cols_all = df.select_dtypes(include="number").columns.tolist()
            if num_cols_all:
                agg = df.groupby(cat_col)[num_cols_all].sum().sum(axis=1).reset_index(name="total")
                agg = agg.sort_values("total", ascending=False).head(100)
                fig = px.treemap(agg, path=[cat_col], values="total", title="Treemap — Top categorías")
                st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.write("No fue posible generar treemap:", e)

# ----------------------------
# Tabla filtrada y descarga
# ----------------------------
st.header("🔎 Tabla filtrada / Descargar")
st.write("Filtra la tabla por texto en una columna:")

cols_display = [c for c in df_display.columns]
col_buscar = st.selectbox("Columna para filtrar (texto)", cols_display, index=0)
texto = st.text_input("Texto a buscar (mayúsc/minúsc no importa)")

df_filtrado = df_display.copy()
if texto:
    df_filtrado = df_filtrado[df_filtrado[col_buscar].astype(str).str.contains(texto, case=False, na=False)]

st.write(f"Registros mostrados: {len(df_filtrado)}")
st.dataframe(df_filtrado.head(200))

csv_bytes = df_to_csv_bytes(df_filtrado)
st.download_button("⬇️ Descargar CSV filtrado", data=csv_bytes, file_name=f"{(dataset_name or 'dataset')}_filtrado.csv", mime="text/csv")

st.caption("Si quieres menos texto en la página pido quitar los expanders o algunos st.write; dime qué se debe mostrar exactamente y lo simplifico.")
