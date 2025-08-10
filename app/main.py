from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
import uuid, os
from app.pipeline.stitchgen import run as make_pattern
from pyembroidery import write_dst

app = FastAPI()
UPLOAD = "storage/uploads"; OUTPUT = "storage/outputs"
os.makedirs(UPLOAD, exist_ok=True); os.makedirs(OUTPUT, exist_ok=True)

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    uid = str(uuid.uuid4())
    in_path = os.path.join(UPLOAD, f"{uid}_{file.filename}")
    # out_dst = os.path.join(OUTPUT, f"{uid}.dst")
    with open(in_path, "wb") as f: f.write(await file.read())

    # Generate EmbPattern with filled stitches
    make_pattern(in_path, uid)
    
    return {"job_id": uid, "download": f"/download/{uid}"}

@app.get("/download/{uid}")
def download(uid: str):
    file = os.path.join(OUTPUT, f"{uid}.dst")
    if not os.path.exists(file): return {"error": "not found"}
    return FileResponse(file, media_type="application/octet-stream", filename=f"{uid}.dst")
