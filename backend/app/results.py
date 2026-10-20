"""Load Spark output from S3 and serve lookups from memory."""
import csv
import io
import json
import threading

import boto3

from .config import settings

_s3 = boto3.client("s3", region_name=settings.aws_region)
_lock = threading.Lock()


class Results:
    def __init__(self):
        self.run_id: str | None = None
        self.counts: dict[int, tuple[int, int]] = {}
        self.summary: dict = {}

    @property
    def loaded(self) -> bool:
        return self.run_id is not None


results = Results()


def _read_first_part(prefix: str) -> str | None:
    resp = _s3.list_objects_v2(Bucket=settings.bucket, Prefix=prefix)
    for obj in resp.get("Contents", []):
        if obj["Key"].rsplit("/", 1)[-1].startswith("part-"):
            body = _s3.get_object(Bucket=settings.bucket, Key=obj["Key"])["Body"]
            return body.read().decode("utf-8")
    return None


def latest_run_id() -> str | None:
    """Most recent output/<run_id>/ that is complete (summary is written last)."""
    paginator = _s3.get_paginator("list_objects_v2")
    runs = []
    for page in paginator.paginate(Bucket=settings.bucket, Prefix=settings.output_prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if "/summary/part-" in key:
                runs.append(key[len(settings.output_prefix):].split("/", 1)[0])
    return max(runs) if runs else None


def load(run_id: str) -> None:
    base = f"{settings.output_prefix}{run_id}/"
    text = _read_first_part(f"{base}counts/")
    if text is None:
        raise FileNotFoundError(f"No counts CSV under s3://{settings.bucket}/{base}")
    counts = {
        int(r["user_id"]): (int(r["followers"]), int(r["followees"]))
        for r in csv.DictReader(io.StringIO(text))
    }
    summary_text = _read_first_part(f"{base}summary/")
    summary = json.loads(summary_text) if summary_text else {}
    with _lock:
        results.run_id, results.counts, results.summary = run_id, counts, summary


def load_latest() -> str | None:
    run_id = latest_run_id()
    if run_id:
        load(run_id)
    return run_id


def lookup(user_id: int) -> dict:
    followers, followees = results.counts.get(user_id, (0, 0))
    return {
        "user_id": str(user_id),
        "found": user_id in results.counts,
        "followers": followers,
        "followees": followees,
    }


def top(by: str, limit: int) -> list[dict]:
    idx = 0 if by == "followers" else 1
    ranked = sorted(results.counts.items(), key=lambda kv: kv[1][idx], reverse=True)[:limit]
    return [{"user_id": str(uid), "followers": f, "followees": g} for uid, (f, g) in ranked]
