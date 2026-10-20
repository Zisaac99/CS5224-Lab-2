"""Follower / followee counts for the Twitter ego-network dataset (PySpark).

Each input line "A B" means user A follows user B, so:
  - B gains one follower
  - A gains one followee

Cleaning rules (the raw file is not cleaned up):
  - trim whitespace / CRLF, split on any whitespace
  - drop lines that are not exactly two numeric ids
  - drop self-loops (A follows A)
  - drop duplicate edges

Output (under --output):
  counts/       single CSV with header: user_id,followers,followees
  summary/      single-line JSON text file with cleaning / dataset statistics
                (written last, so its presence marks a complete run)

Run on EMR Serverless (or any spark-submit):
  spark-submit follow_counts.py --input s3://bucket/input/twitter_combined.txt \
                                --output s3://bucket/output/<run_id>/
"""
import argparse
import json

from pyspark.sql import SparkSession
from pyspark.sql import functions as F


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    # Ignore any extra arguments a launcher may append
    args, _ = p.parse_known_args()
    return args


def main():
    args = parse_args()
    output = args.output.rstrip("/")
    spark = SparkSession.builder.appName("twitter-follow-counts").getOrCreate()

    # 1. Read raw lines and tokenise
    lines = spark.read.text(args.input)
    tokens = lines.select(F.split(F.trim(F.col("value")), r"\s+").alias("t"))

    # 2. Keep well-formed "<id> <id>" lines
    is_valid = (
        (F.size("t") == 2)
        & F.col("t")[0].rlike(r"^\d+$")
        & F.col("t")[1].rlike(r"^\d+$")
    )
    parsed = tokens.where(is_valid).select(
        F.col("t")[0].cast("long").alias("follower"),
        F.col("t")[1].cast("long").alias("followee"),
    ).cache()

    # 3. Remove self-loops and duplicate edges
    edges = parsed.where(F.col("follower") != F.col("followee")).distinct().cache()

    # 4. Count per user
    followers = edges.groupBy(F.col("followee").alias("user_id")).agg(
        F.count("*").alias("followers")
    )
    followees = edges.groupBy(F.col("follower").alias("user_id")).agg(
        F.count("*").alias("followees")
    )

    # 5. Full outer join so users with only followers or only followees appear
    counts = (
        followers.join(followees, on="user_id", how="full_outer")
        .fillna(0, subset=["followers", "followees"])
        .orderBy("user_id")
    ).cache()

    counts.coalesce(1).write.mode("overwrite").option("header", True).csv(
        f"{output}/counts"
    )

    # 6. Summary statistics
    raw_lines = lines.count()
    valid_lines = parsed.count()
    self_loops = parsed.where(F.col("follower") == F.col("followee")).count()
    unique_edges = edges.count()
    summary = {
        "raw_lines": raw_lines,
        "malformed_lines": raw_lines - valid_lines,
        "self_loop_lines": self_loops,
        "duplicate_lines_removed": valid_lines - self_loops - unique_edges,
        "unique_edges": unique_edges,
        "users": counts.count(),
    }
    spark.createDataFrame([(json.dumps(summary),)], ["value"]).coalesce(1).write.mode(
        "overwrite"
    ).text(f"{output}/summary")

    print("SUMMARY", json.dumps(summary))
    for uid in (214328887, 107830991):
        row = counts.where(F.col("user_id") == uid).first()
        if row:
            print(f"{uid} has {row['followers']} followers")
            print(f"{uid} has {row['followees']} followees")

    spark.stop()


if __name__ == "__main__":
    main()
