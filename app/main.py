from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import logging
import os
from app.routes import upload, status, download
from app.utils.errors import handle_embroidery_error, EmbroError
from prometheus_fastapi_instrumentator import Instrumentator
from os import getenv
from dotenv import load_dotenv

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

# ✅ initialize Prometheus metrics BEFORE startup
Instrumentator().instrument(app).expose(app)
 
# Add CORS middleware


load_dotenv()

allowed_origins = getenv("ALLOWED_ORIGINS", "").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# Include routers
app.include_router(upload.router)
app.include_router(status.router)
app.include_router(download.router)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# UI Routes
@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/progress/{job_id}")
async def progress(request: Request, job_id: str):
    return templates.TemplateResponse("progress.html", {"request": request, "job_id": job_id})

# Create required directories
for dir_path in ["storage/uploads", "storage/outputs"]:
    os.makedirs(dir_path, exist_ok=True)
