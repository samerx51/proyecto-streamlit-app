# app.py
import streamlit as st
import pandas as pd
import requests
import os
from io import BytesIO
from typing import Dict, List, Tuple, Optional
import plotly.express as px

# ----------------------------
# CONFIG
# ----------------------------
st.set_page_config(page_title="Estadísticas Policiales Chile", layout="wide")
st.title("📊 Estadísticas Policiales en Chile — PDI & datos.gob.cl")

API_DATASETS: Dict[str, str] = {
    "Victimas": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=285a2c22-9301-4456-9e18-9fd8dbb1c6f2",
    "Controles de identidad": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=69b8c48b-1d64-4296-8275-f3d2abfe1f0e",
    "Denuncias": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=c4675051-558b-42d7-ad15-87f4bb6ee458",
    "Delitos y faltas investigadas": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=b9bdcf46-f717-4dd0-8022-52e2ce3f4080",
    "Personas detenidas": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=9afe42af-034f-4859-a479-c3b25eed49b9"
}

DATA_FOLDER = "data"

# ----------------------------
# HELPERS: carga y transformación
# ----------------------------
@st.cache_data(show_spinner=False)
def fetch_api_all_records(base_url: str, page_limit: int = 1000) -> pd.DataFrame:
    """Descarga todos los registros de una API CKAN/datastore_search paginando."""
    records = []
    offset = 0
    params = {"limit": page_limit, "offset": offset}
    try:
        while True:
            params["offset"] = offset
            resp = requests.get(base_url, params=params, timeout=25)
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

def listar_csvs(folder: str = DATA_FOLDER) -> List[str]:
    if not os.path.exists(folder):
        return []
    return sorted([f for f in os.listdir(folder) if f.lower().endswith(".csv")])

def normalize_colname(s: str) -> str:
    s2 = str(s).strip().lower()
    s2 = s2.replace(" ", "_")
    # quitar caracteres problemáticos comunes
    s2 = s2.replace(".", "").replace(",", "").replace("º", "").replace("ñ", "n").replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u")
    return s2

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [normalize_colname(c) for c in df.columns]
    return df

def wide_to_long_if_needed(df: pd.DataFrame) -> Tuple[pd.DataFrame, bool]:
    """
    Detecta si el dataframe está en formato ancho con filas = delitos y columnas = regiones/meses.
    Si detecta que la primera o segunda columna es el nombre del delito y el resto son regiones/meses,
    realiza melt para devolver un dataframe en formato largo con columnas: delito, variable (region/mes), valor.
    Devuelve (df_largo, transformed_bool)
    """
    df = df.copy()
    cols = list(df.columns)
    # Identificar columna que probablemente contiene el nombre del delito (palabras clave)
    possible_name_cols = [c for c in cols if any(k in c for k in ['delito','delitos','agrupacion','tipo'])]
    if not possible_name_cols and len(cols) >= 2:
        # fallback: si la primera columna no es numérica, considerarla como nombre
        first = cols[0]
        if df[first].dtype == object:
            possible_name_cols = [first]
    if not possible_name_cols:
        return df, False

    name_col = possible_name_cols[0]
    # columnas candidates to melt: those that are numeric (regions/meses) or start with 'region_' or look like months
    candidate_cols = [c for c in cols if c != name_col]
    # if candidate cols are mostly numeric -> melt
    numeric_count = sum(pd.to_numeric(df[c], errors='coerce').notna().sum() for c in candidate_cols)
    if numeric_count == 0:
        return df, False

    # Perform melt
    df_long = df.melt(id_vars=[name_col], value_vars=candidate_cols, var_name="variable", value_name="valor")
    # rename to consistent names
    df_long = df_long.rename(columns={name_col: "delito", "variable": "categoria", "valor": "valor"})
    # ensure numeric
    df_long["valor"] = pd.to_numeric(df_long["valor"], errors="coerce").fillna(0)
    return df_long, True

def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return buf.getvalue()

# ----------------------------
# UI: barra lateral - fuente de datos
# ----------------------------
st.sidebar.header("📁 Fuente de datos")
fuente = st.sidebar.radio("Origen de datos:", ("API (datos.gob.cl)", "CSV local (carpeta /data)"))

df = pd.DataFrame()
dataset_name = None
transformed_from_wide = False

if fuente == "API (datos.gob.cl)":
    st.sidebar.info("Selecciona un dataset y se descargan los registros (datos.gob.cl)")
    dataset_name = st.sidebar.selectbox("Dataset (API)", list(API_DATASETS.keys()))
    if dataset_name:
        url = API_DATASETS[dataset_name]
        with st.spinner(f"Descargando datos desde API: {dataset_name} ..."):
            df = fetch_api_all_records(url, page_limit=1000)
