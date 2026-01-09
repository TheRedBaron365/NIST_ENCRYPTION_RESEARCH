import os
import uuid
import json
import time
from threading import Lock
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from main import final_sanitization, CHUNKSIZE

app = FastAPI(title="NIST STS Research API")

# ------------------------
# Global state (thread-safe)
# ------------------------

jobs = {}
jobs_lock = Lock()


# ------------------------
# Utilities
# ------------------------

def find_nist_path() -> str:
    """Find the NIST STS path relative to this script."""
    script_dir = os.path.dirname(os.path.abspath(__file__))

    candidates = [
        os.path.join(script_dir, "STS", "sts-2.1.2"),
        os.path.join(script_dir, "sts-2.1.2"),
        os.path.join(script_dir, "sts-2.1.2 2", "sts-2.1.2"),
    ]

    for path in candidates:
        if os.path.isdir(path):
            return path

    raise FileNotFoundError(
        "Could not find STS folder. Ensure sts-2.1.2 exists."
    )


NIST_PATH = find_nist_path()


def write_job_metadata(job_dir: str, data: dict) -> None:
    """Persist job metadata to disk."""
    meta_path = os.path.join(job_dir, "job.json")
    with open(meta_path, "w") as f:
        json.dump(data, f, indent=2)


def load_job_metadata(job_dir: str) -> dict | None:
    meta_path = os.path.join(job_dir, "job.json")
    if not os.path.exists(meta_path):
        return None
    with open(meta_path) as f:
        return json.load(f)


# ------------------------
# Background processing
# ------------------------

def process_file(
    job_id: str,
    input_path: str,
    output_path: str,
    job_dir: str,
) -> None:
    try:
        with jobs_lock:
            jobs[job_id]["status"] = "processing"
            jobs[job_id]["started_at"] = time.time()
            write_job_metadata(job_dir, jobs[job_id])

        final_sanitization(
            input_path=input_path,
            nist_path=NIST_PATH,
            chunk_size=CHUNKSIZE,
            output_path=output_path,
        )

        with jobs_lock:
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["completed_at"] = time.time()
            write_job_metadata(job_dir, jobs[job_id])

    except Exception as e:
        with jobs_lock:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = str(e)
            write_job_metadata(job_dir, jobs[job_id])


# ------------------------
# API Endpoints
# ------------------------

@app.get("/")
async def root():
    return {
        "message": "NIST STS Research API",
        "endpoints": {
            "upload": "POST /upload",
            "status": "GET /status/{job_id}",
            "download": "GET /download/{job_id}",
            "docs": "/docs",
        },
    }


@app.post("/upload")
async def upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    job_id = str(uuid.uuid4())

    job_dir = os.path.join(NIST_PATH, "jobs", job_id)
    os.makedirs(job_dir, exist_ok=True)

    input_path = os.path.join(job_dir, "input.dat")
    output_path = os.path.join(job_dir, "output.bit")

    # Stream upload to disk (no memory blowup)
    with open(input_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)

    job_data = {
        "job_id": job_id,
        "status": "pending",
        "created_at": time.time(),
        "chunksize": CHUNKSIZE,
        "nist_version": "2.1.2",
        "input_file": "input.dat",
        "output_file": "output.bit",
    }

    with jobs_lock:
        jobs[job_id] = job_data
        write_job_metadata(job_dir, job_data)

    background_tasks.add_task(
        process_file,
        job_id,
        input_path,
        output_path,
        job_dir,
    )

    return {"job_id": job_id, "status": "pending"}


@app.get("/status/{job_id}")
async def status(job_id: str):
    with jobs_lock:
        if job_id in jobs:
            return jobs[job_id]

    # Fallback to disk (server restart recovery)
    job_dir = os.path.join(NIST_PATH, "jobs", job_id)
    meta = load_job_metadata(job_dir)

    if meta is None:
        raise HTTPException(status_code=404, detail="Job not found")

    with jobs_lock:
        jobs[job_id] = meta

    return meta


@app.get("/download/{job_id}")
async def download(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)

    if job is None:
        job_dir = os.path.join(NIST_PATH, "jobs", job_id)
        job = load_job_metadata(job_dir)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")

    if job["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job not completed (status={job['status']})",
        )

    output_path = os.path.join(
        NIST_PATH, "jobs", job_id, job["output_file"]
    )

    if not os.path.exists(output_path):
        raise HTTPException(status_code=404, detail="Output file missing")

    return FileResponse(output_path, filename="output.bit")


# ------------------------
# Local entry point
# ------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
