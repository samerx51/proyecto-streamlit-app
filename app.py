import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from typing import Dict, List, Optional
import plotly.express as px

st.set_page_config(page_title="Estadísticas Policiales Chile (API)", layout="wide")
st.title("📊 Estadísticas Policiales en Chile — PDI & datos.gob.cl")

# ----------------------------
# CONFIG: APIs
# ----------------------------
API_DATASETS: Dict[str, str] = {
    "Victimas": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=285a2c22-9301-4456-9e18-9fd8dbb1c6f2",
    "Controles de identidad": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=69b8c48b-1d64-4296-8275-f3d2abfe1f0e",
    "Denuncias": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=c4675051-558b-42d7-ad15-87f4bb6ee458",
    "Delitos y faltas investigadas": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=b9bdcf46-f717-4dd0-8022-52e2ce3f4080",
    "Personas detenidas": "https://datos.gob.cl/api/3/action/datastore_search?resource_id=9afe42af-034f-4859-a479-c3b25eed49b9"
}

MESES = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]

# ----------------------------
# HELPERS
# ----------------------------
@st.cache_data(show_spinner=False)
def fetch_api_all_records(base_url: str, page_limit: int = 1000) -> pd.DataFrame:
    """
    Descarga todos los registros de una API CKAN/datastore_search usando paginación.
    Devuelve DataFrame (puede ser vacío).
    """
    records = []
    offset = 0
    params = {"limit": page_limit, "offset": offset}
    try:
        while True:
            params["offset"] = offset
            resp = requests.get(base_url, params=params, timeout=30)
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
        st.error(f"Error al descargar datos desde la API: {e}")
        return pd.DataFrame()

