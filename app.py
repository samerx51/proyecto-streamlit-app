import streamlit as st
import pandas as pd
import requests
import os
from io import BytesIO
from typing import Dict
import plotly.express as px

st.set_page_config(page_title="Estadísticas Policiales Chile", layout="wide")
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

DATA_FOLDER = "data"
MESES = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]

# ----------------------------
# UTIL: funciones de carga y ayuda
# ----------------------------
@st.cache_data(show_spinner=False)
def fetch_api_all_records(base_url: str, page_limit: int = 1000) -> pd.DataFrame:
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

# ----------------------------
# BARRA LATERAL - fuente y opciones
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
# Limpieza inicial: rellenar NAs y normalizar números
# ----------------------------
df = df.fillna(0)

# intentar convertir strings numéricos a numeric
for c in df.columns:
    if df[c].dtype == object:
        sample = df[c].astype(str).head(30).str.replace(r"[^\d\-,\.]", "", regex=True)
        n_nums = sample.str.replace(",", "").str.replace("-", "").str.isnumeric().sum()
        if n_nums >= 3:
            df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", ""), errors='coerce').fillna(0)

# ----------------------------
# Detectar columnas de delito / estructura del CSV
# ----------------------------
# Si existe la columna indicada por el CSV exportado original, la renombramos:
if "delitos_segun_agrupacion_por_modernizacion" in df.columns:
    df = df.rename(columns={"delitos_segun_agrupacion_por_modernizacion": "delito"})

# columnas que suelen venir por regiones/meses: tomar todas excepto identificadores
cols_excluir = ["_id", "delito", "total_general"]
columnas_delitos = [c for c in df.columns if c not in cols_excluir]

# Transformación a formato largo (melt) si el dataset está en formato ancho (regiones/meses como columnas)
# Verificamos si las columnas_delitos contienen nombres de regiones o meses
is_month_format = any(any(m in c for m in MESES) for c in columnas_delitos)
is_region_format = any(c.startswith("region_") or c.startswith("region") for c in columnas_delitos)

# Generaremos df_long como formato estándar: delito, region/mes, cantidad
df_long = None
if is_month_format or is_region_format:
    # Hacemos melt usando 'delito' como id_var (si no existe, intentamos inferir)
    id_vars = [c for c in df.columns if c in ["delito"] or df[c].nunique() <= 200]
    # garantizar al menos 'delito' como id_var si existe
    if "delito" in df.columns:
        id_vars = ["delito"] + [c for c in id_vars if c != "delito"]
    try:
        df_long = df.melt(id_vars=id_vars, value_vars=columnas_delitos, var_name="region_mes", value_name="cantidad")
        # limpiar region_mes
        df_long["region_mes"] = df_long["region_mes"].astype(str).str.replace("region_de_", "", regex=False).str.replace("_", " ").str.strip().str.lower()
        # si es mes, intentar normalizar a nombre de mes
        df_long["region_mes"] = df_long["region_mes"].apply(lambda x: x.lower())
    except Exception:
        df_long = None

# Si no se pudo generar df_long, mantenemos df tal cual pero trabajaremos con él
df_display = df_long.copy() if df_long is not None else df.copy()

# ----------------------------
# Simplified preview (menos texto)
# ----------------------------
st.subheader("Vista previa")
st.dataframe(df.head(8))
with st.expander("Columnas (ver)"):
    st.write(list(df.columns))

# ----------------------------
# Detectar columna categórica para ranking
# ----------------------------
possible_cat_names = ["delito", "tipo_delito", "categoria", "comuna", "region"]
cat_col = None
for name in possible_cat_names:
    if name in df_display.columns:
        cat_col = name
        break

# si no hay, buscar columna object con pocos únicos
if cat_col is None:
    obj_cols = [c for c in df_display.columns if df_display[c].dtype == object and c != "_id"]
    for c in obj_cols:
        if 1 < df_display[c].nunique() <= 500:
            cat_col = c
            break

# ----------------------------
# Ranking — categorías más frecuentes (corregido)
# ----------------------------
st.header("🏆 Ranking — Categorías más frecuentes")
try:
    if cat_col:
        # Construir DataFrame para graficar: columnas 'categoria' y 'valor'
        if df_long is not None and "cantidad" in df_long.columns:
            rank_df = df_long.groupby(cat_col if cat_col in df_long.columns else "delito")["cantidad"].sum().reset_index()
            rank_df = rank_df.rename(columns={rank_df.columns[0]: "categoria", "cantidad": "valor"})
        else:
            # sumar todas las columnas numéricas por categoría en df original
            num_cols = df.select_dtypes(include="number").columns.tolist()
            if num_cols:
                agg_series = df.groupby(cat_col)[num_cols].sum().sum(axis=1)
                rank_df = agg_series.reset_index().rename(columns={agg_series.name: "valor", cat_col: "categoria"})
            else:
                # fallback: conteo simple de valores
                vc = df[cat_col].value_counts().reset_index()
                vc.columns = ["categoria", "valor"]
                rank_df = vc

        rank_df = rank_df.sort_values("valor", ascending=False).head(15).reset_index(drop=True)
        if not rank_df.empty:
            fig_rank = px.bar(rank_df, x="categoria", y="valor", title="Top categorías (por suma total)", labels={"categoria":"Categoría", "valor":"Total"})
            st.plotly_chart(fig_rank, use_container_width=True)
            st.write(rank_df)
        else:
            st.info("No se pudo calcular ranking: dataframe vacío después de agregaciones.")
    else:
        st.info("No se encontraron columnas categóricas claras para generar ranking.")