else:
    st.sidebar.info("Selecciona un CSV del repo (/data/)")
    archivos = listar_csvs()
    if not archivos:
        st.sidebar.warning("No hay archivos CSV en /data/. Súbelos y espera que GitHub actualice el deploy.")
    else:
        archivo_sel = st.sidebar.selectbox("CSV local", archivos)
        if archivo_sel:
            ruta = os.path.join(DATA_FOLDER, archivo_sel)
            dataset_name = archivo_sel
            df = load_csv_local(ruta)

# ----------------------------
# Validación inicial
# ----------------------------
if df is None or (isinstance(df, pd.DataFrame) and df.empty):
    st.warning("No se cargaron datos desde la fuente seleccionada. Revisa la barra lateral.")
    st.stop()

# Normalize columns
df = normalize_columns(df)

# EXPLORACIÓN / limpieza básica
st.header("📌 Exploración y limpieza")
st.subheader("Vista previa")
st.dataframe(df.head(10))

st.subheader("Columnas detectadas")
st.write(list(df.columns))

# Rellenar nulos (temporal) y convertir números cuando sea posible
df = df.fillna(0)
for c in df.columns:
    # intentar convertir columnas que parecen numéricas (si la conversión pierde menos del 50% datos)
    if df[c].dtype == object:
        conv = pd.to_numeric(df[c], errors='coerce')
        non_na = conv.notna().sum()
        if non_na / max(1, len(conv)) > 0.2:
            df[c] = conv.fillna(0)

# ----------------------------
# Detectar si formato ancho y transformar a formato largo
# ----------------------------
df_for_display = df.copy()
df_long = None
df_was_transformed = False

df_long, df_was_transformed = wide_to_long_if_needed(df_for_display)
if df_was_transformed:
    st.success("Dataset detectado en formato ancho → convertido a formato largo (delito, categoria, valor).")
    df_for_display = df_long.copy()
else:
    # If no transform, try to detect if there's a 'total' or 'total_general' column to allow ranking
    df_for_display = df_for_display

# ----------------------------
# Si formato largo: columnas esperadas: delito, categoria, valor
# ----------------------------
is_long = all(c in df_for_display.columns for c in ["delito", "categoria", "valor"])

# ----------------------------
# RANKING — Categorías / Delitos más frecuentes
# ----------------------------
st.header("🏆 Ranking — Categorías / Delitos más frecuentes")

if is_long:
    # sumar por delito
    ranking = df_for_display.groupby("delito")["valor"].sum().sort_values(ascending=False)
    if ranking.empty:
        st.info("No se encontraron valores para generar ranking.")
    else:
        top_n = st.slider("Top N delitos", min_value=3, max_value=20, value=8)
        top_df = ranking.head(top_n).reset_index().rename(columns={0: "total", "valor": "total"})
        top_df = top_df.rename(columns={0: "total"}) if 0 in top_df.columns else top_df
        # gráfico de barras interactivo
        fig = px.bar(top_df, x="delito", y="valor", labels={"valor":"Total"}, title=f"Top {top_n} delitos (suma total)")
        fig.update_layout(xaxis_tickangle=-45, margin=dict(b=200))
        st.plotly_chart(fig, use_container_width=True)
        st.write(top_df)
else:
    # intentar usar columna total_general o total si existe
    possible_total_cols = [c for c in df_for_display.columns if "total" in c]
    if possible_total_cols:
        tot_col = possible_total_cols[0]
        ranking = df_for_display.groupby(df_for_display.columns[0])[tot_col].sum().sort_values(ascending=False)
        top_n = st.slider("Top N (por total)", min_value=3, max_value=20, value=8)
        top_df = ranking.head(top_n).reset_index().rename(columns={0: tot_col})
        fig = px.bar(top_df, x=top_df.columns[0], y=tot_col, title=f"Top {top_n} por {tot_col}")
        fig.update_layout(xaxis_tickangle=-45, margin=dict(b=200))
        st.plotly_chart(fig, use_container_width=True)
        st.write(top_df)
    else:
        st.info("No se encontraron columnas categóricas estándar ni columna 'total' para el ranking.")

# ----------------------------
# BUSCADOR Y FILTROS (interacción)
# ----------------------------
st.header("🔎 Interacción: filtros y búsqueda")

if is_long:
    cols_filter = ["delito", "categoria"]
else:
    cols_filter = list(df_for_display.columns)

col_buscar = st.selectbox("Columna para buscar (texto)", cols_filter)
texto = st.text_input("Texto a buscar (filtra en la columna seleccionada)")
df_filtrado = df_for_display.copy()

