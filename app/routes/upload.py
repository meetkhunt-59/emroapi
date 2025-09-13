"""Upload endpoint for embroidery conversion."""
import os
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException
from app.utils.validators import validate_file_size, validate_mime_type, validate_image_content
from app.utils.job_store import job_store
from app.workers.processor import process_job
from app.utils.image_utils import count_real_colors
from app.pipeline.config import MAX_COLORS
import uuid
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

UPLOAD_DIR = "storage/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
async def upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    Upload a file for embroidery conversion.
    Returns a job ID immediately and processes in background.
    """
    # Generate job ID first thing
    job_id = str(uuid.uuid4())
    logger.info(f"Generated job ID: {job_id}")
    
    try:
        # Read and validate file
        content = await file.read()
        
        validate_file_size(len(content))
        mime_type, ext = validate_mime_type(content)
        validate_image_content(content, mime_type)
        
        # Save file temporarily for color analysis
        temp_path = os.path.join(UPLOAD_DIR, f"temp_{file.filename}")
        try:
            with open(temp_path, "wb") as f:
                f.write(content)
            
            # Check color count
            color_count = count_real_colors(temp_path)
            if color_count > MAX_COLORS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Image contains {color_count} distinct colors (similar shades are counted as one color). Maximum allowed is {MAX_COLORS}. Please simplify the image."
                )
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
        # Store file info
        file_info = {
            "original_name": file.filename,
            "mime_type": mime_type,
            "size": len(content)
        }
        
        # Create job entry immediately
        job = job_store.create_job(job_id, file_info)
        
        # Save file
        file_path = os.path.join(UPLOAD_DIR, f"{job_id}_{file.filename}")
        with open(file_path, "wb") as f:
            f.write(content)
            
        # Add processing to background tasks
        background_tasks.add_task(process_job, job_id, file_path)
        
        # Return response immediately
        response = {
            "job_id": job_id,
            "status": "pending",
            "message": "File uploaded and queued for processing. Use status endpoint to check progress.",
            "status_url": f"/status/{job_id}"
        }
        
        logger.info(f"Returning immediate response for job {job_id}")
        return response
        
        # Return immediately with job ID
        return {
            "job_id": job_id,
            "status": "pending",
            "message": "File uploaded successfully. Use /status/{job_id} to check processing status.",
            "status_url": f"/status/{job_id}"
        }
        
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        raise
