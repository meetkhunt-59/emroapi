"""Download endpoint for completed embroidery files."""
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from app.utils.job_store import job_store
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

OUTPUT_DIR = "storage/outputs"

@router.get("/download/{job_id}")
async def download(job_id: str):
    """
    Download the generated DST file.
    Only available for completed jobs.
    """
    # Check job status
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if job["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job not ready (status: {job['status']})"
        )
    
    # Serve file
    file_path = os.path.join(OUTPUT_DIR, f"{job_id}.dst")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    return FileResponse(
        file_path,
        media_type="application/octet-stream",
        filename=f"{job_id}.dst",
        headers={"Cache-Control": "no-cache"}
    )