if texto:
    df_filtrado = df_filtrado[df_filtrado[col_buscar].astype(str).str.contains(texto, case=False, na=False)]

# filtro por categoría si existe
if is_long:
    cats = sorted(df_for_display["categoria"].astype(str).unique())
    choice_cat = st.multiselect("Filtrar por categoría (region/mes)", options=cats, default=cats[:6] if len(cats)>6 else cats)
    if choice_cat:
        df_filtrado = df_filtrado[df_filtrado["categoria"].isin(choice_cat)]

# filtro por delito (largo)
if is_long:
    delitos = sorted(df_for_display["delito"].astype(str).unique())
    elegir = st.multiselect("Filtrar por delito (opcional)", options=delitos, default=delitos[:5] if len(delitos)>5 else delitos)
    if elegir:
        df_filtrado = df_filtrado[df_filtrado["delito"].isin(elegir)]

st.write(f"Resultados encontrados: {len(df_filtrado)}")
st.dataframe(df_filtrado.head(200))

# ----------------------------
# GRÁFICOS INTERACTIVOS (más creativos)
# ----------------------------
st.header("📊 Gráficos interactivos")

# 1) Gráfico principal: barras por delito (desde df_filtrado)
if is_long:
    # permitir seleccionar cómo agregar (por categoria o total)
    modo = st.selectbox("Agrupar por:", ["delito (total)", "categoria (total)"])
    if modo == "delito (total)":
        agg = df_filtrado.groupby("delito")["valor"].sum().reset_index().sort_values("valor", ascending=False)
        fig1 = px.bar(agg.head(20), x="delito", y="valor", title="Delitos — Totales (filtrado)", labels={"valor":"Total"})
        fig1.update_layout(xaxis_tickangle=-45, margin=dict(b=200))
        st.plotly_chart(fig1, use_container_width=True)
    else:
        agg = df_filtrado.groupby("categoria")["valor"].sum().reset_index().sort_values("valor", ascending=False)
        fig1 = px.bar(agg.head(40), x="categoria", y="valor", title="Categorias (regiones/meses) — Totales (filtrado)", labels={"valor":"Total"})
        fig1.update_layout(xaxis_tickangle=-45, margin=dict(b=200))
        st.plotly_chart(fig1, use_container_width=True)
else:
    # si formato no-largo: permitir seleccionar columna numérica (e.g., meses, regiones)
    num_cols = df_for_display.select_dtypes(include="number").columns.tolist()
    if num_cols:
        # Excluir _id si hay
        num_cols_display = [c for c in num_cols if c not in ["_id", "id"]]
        if not num_cols_display:
            num_cols_display = num_cols
        col_num = st.selectbox("Selecciona columna numérica", num_cols_display)
        tipo = st.selectbox("Tipo de gráfico", ["Barras", "Línea"])
        if tipo == "Barras":
            fig2 = px.bar(df_for_display.sort_values(col_num, ascending=False).head(40), x=df_for_display.columns[0], y=col_num, title=f"{col_num} — por {df_for_display.columns[0]}")
            fig2.update_layout(xaxis_tickangle=-45, margin=dict(b=200))
            st.plotly_chart(fig2, use_container_width=True)
        else:
            fig2 = px.line(df_for_display.sort_values(col_num, ascending=False).head(200), x=df_for_display.columns[0], y=col_num, title=f"{col_num} — serie")
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No se detectan columnas numéricas útiles en este formato. Si tus datos vienen en columnas por mes/región, habilita la conversión a formato largo.")

# ----------------------------
# DESCARGA DE DATOS
# ----------------------------
st.header("⬇️ Descargar datos (vista actual)")
csv_bytes = df_to_csv_bytes(df_filtrado if not df_filtrado.empty else df_for_display)
st.download_button("Descargar CSV actual", data=csv_bytes, file_name=f"{(dataset_name or 'dataset')}_export.csv", mime="text/csv")

# ----------------------------
# AYUDA / NOTAS UI
# ----------------------------
st.markdown("---")
st.info(
    "Sugerencias:\n"
    "- Si el dataset aparece con columnas tipo 'enero,febrero,...' o 'region_xxx' y prefieres ver tipos de delito por fila, la app intenta convertirlo automáticamente. \n"
    "- Si no quedó como esperas, en la barra lateral selecciona 'CSV local' y sube un CSV preparado (filas=delitos, columnas=regions o meses). \n"
    "- Dime si quieres que agregue: mapa, series temporales por año, o gráficos tipo 'treemap' o 'sunburst' para visualizar proporciones."
)
