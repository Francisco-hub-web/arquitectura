"""Ingesta CDC de líneas de ticket POS → Bronze (Iceberg, append idempotente).

Parámetros por ambiente vía argumentos del job (config externa, 15 §22); credenciales vía Secrets Manager.
"""
import json
import sys

import boto3
from awsglue.utils import getResolvedOptions
from pyspark.sql import SparkSession, functions as F

ARGS = getResolvedOptions(sys.argv, ["source_path", "target_table", "secret_id"])


def read_source_credentials(secret_id: str) -> dict:
    client = boto3.client("secretsmanager")
    return json.loads(client.get_secret_value(SecretId=secret_id)["SecretString"])


def with_audit_columns(df):
    return df.withColumn("_ingested_at", F.current_timestamp()).withColumn("_source", F.lit("pos_xstore_cdc"))


def main() -> None:
    spark = SparkSession.builder.getOrCreate()
    _ = read_source_credentials(ARGS["secret_id"])
    df = with_audit_columns(spark.read.json(ARGS["source_path"]))
    df.writeTo(ARGS["target_table"]).append()  # Bronze inmutable respecto al origen (10 §16.1)


if __name__ == "__main__":
    main()
