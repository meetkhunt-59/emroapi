from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
from app.routes import upload, status, download
from app.utils.errors import handle_embroidery_error, EmbroError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="EmroAPI",
    description="Embroidery conversion API for generating DST files from images",
    version="1.0.0",
    root_path="/proxy/9000",
    docs_url="/docs",
    openapi_url="/openapi.json"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(upload.router)
app.include_router(status.router)
app.include_router(download.router)

# Create required directories
for dir_path in ["storage/uploads", "storage/outputs"]:
    os.makedirs(dir_path, exist_ok=True)