def normalize_col_names(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df

def to_numeric_if_possible(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    df = df.copy()
    for c in cols:
        try:
            df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", "").str.replace(".", ""), errors="coerce").fillna(0)
        except Exception:
            pass
    return df

def wide_to_long_if_needed(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detecta si df tiene filas = delitos y columnas = regiones (ej: columna 'delitos_segun_agrupacion_por_modernizacion'
    y varias columnas region_*). Si es así, convierte a formato largo con columnas: delito, region, cantidad
    Si ya está en formato largo intenta mapear a esas columnas y devolver DataFrame con esas columnas.
    """
    df0 = df.copy()
    df0 = normalize_col_names(df0)

    # heurística: si existe columna de delitos agrupados y varias columnas que empiezan con 'region' o 'region_de'
    crime_col_candidates = [c for c in df0.columns if "delitos" in c or "delito" in c or "delitos_segun" in c]
    region_cols = [c for c in df0.columns if c.startswith("region_") or c.startswith("reg_") or c.startswith("region")]
    # also allow columns that look like region names (e.g., 'region_metropolitana_de_santiago')
    region_like = [c for c in df0.columns if any(p in c for p in ["metropolitana","valparaiso","araucania","biobio","antofagasta","tarapaca","los_lagos","los_rios","magallanes","atan"])]
    if region_like and not region_cols:
        region_cols = region_like

    if crime_col_candidates and region_cols:
        # assume wide format
        crime_col = crime_col_candidates[0]
        # prepare melt
        try:
            df_long = df0.melt(id_vars=[crime_col], value_vars=region_cols, var_name="region", value_name="cantidad")
            # clean region names
            df_long["region"] = df_long["region"].astype(str).str.replace("region_de_", "", regex=False).str.replace("region_", "", regex=False)
            df_long["region"] = df_long["region"].str.replace("_", " ").str.strip()
            df_long = df_long.rename(columns={crime_col: "delito"})
            df_long["cantidad"] = pd.to_numeric(df_long["cantidad"], errors="coerce").fillna(0)
            return df_long[["delito","region","cantidad"]]
        except Exception:
            pass

    # else, try to find columns that map to delito, region, cantidad directly
    possible_delito = None
    for c in df0.columns:
        if "delit" in c or "agrup" in c or "tipo" in c or "delito" in c:
            possible_delito = c
            break
    possible_region = None
    for c in df0.columns:
        if "region" in c or "comuna" in c or "provincia" in c:
            possible_region = c
            break
    possible_cantidad = None
    for c in df0.columns:
        if c in ["cantidad","total","num","valor","total_general","total_general"]:
            possible_cantidad = c
            break
    # fallback: numeric column with many values -> cantidad
    if possible_cantidad is None:
        numeric_cols = df0.select_dtypes(include="number").columns.tolist()
        if numeric_cols:
            possible_cantidad = numeric_cols[0]

    if possible_delito and possible_region and possible_cantidad:
        df_long = df0.rename(columns={
            possible_delito: "delito",
            possible_region: "region",
            possible_cantidad: "cantidad"
        })[["delito","region","cantidad"]]
        df_long["cantidad"] = pd.to_numeric(df_long["cantidad"], errors="coerce").fillna(0)
        return df_long

    # as last resort, try to pivot any month columns into long (month detection)
    meses = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]
    month_cols = [c for c in df0.columns if any(m in c for m in meses)]
    if month_cols:
        id_vars = [c for c in df0.columns if c not in month_cols]
        # choose a plausible delito column
        delito_col = None
        for c in id_vars:
            if "delito" in c or "tipo" in c or "agrup" in c:
                delito_col = c
                break
        if delito_col is None and id_vars:
            delito_col = id_vars[0]
        df_long = df0.melt(id_vars=[delito_col], value_vars=month_cols, var_name="mes", value_name="cantidad")
        df_long = df_long.rename(columns={delito_col: "delito"})
        df_long["mes"] = df_long["mes"].astype(str).str.strip().str.lower()
        df_long["cantidad"] = pd.to_numeric(df_long["cantidad"], errors="coerce").fillna(0)
        # region unknown in this case - keep delito, mes, cantidad
        return df_long[["delito","mes","cantidad"]]

    # if nothing pudo detectarse, devolver df con columnas originales pero normalizadas
    return df0

def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return buf.getvalue()

# ----------------------------
# SIDEBAR: selección dataset y opciones
# ----------------------------
st.sidebar.header("📁 Dataset (API)")
dataset_choice = st.sidebar.selectbox("Elegir dataset", list(API_DATASETS.keys()))

st.sidebar.markdown("**Opciones de visualización**")
top_n = st.sidebar.slider("Mostrar top N delitos", min_value=5, max_value=30, value=10)
show_treemap = st.sidebar.checkbox("Mostrar treemap", value=True)
show_heatmap = st.sidebar.checkbox("Mostrar heatmap (región vs delito)", value=True)
show_timeseries = st.sidebar.checkbox("Mostrar serie temporal (si hay año)", value=True)

# ----------------------------
# Descarga datos desde API
# ----------------------------
with st.spinner("Descargando datos (puede tardar unos segundos)..."):
    url = API_DATASETS[dataset_choice]
    raw_df = fetch_api_all_records(url, page_limit=1000)

if raw_df.empty:
    st.error("La API devolvió un dataset vacío o hubo un error. Revisa la conexión o intenta otro dataset.")
    st.stop()

# Normalizar
raw_df = normalize_col_names(raw_df)

# Convertir wide->long o normalizar a df_long
df_long = wide_to_long_if_needed(raw_df)

# Estándar: si df_long tiene 'mes' en lugar de 'region', mantenemos esa info
has_region = "region" in df_long.columns
has_mes = "mes" in df_long.columns

# Asegurar columnas esperadas
if "delito" not in df_long.columns:
    # renombrar primera columna a 'delito' si no existe
    df_long = df_long.rename(columns={df_long.columns[0]: "delito"})

if "cantidad" not in df_long.columns and "valor" in df_long.columns:
    df_long = df_long.rename(columns={"valor": "cantidad"})

# llenar nulos y convertir cantidad a numérico
if "cantidad" in df_long.columns:
    df_long["cantidad"] = pd.to_numeric(df_long["cantidad"], errors="coerce").fillna(0)
else:
    # si no hay columna 'cantidad', crear con 1 para conteo
    df_long["cantidad"] = 1

# Normalizar strings
df_long["delito"] = df_long["delito"].astype(str).str.strip()
if has_region:
    df_long["region"] = df_long["region"].astype(str).str.strip()

# Mostrar info breve
st.sidebar.success(f"Registros: {len(raw_df)} → filas transformadas: {len(df_long)}")

# ----------------------------
# FILTROS principales en UI
# ----------------------------
st.header("🔎 Exploración y filtros (trabajamos solo con API)")

# Filtro por región (si existe)
region_sel: Optional[str] = None
if has_region:
    regiones = sorted(df_long["region"].unique().astype(str).tolist())
    regiones = ["Todos"] + regiones
    region_sel = st.selectbox("Filtrar por región", regiones, index=0)
    if region_sel != "Todos":
        df_vis = df_long[df_long["region"] == region_sel].copy()
    else:
        df_vis = df_long.copy()
else:
    df_vis = df_long.copy()

# Filtro por delito (multi)
delitos_disponibles = sorted(df_vis["delito"].unique().astype(str).tolist())
delitos_sel = st.multiselect("Seleccionar delito(s) (dejar vacío = todos)", delitos_disponibles, default=[])

if delitos_sel:
    df_vis = df_vis[df_vis["delito"].isin(delitos_sel)]

# Filtrar por mes si aplica
if has_mes:
    meses_disponibles = sorted(df_vis["mes"].unique().astype(str).tolist(), key=lambda x: MESES.index(x) if x in MESES else 999)
    mes_sel = st.selectbox("Filtrar por mes", ["Todos"] + meses_disponibles, index=0)
    if mes_sel != "Todos":
        df_vis = df_vis[df_vis["mes"] == mes_sel]

# Mostrar tabla resumida y descarga
st.subheader("Tabla (previsualización)")
st.write(f"Filas mostradas: {len(df_vis)}")
st.dataframe(df_vis.head(200))

csv_bytes = df_to_csv_bytes(df_vis)
st.download_button("⬇️ Descargar CSV (filtrado)", data=csv_bytes, file_name=f"{dataset_choice}_filtrado.csv", mime="text/csv")

# ----------------------------
# Top N delitos (barra)
# ----------------------------
st.header(f"🏆 Top {top_n} — Delitos más frecuentes (suma cantidad)")

try:
    top = df_vis.groupby("delito")["cantidad"].sum().sort_values(ascending=False).head(top_n).reset_index()
    if not top.empty:
        fig_bar = px.bar(top, x="delito", y="cantidad", title=f"Top {top_n} delitos", labels={"cantidad":"Total"}, text="cantidad")
        fig_bar.update_layout(xaxis_tickangle=-45, margin={"t":50,"b":150})
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("No hay datos para mostrar en el Top.")
except Exception as e:
    st.error(f"Error generando Top N: {e}")

# ----------------------------
# Treemap creativo
# ----------------------------
if show_treemap:
    st.header("🌳 Treemap — Distribución por delito")
    try:
        treemap_df = df_vis.groupby("delito")["cantidad"].sum().reset_index().sort_values("cantidad", ascending=False).head(200)
        if not treemap_df.empty:
            fig_t = px.treemap(treemap_df, path=["delito"], values="cantidad", title="Treemap — Delitos (Top)")
            st.plotly_chart(fig_t, use_container_width=True)
        else:
            st.info("No hay datos para el treemap.")
    except Exception as e:
        st.error(f"Error en treemap: {e}")

# ----------------------------
# Heatmap region vs delito (si hay region)
# ----------------------------
if show_heatmap and has_region:
    st.header("🔥 Heatmap — Región vs Delito")
    try:
        pivot = df_vis.pivot_table(index="delito", columns="region", values="cantidad", aggfunc="sum", fill_value=0)
        if pivot.shape[0] == 0 or pivot.shape[1] == 0:
            st.info("No hay suficiente información para generar heatmap.")
        else:
            # limitar a top delitos to keep heatmap readable
            top_delitos_for_heat = pivot.sum(axis=1).sort_values(ascending=False).head(30).index.tolist()
            pivot_small = pivot.loc[top_delitos_for_heat]
            fig_h = px.imshow(pivot_small, labels=dict(x="Región", y="Delito", color="Cantidad"), aspect="auto", title="Heatmap: Regiones vs Delitos (Top 30 delitos)")
            st.plotly_chart(fig_h, use_container_width=True)
    except Exception as e:
        st.error(f"Error generando heatmap: {e}")

# ----------------------------
# Serie temporal si existe columna año
# ----------------------------
possible_year_cols = [c for c in raw_df.columns if "anio" in c or "año" in c or "year" in c]
if show_timeseries and possible_year_cols:
    st.header("📈 Serie temporal (por año)")
    try:
        # preferimos columna 'anio' detectada en df_vis, si no está en df_vis intentamos tomar de raw_df
        ycol = possible_year_cols[0]
        # si está en df_vis usarlo; sino intentar juntar raw_df mapped
        if ycol in df_vis.columns:
            df_times = df_vis.copy()
            df_times[ycol] = pd.to_numeric(df_times[ycol], errors="coerce").fillna(0).astype(int)
            times = df_times.groupby(ycol)["cantidad"].sum().reset_index()
            fig_ts = px.line(times, x=ycol, y="cantidad", title="Serie temporal (total cantidad por año)", markers=True)
            st.plotly_chart(fig_ts, use_container_width=True)
        else:
            st.info(f"No se detectó columna de año usable en la tabla transformada (buscando {ycol}).")
    except Exception as e:
        st.error(f"Error generando serie temporal: {e}")

st.markdown("---")
st.caption("Interfaz diseñada para trabajar SOLO con APIs (datos.gob.cl). Si quieres añadir/editar algún gráfico (mapa, barras apiladas, comparador entre regiones), dime cuál y lo agrego.")