except Exception as e:
    st.error(f"Error generando ranking: {e}")

# ----------------------------
# Gráficos interactivos (mejorados)
# ----------------------------
st.header("📊 Gráficos interactivos (creativos)")

# Construir lista robusta de columnas numéricas a mostrar
if isinstance(df_display, pd.DataFrame):
    numeric_cols = [c for c in df_display.select_dtypes(include="number").columns if c != "_id"]
else:
    numeric_cols = [c for c in df.select_dtypes(include="number").columns if c != "_id"]

# Si aplicamos melt (df_long), la columna numérica principal será 'cantidad'
if df_long is not None and "cantidad" in df_long.columns:
    numeric_cols = ["cantidad"]

if numeric_cols:
    sel_num = st.selectbox("Selecciona columna numérica", numeric_cols)
    # Si tenemos df_long con 'region_mes' y queremos series por mes:
    if df_long is not None and "region_mes" in df_long.columns:
        # permitir filtrar por categoría (delito u otra cat_col)
        if "delito" in df_long.columns:
            cat_choice = st.selectbox("Filtrar por delito (opcional)", ["Todos"] + sorted(df_long["delito"].unique().astype(str).tolist()))
            sub = df_long.copy()
            if cat_choice != "Todos":
                sub = sub[sub["delito"].astype(str) == cat_choice]
        else:
            sub = df_long.copy()

        # Si region_mes contiene meses (check)
        if all(m in MESES for m in sorted(set([r for r in sub["region_mes"].astype(str).unique() if isinstance(r,str) and r.strip()!='']))):
            # ordenar por MESES
            serie = sub.groupby("region_mes")[sel_num].sum().reindex(MESES).fillna(0).reset_index()
            fig = px.line(serie, x="region_mes", y=sel_num, title=f"{sel_num} por mes", labels={"region_mes":"Mes", sel_num:"Total"})
            st.plotly_chart(fig, use_container_width=True)
        else:
            # tratar region_mes como regiones
            region_series = sub.groupby("region_mes")[sel_num].sum().sort_values(ascending=False).reset_index()
            fig = px.bar(region_series.head(30), x="region_mes", y=sel_num, title=f"{sel_num} por región (top 30)", labels={"region_mes":"Región", sel_num:"Total"})
            st.plotly_chart(fig, use_container_width=True)
    else:
        # sin df_long: graficar con df normal (distribución o totales)
        # si la columna es 'total_general' o similar, mostrar barras por filas
        if sel_num in df.columns:
            if df[sel_num].nunique() <= 50:
                # barras por categoría si existe columna 'delito'
                if "delito" in df.columns:
                    agg = df.groupby("delito")[sel_num].sum().reset_index().sort_values(sel_num, ascending=False)
                    fig = px.bar(agg.head(30), x="delito", y=sel_num, title=f"{sel_num} por delito (top 30)", labels={"delito":"Delito", sel_num:"Total"})
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    fig = px.histogram(df, x=sel_num, nbins=30, title=f"Distribución de {sel_num}")
                    st.plotly_chart(fig, use_container_width=True)
            else:
                fig = px.histogram(df, x=sel_num, nbins=30, title=f"Distribución de {sel_num}")
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("La columna seleccionada no está en el dataframe actual.")
else:
    st.info("No se detectan columnas numéricas útiles. Si tus datos están en columnas por mes, activa el pivot/melt (ya aplicado automáticamente cuando corresponde).")

# Treemap creativo (si hay categoría)
if cat_col:
    try:
        if df_long is not None and "cantidad" in df_long.columns:
            treemap_df = df_long.groupby("delito")["cantidad"].sum().reset_index().sort_values("cantidad", ascending=False).head(200)
            fig = px.treemap(treemap_df, path=["delito"], values="cantidad", title="Treemap — Distribución por delito (Top 200)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            num_cols_all = df.select_dtypes(include="number").columns.tolist()
            if num_cols_all:
                agg = df.groupby(cat_col)[num_cols_all].sum().sum(axis=1).reset_index(name="total")
                agg = agg.sort_values("total", ascending=False).head(200)
                fig = px.treemap(agg, path=[cat_col], values="total", title="Treemap — Top categorías")
                st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.write("No fue posible generar treemap:", e)

# ----------------------------
# Tabla filtrada y descarga
# ----------------------------
st.header("🔎 Tabla filtrada / Descargar")
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

st.caption("Si quieres que la interfaz sea más 'visual' (menos texto) puedo quitar algunos st.write/expanders y dejar solo gráficos y botones. Dime exactamente qué mostrar y lo simplifico.")
