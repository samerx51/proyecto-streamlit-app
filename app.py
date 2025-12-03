# app.py
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
MESES_ORDER = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]

# ----------------------------
# UTIL: funciones
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

def normalizar_colnames(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df

def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return buf.getvalue()

def try_convert_numeric_columns(df: pd.DataFrame, min_numeric_samples: int = 3) -> pd.DataFrame:
    """Intenta convertir columnas object a numéricas si la mayoría de muestras parecen números."""
    df = df.copy()
    for c in df.columns:
        if df[c].dtype == object:
            sample = df[c].astype(str).head(20).str.replace(r"[^\d\-,\.]", "", regex=True)
            n_nums = sample.str.replace(",", "").str.replace("-", "").str.isnumeric().sum()
            if n_nums >= min_numeric_samples:
                df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", ""), errors="coerce").fillna(0)
    return df

# ----------------------------
# SIDEBAR: fuente y opciones
# ----------------------------
st.sidebar.header("Fuente de datos")
fuente = st.sidebar.radio("Origen de datos:", ("API (datos.gob.cl)", "CSV local (carpeta /data)"))

df = pd.DataFrame()
dataset_name = None

if fuente == "API (datos.gob.cl)":
    st.sidebar.info("Selecciona dataset (datos.gob.cl)")
    dataset_name = st.sidebar.selectbox("Dataset (API)", list(API_DATASETS.keys()))
    if dataset_name:
        url = API_DATASETS[dataset_name]
        with st.spinner("Descargando datos..."):
            df = fetch_api_all_records(url)
else:
    st.sidebar.info("Selecciona CSV local")
    archivos = listar_csvs()
    if not archivos:
        st.sidebar.warning("No hay archivos CSV en /data/. Súbelos al repo.")
    else:
        archivo_sel = st.sidebar.selectbox("CSV local", archivos)
        if archivo_sel:
            ruta = os.path.join(DATA_FOLDER, archivo_sel)
            df = load_csv_local(ruta)
            dataset_name = archivo_sel

# Validación
if df is None or (isinstance(df, pd.DataFrame) and df.empty):
    st.warning("No se cargaron datos. Revisa la barra lateral.")
    st.stop()

# Normalizar nombres
df = normalizar_colnames(df)

# Rellenar NA con 0 (según lo solicitado)
df = df.fillna(0)

# Intentar convertir strings numéricos
df = try_convert_numeric_columns(df)

# ----------------------------
# IDENTIFICAR columnas de delitos / meses / categoría
# ----------------------------
# Heurística: si existe columna llamada 'delitos_segun_agrupacion_por_modernizacion' -> la renombramos a 'delito'
if "delitos_segun_agrupacion_por_modernizacion" in df.columns:
    df = df.rename(columns={"delitos_segun_agrupacion_por_modernizacion": "delito"})

# Detectar columnas que son meses (contienen nombre de mes)
cols = list(df.columns)
month_cols = [c for c in cols if any(m in c for m in MESES_ORDER)]
# Si no detecta meses y hay columnas que claramente son regiones (region_...), las dejamos como están.

# Detectar columna categórica principal (delito, tipo_delito, etc.)
possible_cat_names = ["delito","tipo_delito","categoria","categoria_delito","comuna","region","nombre_delito"]
cat_col = None
for n in possible_cat_names:
    if n in df.columns:
        cat_col = n
        break

# Si no encontramos cat_col, elegir columna object con pocos valores únicos
if cat_col is None:
    object_cols = [c for c in df.columns if df[c].dtype == object and c != "_id"]
    cand = sorted(object_cols, key=lambda x: df[x].nunique() if x in df.columns else 9999)
    for c in cand:
        if df[c].nunique() <= 200:
            cat_col = c
            break

# ----------------------------
# TRANSFORMACIÓN: si hay columnas por mes -> pivot a formato largo
# ----------------------------
df_display = df.copy()  # dataframe que usaremos para mostrar / filtrar

if month_cols:
    # id_vars = todas las columnas que no son month_cols
    id_vars = [c for c in df.columns if c not in month_cols]
    # asegurarse que exista una columna categorica (preferentemente 'delito')
    if cat_col is None:
        # si 'delito' no existe, tomar primera id_var no-_id
        for c in id_vars:
            if c != "_id":
                cat_col = c
                break
    df_display = df.melt(id_vars=id_vars, value_vars=month_cols, var_name="mes", value_name="valor_mes")
    # normalizar mes y valor
    df_display["mes"] = df_display["mes"].astype(str).str.strip().str.lower()
    df_display["valor_mes"] = pd.to_numeric(df_display["valor_mes"], errors="coerce").fillna(0)

# ----------------------------
# VISTA PREVIA COMPACTA
# ----------------------------
st.subheader("Vista previa")
st.dataframe(df.head(8))

with st.expander("Columnas (ver)"):
    st.write(list(df.columns))

# ----------------------------
# RANKING — categorías más frecuentes (compacto)
# ----------------------------
st.header("🏆 Ranking — Categorías más frecuentes")
if cat_col:
    try:
        if month_cols and "valor_mes" in df_display.columns:
            rank = df_display.groupby(cat_col)["valor_mes"].sum().sort_values(ascending=False)
        else:
            num_cols = df.select_dtypes(include="number").columns.tolist()
            if num_cols:
                rank = df.groupby(cat_col)[num_cols].sum().sum(axis=1).sort_values(ascending=False)
            else:
                rank = df[cat_col].value_counts()
        st.plotly_chart(px.bar(rank.head(10).reset_index().rename(columns={cat_col:"categoria", 0:"valor"}), x=cat_col, y=rank.name or "valor"), use_container_width=True)
        st.write(rank.head(10))
    except Exception as e:
        st.error(f"Error generando ranking: {e}")
else:
    st.info("No se encontraron columnas categóricas claras (tipo_delito/comuna/region).")

# ----------------------------
# GRÁFICOS INTERACTIVOS (centrales)
# ----------------------------
st.header("📊 Gráficos interactivos (interactúa desde acá)")

# Preparar lista de columnas numéricas en df_display
numeric_cols = [c for c in df_display.select_dtypes(include="number").columns if c != "_id"]
if numeric_cols:
    sel_num = st.selectbox("Selecciona columna numérica", numeric_cols, index=0)
    # Si pivot aplicado (meses)
    if "valor_mes" in df_display.columns:
        # permitir elegir categoría para filtrar series
        if cat_col:
            opciones_cat = [None] + sorted(df_display[cat_col].astype(str).unique().tolist())
            cat_choice = st.selectbox("Selecciona categoría (opcional) para ver serie por mes", opciones_cat)
            if cat_choice:
                sub = df_display[df_display[cat_col].astype(str) == cat_choice]
            else:
                sub = df_display
        else:
            sub = df_display

        # Agrupar por mes en el orden definido
        ser = sub.groupby("mes")[sel_num].sum().reindex(MESES_ORDER).fillna(0).reset_index()
        fig = px.line(ser, x="mes", y=sel_num, title=f"{sel_num} por mes", markers=True)
        st.plotly_chart(fig, use_container_width=True)

        # Top N delitos (si cat_col existe)
        if cat_col:
            st.subheader("Top delitos (suma total)")
            top_n = st.slider("Top N", 3, 20, 7)
            top_df = df_display.groupby(cat_col)["valor_mes"].sum().reset_index().sort_values("valor_mes", ascending=False).head(top_n)
            fig2 = px.bar(top_df, x=cat_col, y="valor_mes", title=f"Top {top_n} {cat_col} (suma total)")
            st.plotly_chart(fig2, use_container_width=True)

    else:
        # sin pivot: mostramos histograma y top categorías si aplica
        fig = px.histogram(df_display, x=sel_num, nbins=30, title=f"Distribución de {sel_num}")
        st.plotly_chart(fig, use_container_width=True)

        if cat_col:
            st.subheader("Top categorías por suma")
            top_n = st.slider("Top N", 3, 20, 7)
            num_cols_all = df.select_dtypes(include="number").columns.tolist()
            if num_cols_all:
                agg = df.groupby(cat_col)[num_cols_all].sum().sum(axis=1).reset_index(name="total").sort_values("total", ascending=False).head(top_n)
                fig3 = px.bar(agg, x=cat_col, y="total", title=f"Top {top_n} {cat_col} por total")
                st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("No se detectan columnas numéricas útiles. Activa 'pivot' si tus datos vienen por meses.")

# Treemap creativo (si aplica)
if cat_col and (("valor_mes" in df_display.columns and df_display["valor_mes"].sum() > 0) or (df.select_dtypes(include="number").any().any())):
    try:
        st.subheader("🌳 Treemap — Distribución por categoría")
        if "valor_mes" in df_display.columns:
            treemap_df = df_display.groupby(cat_col)["valor_mes"].sum().reset_index().sort_values("valor_mes", ascending=False).head(200)
            fig = px.treemap(treemap_df, path=[cat_col], values="valor_mes", title="Treemap — Top categorías")
            st.plotly_chart(fig, use_container_width=True)
        else:
            num_cols_all = df.select_dtypes(include="number").columns.tolist()
            if num_cols_all:
                agg = df.groupby(cat_col)[num_cols_all].sum().sum(axis=1).reset_index(name="total").sort_values("total", ascending=False).head(200)
                fig = px.treemap(agg, path=[cat_col], values="total", title="Treemap — Top categorías")
                st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.write("No fue posible generar treemap:", e)

# ----------------------------
# TABLA FILTRADA Y DESCARGA (compacta)
# ----------------------------
st.header("🔎 Tabla filtrada / Descargar")
cols_display = [c for c in df_display.columns]
col_buscar = st.selectbox("Columna para filtrar (texto)", cols_display, index=0)
texto = st.text_input("Texto a buscar (no sensible a mayúsculas)")

df_filtrado = df_display.copy()
if texto:
    df_filtrado = df_filtrado[df_filtrado[col_buscar].astype(str).str.contains(texto, case=False, na=False)]

st.write(f"Registros: {len(df_filtrado)}")
st.dataframe(df_filtrado.head(200))

csv_bytes = df_to_csv_bytes(df_filtrado)
st.download_button("⬇️ Descargar CSV filtrado", data=csv_bytes, file_name=f"{(dataset_name or 'dataset')}_filtrado.csv", mime="text/csv")

st.caption("Si quieres quitar textos/expanders para una vista más limpia dímelo y lo simplifico.")
