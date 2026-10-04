"""Kafka telemetry.raw -> append-only Bronze Parquet (fixed raw schema)."""
from pyspark.sql import functions as F

from pipeline import config
from pipeline.spark_session import build


def main() -> None:
    spark = build("telemetry-raw")
    raw = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", config.KAFKA_BOOTSTRAP)
        .option("subscribe", config.TOPIC)
        .option("startingOffsets", "earliest")  # only used by a brand-new checkpoint
        .option("failOnDataLoss", "true")  # missing offsets must fail visibly
        .load()
    )
    bronze = raw.select(
        F.col("value"),
        F.col("topic"),
        F.col("partition"),
        F.col("offset"),
        F.col("timestamp").alias("kafka_timestamp"),
        F.current_timestamp().alias("ingested_at"),
    ).withColumn("ingest_date", F.to_date("ingested_at"))
    query = (
        bronze.writeStream.format("parquet")
        .option("path", str(config.BRONZE_DIR))
        .option("checkpointLocation", str(config.CHECKPOINT_DIR / "raw"))
        .partitionBy("ingest_date")
        .trigger(processingTime=f"{config.TRIGGER_SECONDS} seconds")
        .queryName("raw")
        .start()
    )
    query.awaitTermination()


if __name__ == "__main__":
    main()
