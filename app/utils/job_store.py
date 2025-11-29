"""Job store with Redis for persistent job state across container restarts."""
import redis
import json
from typing import Dict, Optional, Any
from datetime import datetime
import logging
from os import getenv

logger = logging.getLogger(__name__)

# Connect to Redis
redis_host = getenv("REDIS_HOST", "redis")
redis_port = int(getenv("REDIS_PORT", "6379"))

try:
    redis_client = redis.Redis(
        host=redis_host,
        port=redis_port,
        decode_responses=True,
        socket_connect_timeout=5
    )
    redis_client.ping()
    logger.info(f"Connected to Redis at {redis_host}:{redis_port}")
except Exception as e:
    logger.error(f"Failed to connect to Redis: {e}")
    redis_client = None

class JobStore:
    def __init__(self):
        self.redis = redis_client
        
    def create_job(self, job_id: str, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new job entry in Redis."""
        job = {
            "job_id": job_id,
            "status": "pending",
            "file_info": file_info,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "download": None,
            "error": None
        }
        if self.redis:
            self.redis.set(f"job:{job_id}", json.dumps(job), ex=86400)  # 24hr TTL
        logger.info(f"Created job {job_id}")
        return job
        
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job details from Redis."""
        if not self.redis:
            return None
        data = self.redis.get(f"job:{job_id}")
        return json.loads(data) if data else None
        
    def update_job(self, job_id: str, **updates) -> Optional[Dict[str, Any]]:
        """Update job in Redis."""
        if not self.redis:
            return None
            
        job = self.get_job(job_id)
        if not job:
            return None
            
        job.update(updates)
        job["updated_at"] = datetime.utcnow().isoformat()
        self.redis.set(f"job:{job_id}", json.dumps(job), ex=86400)
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
