# app.py - Versión estable y visual (Plotly) para Estadísticas PDI (API + CSV local)
import streamlit as st
import pandas as pd
import requests
import os
from io import BytesIO
from typing import Dict, List
import plotly.express as px

# ---------- Config y constantes ----------
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
MESES = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]

# ---------- Helpers ----------
def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return buf.getvalue()

@st.cache_data(show_spinner=False)
def fetch_api_all_records(base_url: str, page_limit: int = 1000) -> pd.DataFrame:
    """Paginación segura para CKAN/datastore_search (datos.gob.cl)."""
    try:
        records = []
        offset = 0
        while True:
            params = {"limit": page_limit, "offset": offset}
            resp = requests.get(base_url, params=params, timeout=20)
            resp.raise_for_status()
            j = resp.json()
            batch = j.get("result", {}).get("records", [])
            if not batch:
                break
            records.extend(batch)
            offset += len(batch)
            if len(batch) < page_limit:
                break
        return pd.DataFrame(records)
    except Exception as e:
        st.error(f"Error al descargar desde API: {e}")
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

def normalizar_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df

def detect_month_columns(cols: List[str]) -> List[str]:
    cols_l = [c.lower() for c in cols]
    meses = [c for c in cols if any(m in c.lower() for m in MESES)]
    return meses

# ---------- Sidebar: elegir fuente ----------
st.sidebar.header("Fuente de datos")
fuente = st.sidebar.radio("Origen:", ("API (datos.gob.cl)", "CSV local (carpeta /data)"))

df_raw = pd.DataFrame()
dataset_name = None

if fuente == "API (datos.gob.cl)":
    st.sidebar.info("Selecciona un dataset (datos.gob.cl).")
    dataset_name = st.sidebar.selectbox("Dataset (API)", list(API_DATASETS.keys()))
    if dataset_name:
        url = API_DATASETS[dataset_name]
        with st.spinner("Descargando datos desde la API..."):
            df_raw = fetch_api_all_records(url)
else:
    st.sidebar.info("Selecciona un CSV subido a /data/")
    archivos = listar_csvs()
    if not archivos:
        st.sidebar.warning("No hay archivos CSV en /data/. Súbelos y refresca.")
    else:
        archivo_sel = st.sidebar.selectbox("CSV local", archivos)
        if archivo_sel:
            dataset_name = archivo_sel
            ruta = os.path.join(DATA_FOLDER, archivo_sel)
            df_raw = load_csv_local(ruta)

# ---------- Validación ----------
if df_raw is None or df_raw.empty:
    st.warning("No se han cargado datos desde la fuente seleccionada. Revisa la barra lateral.")
    st.stop()

# ---------- Limpieza básica ----------
# eliminar columna de índice si existe (Unnamed: 0)
if "unnamed: 0" in [c.lower() for c in df_raw.columns]:
    df_raw = df_raw.loc[:, [c for c in df_raw.columns if c.lower() != "unnamed: 0"]]

df = normalizar_cols(df_raw)
df = df.fillna(0)

# Si la tabla viene como filas = delitos, columnas = regiones (como tu CSV), transformamos a largo
# Buscamos columna que contenga el texto 'delito' / 'delitos' / 'delitos_segun' u otras heurísticas
possible_del_cols = [c for c in df.columns if any(k in c for k in ["delito", "delitos", "agrupacion", "descripcion"])]
del_col = possible_del_cols[0] if possible_del_cols else None

# Si no detectamos, intentar detectar por posición: primera columna no-numérica con varios únicos pero < 500
if del_col is None:
    for c in df.columns:
        if df[c].dtype == object and c != "_id":
            nunq = df[c].nunique()
            if 1 < nunq < 500:
                del_col = c
                break

# detectamos columnas mes/región (numéricas)
month_cols = detect_month_columns(df.columns)
# también detectar columnas numéricas diferentes (regiones)
numeric_candidate_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and c not in [del_col, "total_general", "_id"]]

# Decisión: si hay del_col y numeric_candidate_cols -> crear df_long por melt (filas: delito-region-cantidad)
df_long = pd.DataFrame()
if del_col and numeric_candidate_cols:
    id_vars = [del_col]
    value_vars = numeric_candidate_cols
    df_long = df.melt(id_vars=id_vars, value_vars=value_vars, var_name="region", value_name="cantidad")
    # limpiar nombres region
    df_long["region"] = df_long["region"].astype(str).str.replace("region_de_", "", regex=False).str.replace("_", " ").str.strip()
    df_long["delito"] = df_long[del_col].astype(str).str.strip()
    df_long["cantidad"] = pd.to_numeric(df_long["cantidad"], errors="coerce").fillna(0).astype(int)
else:
    # fallback: si ya está en formato largo (tiene columnas 'delito' y 'region' y 'cantidad')
    if set(["delito","region","cantidad"]).issubset(set(df.columns)):
        df_long = df[["delito","region","cantidad"]].copy()
        df_long["cantidad"] = pd.to_numeric(df_long["cantidad"], errors="coerce").fillna(0).astype(int)
    else:
        # si no podemos resolver, convertimos lo posible: todas las columnas numéricas sumadas a una columna 'total'
        if df.select_dtypes(include="number").shape[1] > 0:
            numeric_cols = df.select_dtypes(include="number").columns.tolist()
            agg = pd.DataFrame(df[numeric_cols].sum()).reset_index()
            agg.columns = ["region_or_col","cantidad"]
            agg["delito"] = "total_agrupado"
            df_long = agg[["delito","region_or_col","cantidad"]].rename(columns={"region_or_col":"region"})
        else:
            st.error("No fue posible inferir formato (ni filas-delito ni formato largo). Revisa tu CSV o selecciona otro dataset.")
            st.stop()

