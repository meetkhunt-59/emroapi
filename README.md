# 🧵 EmroAPI – Image → Embroidery (DST) Converter

EmroAPI is a **FastAPI-based web service** that converts raster/vector images (`.png`, `.jpg`, `.svg`) into embroidery machine-ready **DST files**.  
It automates the entire process:  
**Upload → Background Removal → Vectorization → Embroidery Generation → DST Download**  

---

## 🚀 Features
- Supports **PNG, JPG, SVG** (≤ 20 MB).
- Automatic **background removal** (`rembg`).
- **Vector conversion** (`vtracer`).
- Embeds **thread color metadata** (`inkstitch:thread-color`).
- Converts **SVG → DST** using Ink/Stitch.
- **Async background jobs** with status polling.
- Dockerized for easy deployment.

---

## 📂 Project Structure
```
app/
├── main.py          # FastAPI entrypoint
├── pipeline/
│   ├── preprocess.py   # Background removal + vector conversion
│   └── stitchgen.py    # SVG → DST conversion
├── routes/          # API endpoints
├── utils/
│   ├── job_store.py    # Job tracking
│   ├── validators.py   # Input validation
│   └── errors.py       # Custom exceptions
└── workers/
    └── processor.py    # Background job processing
```

---

## ⚙️ Installation

### 1. Clone repo
```bash
pull from internal repo
cd emroapi
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Run locally
```bash
uvicorn app.main:app --reload --port 9000
```

### 4. Run with Docker
```bash
docker build -t emroapi .
docker run -p 9000:9000 emroapi
```

---

## 🔑 API Endpoints

### 1. **Upload an Image**
```bash
curl -X POST "http://localhost:9000/upload" \
  -F "file=@your_image.png"
```
**Response:**
```json
{
  "job_id": "d8374c0f-4e78-4661-bef6-9c915c17ae33",
  "status": "pending"
}
```

---

### 2. **Check Job Status**
```bash
curl "http://localhost:9000/status/d8374c0f-4e78-4661-bef6-9c915c17ae33"
```
**Response:**
```json
{
  "job_id": "d8374c0f-4e78-4661-bef6-9c915c17ae33",
  "status": "completed"
}
```

---

### 3. **Download Result (DST file)**
```bash
curl -O "http://localhost:9000/download/d8374c0f-4e78-4661-bef6-9c915c17ae33"
```

---

## 🛠️ Configuration
- **Max file size**: 20 MB  
- **Supported formats**: PNG, JPG, SVG  
- **Embroidery settings**: configurable (spacing, density, etc.)  

---

## 🐞 Error Handling
- Invalid file type / size → `400`
- Corrupt SVG → `422`
- Processing failure → `500`

---

## 📦 Dependencies
- **FastAPI** – API framework  
- **Pillow (PIL)** – image handling  
- **rembg** – background removal  
- **vtracer** – raster → vector  
- **Ink/Stitch** – SVG → DST conversion  
- **uvicorn** – ASGI server  

---

## 🛤️ Roadmap
- [ ] Redis job store (instead of in-memory)  
- [ ] Celery / RQ distributed workers  
- [ ] REST + WebSocket for realtime status updates  
- [ ] Advanced embroidery customization (stitch type, density, etc.)  

---



TODO LIST :

PREPROCESS :
    -remove bg in high edgh and inner design not detacting
    -path for desigh is not desiginig for complex design 
    -improve image to svg conversation by any ways like using ml model etc.
    -upload is not giving job id as it generate it gives after the job is completed



COMAND : uvicorn app.main:app --reload

DOCKER : docker build -t emroapi .
         docker run -p 9000:9000 emroapi

         OR

         Docker compose build

CLEAR DOCKER CONTAINERS :
         docker system prune -a -f
         