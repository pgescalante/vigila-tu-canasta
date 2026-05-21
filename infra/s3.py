import boto3

BUCKET_NAME = "itam-analytics-paulo"
REGION = "us-east-1"

PREFIXES = [
    "vigila-canasta/bronze/",
    "vigila-canasta/silver/",
    "vigila-canasta/gold/",
    "vigila-canasta/artifacts/",
]


def create_prefixes(s3_client):
    for prefix in PREFIXES:
        s3_client.put_object(Bucket=BUCKET_NAME, Key=prefix)
        print(f"Prefijo creado: s3://{BUCKET_NAME}/{prefix}")


def main():
    s3_client = boto3.client("s3", region_name=REGION)
    create_prefixes(s3_client)
    print("\nEstructura base S3 creada correctamente.")


if __name__ == "__main__":
    main()