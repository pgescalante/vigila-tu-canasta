from pathlib import Path
import re
import boto3


BUCKET_NAME = "itam-analytics-paulo"
S3_PREFIX = "vigila-canasta/bronze/inegi/precios_promedio/cdmx"

LOCAL_RAW_DIR = Path("data/raw/inegi/precios_promedio/cdmx")

MONTHS = {
    "ene": "01",
    "feb": "02",
    "mar": "03",
    "abr": "04",
    "may": "05",
    "jun": "06",
    "jul": "07",
    "ago": "08",
    "sep": "09",
    "oct": "10",
    "nov": "11",
    "dic": "12",
}


def extract_year_month(filename: str) -> tuple[str, str]:
    """
    Extracts year and month from filenames like:
    INP_PP_CAB18a_2026_mar.CSV
    """
    pattern = r"_(\d{4})_([a-zA-Z]{3})"
    match = re.search(pattern, filename)

    if not match:
        raise ValueError(f"No se pudo extraer año/mes del archivo: {filename}")

    year = match.group(1)
    month_name = match.group(2).lower()

    if month_name not in MONTHS:
        raise ValueError(f"Mes no reconocido en archivo: {filename}")

    return year, MONTHS[month_name]


def upload_file_to_s3(s3_client, local_file: Path) -> None:
    year, month = extract_year_month(local_file.name)

    s3_key = (
        f"{S3_PREFIX}/"
        f"year={year}/"
        f"month={month}/"
        f"{local_file.name}"
    )

    s3_client.upload_file(
        Filename=str(local_file),
        Bucket=BUCKET_NAME,
        Key=s3_key,
    )

    print(f"Cargado: {local_file} → s3://{BUCKET_NAME}/{s3_key}")


def main() -> None:
    if not LOCAL_RAW_DIR.exists():
        raise FileNotFoundError(f"No existe la carpeta: {LOCAL_RAW_DIR}")

    csv_files = sorted(LOCAL_RAW_DIR.glob("*.CSV")) + sorted(LOCAL_RAW_DIR.glob("*.csv"))

    if not csv_files:
        raise FileNotFoundError(f"No se encontraron CSV en: {LOCAL_RAW_DIR}")

    s3_client = boto3.client("s3")

    for csv_file in csv_files:
        upload_file_to_s3(s3_client, csv_file)

    print("\nCarga Bronze terminada correctamente.")


if __name__ == "__main__":
    main()