from datetime import datetime, timezone
from io import BytesIO
import json
import uuid

import boto3
import pandas as pd
import plotly.express as px
import streamlit as st


BUCKET_NAME = "itam-analytics-paulo"
GOLD_KEY = "vigila-canasta/gold/inflacion_productos/inflacion_productos.parquet"
BASKETS_PREFIX = "vigila-canasta/app/canastas/"


@st.cache_data
def load_data():
    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=BUCKET_NAME, Key=GOLD_KEY)
    df = pd.read_parquet(BytesIO(obj["Body"].read()))

    df["fecha"] = pd.to_datetime(df["fecha"])
    df["subclase_limpia"] = (
        df["subclase"].astype(str).str.replace(r"^\d+\s*", "", regex=True).str.strip()
    )
    df["generico_limpio"] = df["generico"].astype(str).str.strip()
    df["producto_nombre"] = df["especificacion"].astype(str).str.strip()
    df["producto_selector"] = (
        df["producto_nombre"]
        + " | "
        + df["cantidad"].astype(str)
        + " "
        + df["unidad"].astype(str)
    )
    return df


def get_latest_data(df):
    latest_date = df["fecha"].max()
    latest = df[df["fecha"] == latest_date].copy()
    latest_unique = (
        latest.sort_values("precio_promedio")
        .drop_duplicates(subset=["generico_limpio", "producto_selector"], keep="first")
        .copy()
    )
    return latest_unique, latest_date


def save_basket_to_s3(basket_name, product_ids):
    s3 = boto3.client("s3")

    basket_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    payload = {
        "basket_id": basket_id,
        "basket_name": basket_name,
        "created_at": created_at,
        "product_ids": product_ids,
    }

    key = f"{BASKETS_PREFIX}{basket_id}.json"

    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json",
    )

    return payload


@st.cache_data(ttl=30)
def list_saved_baskets():
    s3 = boto3.client("s3")

    response = s3.list_objects_v2(
        Bucket=BUCKET_NAME,
        Prefix=BASKETS_PREFIX,
    )

    baskets = []

    for obj in response.get("Contents", []):
        key = obj["Key"]

        if not key.endswith(".json"):
            continue

        body = s3.get_object(Bucket=BUCKET_NAME, Key=key)["Body"].read()
        payload = json.loads(body.decode("utf-8"))
        payload["s3_key"] = key
        baskets.append(payload)

    baskets = sorted(baskets, key=lambda x: x["created_at"], reverse=True)
    return baskets


def build_product_history(df, product_ids):
    history = df[df["producto_id"].isin(product_ids)].copy()

    history["serie_producto"] = (
        history["generico_limpio"] + " | " + history["producto_selector"]
    )

    history = (
        history.groupby(["fecha", "serie_producto"], as_index=False)
        .agg(precio_promedio=("precio_promedio", "mean"))
        .sort_values(["serie_producto", "fecha"])
    )

    return history


def build_basket_history(product_history):
    return (
        product_history.groupby("fecha", as_index=False)
        .agg(costo_canasta=("precio_promedio", "sum"))
        .sort_values("fecha")
    )


def optimize_basket(latest, basket_df):
    optimized_rows = []

    for generico in basket_df["generico_limpio"].unique():
        candidates = latest[latest["generico_limpio"] == generico].copy()
        candidates = candidates.dropna(subset=["inflacion_mensual"])

        if candidates.empty:
            continue

        best = candidates.sort_values("inflacion_mensual").iloc[0]
        optimized_rows.append(best)

    if not optimized_rows:
        return pd.DataFrame()

    return pd.DataFrame(optimized_rows)


st.set_page_config(page_title="Vigila tu Canasta", layout="wide")
st.title("Vigila tu Canasta")

df = load_data()
latest, latest_date = get_latest_data(df)

if "basket_ids" not in st.session_state:
    st.session_state["basket_ids"] = []

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "1. Construir canasta",
        "2. Ver evolución",
        "3. Optimizar canasta",
        "4. Canastas guardadas",
    ]
)

