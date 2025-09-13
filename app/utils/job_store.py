"""Simple in-memory job store (can be replaced with Redis/PostgreSQL later)."""
from typing import Dict, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class JobStore:
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}
        
    def create_job(self, job_id: str, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new job entry."""
        job = {
            "job_id": job_id,
            "status": "pending",
            "file_info": file_info,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "download": None,
            "error": None
        }
        self._store[job_id] = job
        logger.info(f"Created job {job_id}")
        return job
        
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job details by ID."""
        return self._store.get(job_id)
        
    def update_job(self, job_id: str, **updates) -> Optional[Dict[str, Any]]:
        """Update job details."""
        if job_id not in self._store:
            return None
            
        job = self._store[job_id]
        job.update(updates)
        job["updated_at"] = datetime.utcnow().isoformat()
        logger.info(f"Updated job {job_id}: {updates}")
        return job
        
    def complete_job(self, job_id: str, download_path: str) -> Optional[Dict[str, Any]]:
        """Mark job as completed."""
        return self.update_job(
            job_id,
            status="completed",
            download=download_path
        )
        
    def fail_job(self, job_id: str, error: str) -> Optional[Dict[str, Any]]:
        """Mark job as failed."""
        return self.update_job(
            job_id,
            status="failed",
            error=error
        )

# Global job store instance
job_store = JobStore()
