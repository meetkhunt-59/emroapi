from fastapi import HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from starlette.status import HTTP_403_FORBIDDEN
from os import getenv
from datetime import datetime, timedelta
from collections import defaultdict
import time

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
request_counts = defaultdict(list)

def get_api_key(api_key_header: str = Security(api_key_header)) -> str:
    if api_key_header == getenv("API_KEY"):
        return api_key_header
    raise HTTPException(
        status_code=HTTP_403_FORBIDDEN, detail="Could not validate API key"
    )

def check_rate_limit(client_ip: str):
    now = datetime.now()
    minute_ago = now - timedelta(minutes=1)
    
    # Clean old requests
    request_counts[client_ip] = [
        req_time for req_time in request_counts[client_ip] 
        if req_time > minute_ago
    ]
    
    # Check rate limit
    max_requests = int(getenv("MAX_REQUESTS_PER_MINUTE", 100))
    if len(request_counts[client_ip]) >= max_requests:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later."
        )
    
    # Add new request
    request_counts[client_ip].append(now)