with tab1:
    st.header("Construye tu canasta")

    col_a, col_b = st.columns([1, 2])

    with col_a:
        genericos = sorted(latest["generico_limpio"].dropna().unique())
        selected_generico = st.selectbox("Producto genérico", genericos)

    available_specs = (
        latest[latest["generico_limpio"] == selected_generico]
        .copy()
        .sort_values("producto_selector")
    )

    product_options = (
        available_specs[["producto_id", "producto_selector"]]
        .drop_duplicates(subset=["producto_selector"])
        .sort_values("producto_selector")
    )

    selector_to_id = dict(
        zip(product_options["producto_selector"], product_options["producto_id"])
    )

    with col_b:
        selected_specs = st.multiselect(
            "Especificación, cantidad y unidad",
            product_options["producto_selector"].tolist(),
            placeholder="Selecciona una o varias opciones",
        )

    selected_ids = [selector_to_id[name] for name in selected_specs]

    col_btn1, col_btn2 = st.columns([1, 1])

    with col_btn1:
        if st.button("Agregar productos a la canasta"):
            st.session_state["basket_ids"] = sorted(
                list(set(st.session_state["basket_ids"] + selected_ids))
            )

    with col_btn2:
        if st.button("Limpiar canasta"):
            st.session_state["basket_ids"] = []

    basket_ids = st.session_state["basket_ids"]

    st.subheader("Resumen de canasta seleccionada")

    if not basket_ids:
        st.info("Todavía no has agregado productos.")
    else:
        basket_current = latest[latest["producto_id"].isin(basket_ids)].copy()
        total = basket_current["precio_promedio"].sum()

        col1, col2, col3 = st.columns(3)
        col1.metric("Gasto total actual", f"${total:,.2f}")
        col2.metric("Productos seleccionados", basket_current["producto_id"].nunique())
        col3.metric("Fecha de precios", latest_date.strftime("%Y-%m-%d"))

        basket_name = st.text_input(
            "Nombre de la canasta",
            placeholder="Ejemplo: Canasta semanal básica",
        )

        if st.button("Guardar canasta"):
            if not basket_name.strip():
                st.warning("Escribe un nombre para guardar la canasta.")
            else:
                saved = save_basket_to_s3(basket_name.strip(), basket_ids)
                list_saved_baskets.clear()
                st.success(f"Canasta guardada: {saved['basket_name']}")

        st.dataframe(
            basket_current[
                [
                    "generico_limpio",
                    "producto_nombre",
                    "cantidad",
                    "unidad",
                    "precio_promedio",
                    "inflacion_mensual",
                    "inflacion_anual",
                ]
            ].rename(
                columns={
                    "generico_limpio": "Genérico",
                    "producto_nombre": "Especificación",
                    "cantidad": "Cantidad",
                    "unidad": "Unidad",
                    "precio_promedio": "Precio promedio",
                    "inflacion_mensual": "Inflación mensual",
                    "inflacion_anual": "Inflación anual",
                }
            ),
            use_container_width=True,
        )

with tab2:
    st.header("Evolución histórica de la canasta")

    basket_ids = st.session_state["basket_ids"]

    if not basket_ids:
        st.info("Primero construye una canasta en la pestaña 1.")
    else:
        product_history = build_product_history(df, basket_ids)
        basket_history = build_basket_history(product_history)

        fig_basket = px.line(
            basket_history,
            x="fecha",
            y="costo_canasta",
            markers=True,
            title="Costo total de la canasta seleccionada",
            labels={
                "fecha": "Fecha",
                "costo_canasta": "Costo total de la canasta",
            },
        )
        st.plotly_chart(fig_basket, use_container_width=True)

        fig_products = px.line(
            product_history,
            x="fecha",
            y="precio_promedio",
            color="serie_producto",
            markers=True,
            title="Precio promedio por producto seleccionado",
            labels={
                "fecha": "Fecha",
                "precio_promedio": "Precio promedio",
                "serie_producto": "Producto",
            },
        )
        st.plotly_chart(fig_products, use_container_width=True)

with tab3:
    st.header("Optimizar canasta")

    basket_ids = st.session_state["basket_ids"]

    if not basket_ids:
        st.info("Primero construye una canasta en la pestaña 1.")
    else:
        basket_current = latest[latest["producto_id"].isin(basket_ids)].copy()

        st.write(
            "La optimización busca, dentro de cada producto genérico seleccionado, "
            "la especificación con menor inflación mensual reciente."
        )

        if st.button("Optimizar canasta"):
            optimized = optimize_basket(latest, basket_current)

            if optimized.empty:
                st.warning("No se pudo generar una canasta optimizada.")
            else:
                original_total = basket_current["precio_promedio"].sum()
                optimized_total = optimized["precio_promedio"].sum()

                col1, col2, col3 = st.columns(3)
                col1.metric("Canasta original", f"${original_total:,.2f}")
                col2.metric("Canasta optimizada", f"${optimized_total:,.2f}")
                col3.metric("Diferencia", f"${optimized_total - original_total:,.2f}")

                st.subheader("Canasta optimizada")

                st.dataframe(
                    optimized[
                        [
                            "generico_limpio",
                            "producto_nombre",
                            "cantidad",
                            "unidad",
                            "precio_promedio",
                            "inflacion_mensual",
                        ]
                    ].rename(
                        columns={
                            "generico_limpio": "Genérico",
                            "producto_nombre": "Especificación",
                            "cantidad": "Cantidad",
                            "unidad": "Unidad",
                            "precio_promedio": "Precio promedio",
                            "inflacion_mensual": "Inflación mensual",
                        }
                    ),
                    use_container_width=True,
                )

with tab4:
    st.header("Canastas guardadas")

    baskets = list_saved_baskets()

    if not baskets:
        st.info("Todavía no hay canastas guardadas.")
    else:
        options = {
            f"{b['basket_name']} | {b['created_at'][:10]}": b for b in baskets
        }

        selected_label = st.selectbox(
            "Selecciona una canasta guardada",
            list(options.keys()),
        )

        selected_basket = options[selected_label]

        if st.button("Cargar canasta seleccionada"):
            st.session_state["basket_ids"] = selected_basket["product_ids"]
            st.success(f"Canasta cargada: {selected_basket['basket_name']}")

        st.json(
            {
                "basket_name": selected_basket["basket_name"],
                "created_at": selected_basket["created_at"],
                "products_count": len(selected_basket["product_ids"]),
            }
        )