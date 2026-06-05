"""Status check endpoint for embroidery conversion jobs."""
from fastapi import APIRouter, HTTPException
from app.utils.job_store import job_store
import logging

# logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/status/{job_id}")
async def get_status(job_id: str):
    """
    Check the status of a conversion job.
    Returns job details including status and download URL if complete.
    """
    job = job_store.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    # Return full job info except internal fields
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "download": job["download"],
        "file_info": job["file_info"],
        "error": job["error"] if job["status"] == "failed" else None
    }
