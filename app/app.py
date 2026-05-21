from io import BytesIO
import boto3
import pandas as pd
import plotly.express as px
import streamlit as st


BUCKET_NAME = "itam-analytics-paulo"
GOLD_KEY = "vigila-canasta/gold/inflacion_productos/inflacion_productos.parquet"


@st.cache_data
def load_gold_data():
    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=BUCKET_NAME, Key=GOLD_KEY)
    return pd.read_parquet(BytesIO(obj["Body"].read()))


st.set_page_config(
    page_title="Vigila tu Canasta",
    layout="wide",
)

st.title("Vigila tu Canasta")
st.write("Seguimiento de precios promedio e inflación de productos en Ciudad de México.")

df = load_gold_data()
df["fecha"] = pd.to_datetime(df["fecha"])

st.sidebar.header("Filtros")

subclases = sorted(df["subclase"].unique())
subclase = st.sidebar.selectbox("Subclase", subclases)

df_sub = df[df["subclase"] == subclase]

productos = sorted(df_sub["generico"].unique())
generico = st.sidebar.selectbox("Producto genérico", productos)

df_prod = df_sub[df_sub["generico"] == generico]

especificaciones = sorted(df_prod["especificacion"].unique())
especificacion = st.sidebar.selectbox("Especificación", especificaciones)

serie = df_prod[df_prod["especificacion"] == especificacion].sort_values("fecha")

st.subheader(f"{generico} - {especificacion}")

ultimo = serie.sort_values("fecha").iloc[-1]

col1, col2, col3 = st.columns(3)

col1.metric("Precio actual", f"${ultimo['precio_promedio']:,.2f}")

col2.metric(
    "Inflación mensual",
    "N/D" if pd.isna(ultimo["inflacion_mensual"]) else f"{ultimo['inflacion_mensual']:.2%}",
)

col3.metric(
    "Inflación anual",
    "N/D" if pd.isna(ultimo["inflacion_anual"]) else f"{ultimo['inflacion_anual']:.2%}",
)

fig_precio = px.line(
    serie,
    x="fecha",
    y="precio_promedio",
    markers=True,
    title="Evolución del precio promedio",
)

st.plotly_chart(fig_precio, use_container_width=True)

fig_mensual = px.bar(
    serie,
    x="fecha",
    y="inflacion_mensual",
    title="Inflación mensual",
)

st.plotly_chart(fig_mensual, use_container_width=True)

fig_anual = px.line(
    serie,
    x="fecha",
    y="inflacion_anual",
    markers=True,
    title="Inflación anual",
)

st.plotly_chart(fig_anual, use_container_width=True)

with st.expander("Ver datos"):
    st.dataframe(serie)