"""Watches committed Bronze files and republishes a full snapshot per micro-batch."""
from pyspark.sql import DataFrame

from pipeline import config
from pipeline.snapshot import materialize
from pipeline.spark_session import build
from pipeline.spark_types import bronze_struct

QUERY_NAME = "materializer"


def snapshot_id_for(batch_id: int) -> str:
    return f"{QUERY_NAME}-{batch_id:010d}"


def publish_batch(_: DataFrame, batch_id: int) -> None:
    # foreachBatch is at-least-once: the snapshot id derives from batch_id, so a
    # retry re-activates the existing snapshot instead of writing a second one.
    # The batch DataFrame only signals new files; content is rebuilt from all of
    # Bronze so late events correct their original hour and day.
    materialize(config.BRONZE_DIR, config.MARTS_DIR, snapshot_id_for(batch_id))


def main() -> None:
    spark = build("telemetry-materializer")
    config.BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    stream = spark.readStream.schema(bronze_struct()).parquet(str(config.BRONZE_DIR))
    query = (
        stream.writeStream.foreachBatch(publish_batch)
        .option("checkpointLocation", str(config.CHECKPOINT_DIR / QUERY_NAME))
        .trigger(processingTime=f"{config.TRIGGER_SECONDS} seconds")
        .queryName(QUERY_NAME)
        .start()
    )
    query.awaitTermination()


if __name__ == "__main__":
    main()
