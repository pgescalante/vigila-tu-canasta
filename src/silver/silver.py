from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import hashlib
import boto3
import pandas as pd


BUCKET_NAME = "itam-analytics-paulo"

BRONZE_PREFIX = "vigila-canasta/bronze/inegi/precios_promedio/cdmx/"
SILVER_PREFIX = "vigila-canasta/silver/inegi/precios_promedio/cdmx/"

ENCODING = "latin-1"
SKIPROWS = 5


COLUMN_RENAME = {
    "Año": "anio",
    "Mes": "mes",
    "Subclase": "subclase",
    "Genérico": "generico",
    "Especificación": "especificacion",
    "Precio promedio": "precio_promedio",
    "Cantidad": "cantidad",
    "Unidad": "unidad",
}


KEEP_COLUMNS = list(COLUMN_RENAME.keys())


def list_bronze_csv_files(s3_client):
    response = s3_client.list_objects_v2(
        Bucket=BUCKET_NAME,
        Prefix=BRONZE_PREFIX,
    )

    objects = response.get("Contents", [])

    return [
        obj["Key"]
        for obj in objects
        if obj["Key"].lower().endswith(".csv")
    ]


def read_csv_from_s3(s3_client, key):
    response = s3_client.get_object(Bucket=BUCKET_NAME, Key=key)
    body = response["Body"].read()

    # Conteo aproximado de filas esperadas
    raw_lines = body.decode(ENCODING, errors="ignore").splitlines()

    expected_data_rows = len(raw_lines) - SKIPROWS - 1

    df = pd.read_csv(
        BytesIO(body),
        encoding=ENCODING,
        skiprows=SKIPROWS,
        engine="python",
        on_bad_lines="skip",
    )

    loaded_rows = len(df)

    skipped_rows = expected_data_rows - loaded_rows

    if skipped_rows > 0:
        print(
            f"[WARNING] {skipped_rows} filas problemáticas "
            f"fueron omitidas en: {key}"
        )

    return df


def create_producto_id(row):
    text = (
        f"{row['subclase']}|"
        f"{row['generico']}|"
        f"{row['especificacion']}|"
        f"{row['cantidad']}|"
        f"{row['unidad']}"
    )

    return hashlib.md5(text.encode("utf-8")).hexdigest()


def clean_dataframe(df, source_key):
    missing_columns = [col for col in KEEP_COLUMNS if col not in df.columns]

    if missing_columns:
        raise ValueError(
            f"Faltan columnas en {source_key}: {missing_columns}"
        )

    df = df[KEEP_COLUMNS].copy()
    df = df.rename(columns=COLUMN_RENAME)

    df["anio"] = pd.to_numeric(df["anio"], errors="coerce").astype("Int64")
    df["mes"] = pd.to_numeric(df["mes"], errors="coerce").astype("Int64")

    df["precio_promedio"] = (
        df["precio_promedio"]
        .astype(str)
        .str.replace(",", "", regex=False)
    )
    df["precio_promedio"] = pd.to_numeric(
        df["precio_promedio"],
        errors="coerce",
    )

    df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce")

    text_columns = ["subclase", "generico", "especificacion", "unidad"]

    for col in text_columns:
        df[col] = (
            df[col]
            .astype(str)
            .str.strip()
        )

    df["fecha"] = pd.to_datetime(
        df["anio"].astype(str) + "-" + df["mes"].astype(str) + "-01",
        errors="coerce",
    )

    df["producto_id"] = df.apply(create_producto_id, axis=1)

    df["source_file"] = Path(source_key).name
    df["source_s3_key"] = source_key
    df["load_timestamp"] = datetime.now(timezone.utc).isoformat()

    df = df[
        [
            "fecha",
            "anio",
            "mes",
            "subclase",
            "generico",
            "especificacion",
            "producto_id",
            "precio_promedio",
            "cantidad",
            "unidad",
            "source_file",
            "source_s3_key",
            "load_timestamp",
        ]
    ]

    return df


def write_parquet_to_s3(s3_client, df, source_key):
    year = int(df["anio"].dropna().iloc[0])
    month = int(df["mes"].dropna().iloc[0])

    source_name = Path(source_key).stem
    output_key = (
        f"{SILVER_PREFIX}"
        f"year={year}/"
        f"month={month:02d}/"
        f"{source_name}.parquet"
    )

    buffer = BytesIO()
    df.to_parquet(buffer, index=False, engine="pyarrow")
    buffer.seek(0)

    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=output_key,
        Body=buffer.getvalue(),
    )

    print(f"Silver creado: s3://{BUCKET_NAME}/{output_key}")


def main():
    s3_client = boto3.client("s3")

    bronze_files = list_bronze_csv_files(s3_client)

    if not bronze_files:
        raise FileNotFoundError(
            f"No se encontraron CSV en s3://{BUCKET_NAME}/{BRONZE_PREFIX}"
        )

    print(f"Archivos Bronze encontrados: {len(bronze_files)}")

    for key in bronze_files:
        print(f"\nProcesando: s3://{BUCKET_NAME}/{key}")

        raw_df = read_csv_from_s3(s3_client, key)
        silver_df = clean_dataframe(raw_df, key)
        write_parquet_to_s3(s3_client, silver_df, key)

    print("\nProceso Silver terminado correctamente.")


if __name__ == "__main__":
    main()