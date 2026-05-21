from io import BytesIO
from pathlib import Path

import boto3
import pandas as pd


BUCKET_NAME = "itam-analytics-paulo"

SILVER_PREFIX = "vigila-canasta/silver/inegi/precios_promedio/cdmx/"
GOLD_PREFIX = "vigila-canasta/gold/inflacion_productos/"


def list_silver_parquets(s3_client):
    response = s3_client.list_objects_v2(
        Bucket=BUCKET_NAME,
        Prefix=SILVER_PREFIX,
    )

    objects = response.get("Contents", [])

    return [
        obj["Key"]
        for obj in objects
        if obj["Key"].endswith(".parquet")
    ]


def read_parquet_from_s3(s3_client, key):
    response = s3_client.get_object(Bucket=BUCKET_NAME, Key=key)

    return pd.read_parquet(
        BytesIO(response["Body"].read())
    )


def load_silver_data(s3_client):
    parquet_files = list_silver_parquets(s3_client)

    dfs = []

    for key in parquet_files:
        print(f"Leyendo: s3://{BUCKET_NAME}/{key}")

        df_temp = read_parquet_from_s3(s3_client, key)
        dfs.append(df_temp)

    df = pd.concat(dfs, ignore_index=True)

    return df


def filter_active_products(df):
    """
    Conserva productos observados
    dentro de los últimos 12 meses.
    """

    max_date = df["fecha"].max()

    cutoff_date = max_date - pd.DateOffset(months=12)

    latest_dates = (
        df.groupby("producto_id")["fecha"]
        .max()
        .reset_index()
    )

    active_products = latest_dates.loc[
        latest_dates["fecha"] >= cutoff_date,
        "producto_id"
    ]

    df = df[df["producto_id"].isin(active_products)]

    return df


def calculate_inflation(df):
    df = df.sort_values(
        by=["producto_id", "fecha"]
    ).copy()

    df["precio_anterior"] = (
        df.groupby("producto_id")["precio_promedio"]
        .shift(1)
    )

    df["precio_12_meses"] = (
        df.groupby("producto_id")["precio_promedio"]
        .shift(12)
    )

    df["inflacion_mensual"] = (
        (df["precio_promedio"] - df["precio_anterior"])
        / df["precio_anterior"]
    )

    df["inflacion_anual"] = (
        (df["precio_promedio"] - df["precio_12_meses"])
        / df["precio_12_meses"]
    )

    return df


def write_gold_parquet(s3_client, df):
    output_key = (
        f"{GOLD_PREFIX}"
        f"inflacion_productos.parquet"
    )

    buffer = BytesIO()

    df.to_parquet(
        buffer,
        index=False,
        engine="pyarrow"
    )

    buffer.seek(0)

    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=output_key,
        Body=buffer.getvalue(),
    )

    print(
        f"\nGold creado correctamente:\n"
        f"s3://{BUCKET_NAME}/{output_key}"
    )


def main():
    s3_client = boto3.client("s3")

    print("\nCargando Silver...")
    df = load_silver_data(s3_client)

    print(f"Filas iniciales: {len(df):,}")

    print("\nFiltrando productos activos...")
    df = filter_active_products(df)

    print(f"Filas después del filtro: {len(df):,}")

    print("\nCalculando inflación...")
    df = calculate_inflation(df)

    final_columns = [
        "fecha",
        "producto_id",
        "subclase",
        "generico",
        "especificacion",
        "precio_promedio",
        "precio_anterior",
        "precio_12_meses",
        "inflacion_mensual",
        "inflacion_anual",
        "cantidad",
        "unidad",
    ]

    df = df[final_columns]

    print("\nEscribiendo Gold...")
    write_gold_parquet(s3_client, df)

    print("\nProceso Gold terminado correctamente.")


if __name__ == "__main__":
    main()