# Ahora df_long tiene: delito, region, cantidad
# Normalizar texto
df_long["region"] = df_long["region"].astype(str).str.lower()
df_long["delito"] = df_long["delito"].astype(str).str.strip()

# ----------------- INTERFAZ PRINCIPAL (más visual y menos texto) -----------------
st.markdown("### Visualizaciones interactivas")
col1, col2 = st.columns([2,1])

with col2:
    st.subheader("Controles")
    top_n = st.number_input("Top N delitos (ranking)", min_value=3, max_value=50, value=8, step=1)
    region_filter = st.selectbox("Filtrar por región (opcional)", ["Todas"] + sorted(df_long["region"].unique().tolist()))
    delito_filter = st.selectbox("Filtrar por delito (opcional)", ["Todos"] + sorted(df_long["delito"].unique().tolist()))
    compact_mode = st.checkbox("Mostrar menos textos/expander", value=True)
    download_source = st.selectbox("Descargar datos de:", ["Tabla larga (delito-region)","Resultados filtrados"])

with col1:
    # Top N delitos (suma total)
    st.subheader(f"🏆 Top {top_n} delitos (suma total)")
    df_top = df_long.groupby("delito", as_index=False)["cantidad"].sum().sort_values("cantidad", ascending=False)
    if delito_filter != "Todos":
        # si hay un filtro por delito, limitar (mantener orden)
        df_top = df_top[df_top["delito"] == delito_filter]
    fig_top = px.bar(df_top.head(top_n), x="cantidad", y="delito", orientation="h",
                     title=f"Top {top_n} delitos", labels={"cantidad":"Total","delito":"Delito"})
    st.plotly_chart(fig_top, use_container_width=True)

# Aplicar filtros a df_long
df_filtered = df_long.copy()
if region_filter != "Todas":
    df_filtered = df_filtered[df_filtered["region"] == region_filter]
if delito_filter != "Todos":
    df_filtered = df_filtered[df_filtered["delito"] == delito_filter]

# Serie por región / mes (si 'mes' existe en tu df o si month_cols detectados)
st.markdown("### Series por categoría / región")
if "mes" in df_filtered.columns or any(m in c for m in MESES for c in df.columns):
    # Si existe df with mes column (rare), o user wants months, attempt to build monthly series
    # We'll attempt to detect month-named columns in the original df and pivot if present
    meses_found = [c for c in df.columns if any(m in c for m in MESES)]
    if meses_found:
        # Si original tiene columnas por mes, hacer melt específico
        base_id_vars = [c for c in df.columns if c not in meses_found]
        df_meses = df.melt(id_vars=base_id_vars, value_vars=meses_found, var_name="mes", value_name="valor")
        # Si col del nombre del delito cambió en normalizar, ubicarlo
        delito_col_name = del_col if del_col else base_id_vars[0] if base_id_vars else None
        if delito_col_name:
            df_meses["delito"] = df_meses[delito_col_name].astype(str).str.strip()
            df_meses["mes"] = df_meses["mes"].astype(str).str.lower()
            df_meses["valor"] = pd.to_numeric(df_meses["valor"], errors="coerce").fillna(0).astype(int)
            # aplicar filtros
            tmp = df_meses.copy()
            if region_filter != "Todas" and "region" in tmp.columns:
                tmp = tmp[tmp["region"]==region_filter]
            if delito_filter != "Todos":
                tmp = tmp[tmp["delito"]==delito_filter]
            # agrupar por mes
            series = tmp.groupby("mes")["valor"].sum().reindex(MESES).fillna(0).reset_index()
            fig = px.line(series, x="mes", y="valor", title="Serie por mes (valores agrupados)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No se pudo identificar columna de delito para la transformación por meses.")
    else:
        # Si no hay meses, mostrar serie por region (si hay varias regiones)
        if df_filtered["region"].nunique() > 1:
            series = df_filtered.groupby("region")["cantidad"].sum().reset_index().sort_values("cantidad", ascending=False)
            fig = px.bar(series.head(30), x="region", y="cantidad", title="Totales por región (top)", labels={"cantidad":"Total","region":"Región"})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos por mes detectados; mostrando totales por región o por delito arriba.")
else:
    # Sin meses detectados: mostrar totales por región o por delito
    if df_filtered["region"].nunique() > 1:
        series = df_filtered.groupby("region")["cantidad"].sum().reset_index().sort_values("cantidad", ascending=False)
        fig = px.bar(series.head(30), x="region", y="cantidad", title="Totales por región (top)", labels={"cantidad":"Total","region":"Región"})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No se detectaron series por mes ni múltiples regiones en los datos filtrados.")

# Treemap creativo
st.markdown("### 🌳 Treemap — Distribución por delito")
treemap_df = df_long.groupby("delito", as_index=False)["cantidad"].sum().sort_values("cantidad", ascending=False).head(100)
fig_tree = px.treemap(treemap_df, path=["delito"], values="cantidad", title="Treemap — Top delitos")
st.plotly_chart(fig_tree, use_container_width=True)

# Tabla filtrada y descarga
st.markdown("### 🔎 Tabla filtrada")
st.write(f"Registros: {len(df_filtered)}")
st.dataframe(df_filtered.head(300))

csv_choice = df_to_csv_bytes(df_filtered if download_source=="Resultados filtrados" else df_long)
st.download_button("⬇️ Descargar CSV seleccionado", data=csv_choice, file_name=f"{(dataset_name or 'dataset')}_export.csv", mime="text/csv")

# Mensaje final pequeño (para cumplir con claridad)
if not compact_mode:
    st.markdown("---")
    st.info("Interactividad: filtra por región o delito en la columna de la derecha. Si los datos vienen por meses (enero...diciembre) activa el pivot en la versión anterior para series mensuales.")


