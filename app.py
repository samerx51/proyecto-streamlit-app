import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(page_title="Estadísticas PDI", layout="wide")

st.title("📊 Estadísticas Policiales – PDI Chile")

# ============================
# Cargar archivo
# ============================
st.sidebar.header("Cargar archivo")
archivo = st.sidebar.file_uploader("Sube tu archivo CSV", type=["csv"])

if archivo:
    df = pd.read_csv(archivo)
    st.subheader("Vista previa de los datos")
    st.dataframe(df.head())

    # ============================
    # Variables numéricas y categóricas
    # ============================
    numericas = df.select_dtypes(include=["int64", "float64"]).columns.tolist()
    categoricas = df.select_dtypes(include=["object", "category"]).columns.tolist()

    st.sidebar.header("Opciones de análisis")

    analisis = st.sidebar.selectbox(
        "Selecciona tipo de análisis",
        ["Estadísticas descriptivas", "Gráfico de una variable", "Gráfico comparativo"]
    )

    # ============================
    # Estadísticas descriptivas
    # ============================
    if analisis == "Estadísticas descriptivas":
        st.subheader("📌 Estadísticas descriptivas")
        st.write(df.describe())

    # ============================
    # Gráfico de una variable
    # ============================
    elif analisis == "Gráfico de una variable":

        variable = st.sidebar.selectbox("Selecciona variable", df.columns)

        st.subheader(f"📉 Gráfico de {variable}")

        if st.button("Generar Gráfico"):
            fig, ax = plt.subplots()

            if variable in numericas:
                ax.hist(df[variable].dropna())
                ax.set_xlabel(variable)
                ax.set_ylabel("Frecuencia")
                ax.set_title(f"Histograma de {variable}")

            elif variable in categoricas:
                conteo = df[variable].value_counts()
                ax.bar(conteo.index, conteo.values)
                ax.set_xticklabels(conteo.index, rotation=45)
                ax.set_ylabel("Frecuencia")
                ax.set_title(f"Conteo de {variable}")

            st.pyplot(fig)

    # ============================
    # Gráfico comparativo
    # ============================
    elif analisis == "Gráfico comparativo":

        st.sidebar.write("Comparar una variable numérica según categoría")

        var_num = st.sidebar.selectbox("Variable numérica", numericas)
        var_cat = st.sidebar.selectbox("Variable categórica", categoricas)

        st.subheader(f"📊 Comparación de {var_num} según {var_cat}")

        if st.button("Generar Gráfico Comparativo"):
            fig, ax = plt.subplots()

            data = df.groupby(var_cat)[var_num].mean()

            ax.bar(data.index, data.values)
            ax.set_xticklabels(data.index, rotation=45)
            ax.set_ylabel(f"Promedio de {var_num}")
            ax.set_title(f"{var_num} promedio por categoría de {var_cat}")

            st.pyplot(fig)
