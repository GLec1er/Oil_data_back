from pyspark.sql import types as T


def bronze_struct() -> T.StructType:
    return T.StructType(
        [
            T.StructField("value", T.BinaryType()),
            T.StructField("topic", T.StringType()),
            T.StructField("partition", T.IntegerType()),
            T.StructField("offset", T.LongType()),
            T.StructField("kafka_timestamp", T.TimestampType()),
            T.StructField("ingested_at", T.TimestampType()),
        ]
    )
