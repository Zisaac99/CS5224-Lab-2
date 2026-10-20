"""Thin wrappers around Amazon EMR (on EC2) for job submission / status.

Each analysis run launches a transient single-node EMR cluster with one Spark step.
The cluster auto-terminates when the step finishes, so nothing idles and bills.
The cluster id doubles as the job id exposed to the frontend.
"""
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from .config import settings

_s3 = boto3.client("s3", region_name=settings.aws_region)
_emr = boto3.client("emr", region_name=settings.aws_region)

_ACTIVE_CLUSTER_STATES = ["STARTING", "BOOTSTRAPPING", "RUNNING", "WAITING", "TERMINATING"]


def _s3_uri(key: str) -> str:
    return f"s3://{settings.bucket}/{key}"


def _ensure_object(key: str, local_path: str) -> None:
    """Upload a local file to S3 if the object does not exist yet."""
    try:
        _s3.head_object(Bucket=settings.bucket, Key=key)
    except ClientError as e:
        if e.response["Error"]["Code"] not in ("404", "NoSuchKey", "NotFound"):
            raise
        path = Path(local_path)
        if not path.exists():
            raise FileNotFoundError(f"{_s3_uri(key)} missing and no local copy at {path}")
        _s3.upload_file(str(path), settings.bucket, key)


def _job_state(cluster_state: str, step_state: str | None) -> str:
    """Collapse cluster + step state into one job state for the UI."""
    if step_state == "COMPLETED":
        return "SUCCESS"
    if step_state in ("FAILED", "CANCELLED", "INTERRUPTED") or cluster_state == "TERMINATED_WITH_ERRORS":
        return "FAILED"
    if cluster_state == "TERMINATED":  # terminated before the step ran
        return "CANCELLED"
    if step_state == "RUNNING":
        return "RUNNING"
    return cluster_state  # STARTING / BOOTSTRAPPING / RUNNING (step pending)


def start_job() -> dict:
    _ensure_object(settings.input_key, settings.local_dataset)
    _ensure_object(settings.script_key, settings.local_script)

    # The account vCPU quota only fits one cluster at a time
    active = _emr.list_clusters(ClusterStates=_ACTIVE_CLUSTER_STATES)["Clusters"]
    if any(c["Name"].startswith(settings.cluster_name_prefix) for c in active):
        raise RuntimeError("An analysis cluster is already running - wait for it to finish")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_uri = _s3_uri(f"{settings.output_prefix}{run_id}/")
    resp = _emr.run_job_flow(
        Name=f"{settings.cluster_name_prefix}{run_id}",
        ReleaseLabel=settings.emr_release,
        Applications=[{"Name": "Spark"}],
        LogUri=_s3_uri(f"{settings.logs_prefix}emr/"),
        Instances={
            "InstanceGroups": [
                {
                    "Name": "primary",
                    "InstanceRole": "MASTER",
                    "InstanceType": settings.emr_instance_type,
                    "InstanceCount": 1,
                }
            ],
            "KeepJobFlowAliveWhenNoSteps": False,  # auto-terminate after the step
        },
        Steps=[
            {
                "Name": "follow-counts",
                "ActionOnFailure": "TERMINATE_CLUSTER",
                "HadoopJarStep": {
                    "Jar": "command-runner.jar",
                    "Args": [
                        "spark-submit", "--deploy-mode", "cluster",
                        _s3_uri(settings.script_key),
                        "--input", _s3_uri(settings.input_key),
                        "--output", output_uri,
                    ],
                },
            }
        ],
        ServiceRole=settings.emr_service_role,
        JobFlowRole=settings.emr_instance_profile,
        VisibleToAllUsers=True,
        Tags=[{"Key": "project", "Value": "cs5224-lab2"}, {"Key": "run_id", "Value": run_id}],
    )
    return {"job_run_id": resp["JobFlowId"], "run_id": run_id, "output": output_uri}


def get_job(cluster_id: str) -> dict:
    cluster = _emr.describe_cluster(ClusterId=cluster_id)["Cluster"]
    steps = _emr.list_steps(ClusterId=cluster_id)["Steps"]
    step = steps[0] if steps else None
    status = cluster["Status"]
    timeline = status.get("Timeline", {})
    updated = timeline.get("EndDateTime") or timeline.get("ReadyDateTime") or timeline["CreationDateTime"]
    details = ""
    if step and step["Status"].get("FailureDetails"):
        details = step["Status"]["FailureDetails"].get("Message", "")
    elif status.get("StateChangeReason", {}).get("Message"):
        details = status["StateChangeReason"]["Message"]
    return {
        "job_run_id": cluster["Id"],
        "name": cluster["Name"],
        "state": _job_state(status["State"], step["Status"]["State"] if step else None),
        "cluster_state": status["State"],
        "step_state": step["Status"]["State"] if step else None,
        "state_details": details,
        "created_at": timeline["CreationDateTime"].isoformat(),
        "updated_at": updated.isoformat(),
        "run_id": next((t["Value"] for t in cluster.get("Tags", []) if t["Key"] == "run_id"), None),
    }


def list_jobs(limit: int = 10) -> list[dict]:
    clusters = _emr.list_clusters()["Clusters"]
    ours = [c for c in clusters if c["Name"].startswith(settings.cluster_name_prefix)][:limit]
    jobs = []
    for c in ours:
        status = c["Status"]
        state = status["State"]
        if state == "TERMINATED" and status.get("StateChangeReason", {}).get("Code") == "ALL_STEPS_COMPLETED":
            state = "SUCCESS"
        elif state == "TERMINATED_WITH_ERRORS":
            state = "FAILED"
        jobs.append({
            "job_run_id": c["Id"],
            "name": c["Name"],
            "state": state,
            "created_at": status["Timeline"]["CreationDateTime"].isoformat(),
            "updated_at": (status["Timeline"].get("EndDateTime")
                           or status["Timeline"]["CreationDateTime"]).isoformat(),
        })
    return jobs
