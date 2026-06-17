"""Background job processor for embroidery conversion."""
import os
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any
from app.pipeline.stitchgen import run as make_pattern
from app.utils.job_store import job_store
from app.utils.errors import EmbroError

logger = logging.getLogger(__name__)
# Create a thread pool executor for CPU-bound tasks
thread_pool = ThreadPoolExecutor(max_workers=4)

async def process_job(job_id: str, file_path: str, width: float = None, height: float = None) -> Dict[str, Any]:
    """
    Process an embroidery conversion job in the background.
    Updates job status in job store when complete.
    """
    try:
        logger.info(f"Starting processing for job {job_id}")
        
        # Run the CPU-intensive task in our thread pool
        dst_path = await asyncio.get_running_loop().run_in_executor(
            thread_pool, 
            make_pattern, 
            file_path, 
            job_id,
            width,
            height
        )
        
        if not os.path.exists(dst_path):
            raise EmbroError("DST file generation failed")
            
        # Update job status
        job = job_store.complete_job(job_id, f"/download/{job_id}")
        logger.info(f"Completed processing job {job_id}")
        
        return job
        
    except Exception as e:
        logger.error(f"Error processing job {job_id}: {str(e)}")
        job_store.fail_job(job_id, str(e))
        raise
