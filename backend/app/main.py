import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import emr
from . import results as res
from .config import settings

log = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        log.info("Loaded results run: %s", res.load_latest())
    except Exception as e:  # keep serving; a job can still be triggered
        log.warning("Could not load results on startup: %s", e)
    yield


app = FastAPI(title="CS5224 Lab 2 - Twitter follow counts", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _require_results() -> None:
    if not res.results.loaded:
        raise HTTPException(503, "No analysis results loaded yet - run a job first")


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "results_run_id": res.results.run_id,
        "users_loaded": len(res.results.counts),
    }


@app.get("/api/users")
def users(ids: str = Query(..., description="Comma-separated user ids")):
    _require_results()
    try:
        parsed = [int(i) for i in ids.replace(" ", "").split(",") if i]
    except ValueError:
        raise HTTPException(400, "ids must be comma-separated integers")
    return {"run_id": res.results.run_id, "users": [res.lookup(i) for i in parsed]}


@app.get("/api/users/{user_id}")
def user(user_id: int):
    _require_results()
    return res.lookup(user_id)


@app.get("/api/top")
def top(by: str = Query("followers", pattern="^(followers|followees)$"),
        limit: int = Query(10, ge=1, le=100)):
    _require_results()
    return {"by": by, "users": res.top(by, limit)}


@app.get("/api/summary")
def summary():
    _require_results()
    return {"run_id": res.results.run_id, **res.results.summary}


@app.post("/api/jobs", status_code=202)
def start_job():
    try:
        return emr.start_job()
    except Exception as e:
        raise HTTPException(500, f"Failed to start EMR job: {e}")


@app.get("/api/jobs")
def list_jobs(limit: int = Query(10, ge=1, le=50)):
    return {"jobs": emr.list_jobs(limit)}


@app.get("/api/jobs/{job_run_id}")
def get_job(job_run_id: str):
    job = emr.get_job(job_run_id)
    if job["state"] == "SUCCESS" and job["run_id"] and job["run_id"] != res.results.run_id:
        res.load(job["run_id"])
    job["results_run_id"] = res.results.run_id
    return job
