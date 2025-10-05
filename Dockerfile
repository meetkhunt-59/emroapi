# ==========================
# 1. Base image
# ==========================
FROM python:3.10-slim

# Prevent Python from writing pyc files & enable unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# ==========================
# 2. Install system dependencies
# ==========================
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl unzip xz-utils ca-certificates build-essential \
    xvfb xauth inkscape \
    libglib2.0-0 libsm6 libxrender1 libxext6 libcairo2 \
    libgtk-3-0 libatk1.0-0 libgdk-pixbuf-xlib-2.0-0 libpango-1.0-0 libwayland-server0 \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*


# ==========================
# 3. Install Ink/Stitch
# ==========================
WORKDIR /tmp
RUN wget https://github.com/inkstitch/inkstitch/releases/latest/download/inkstitch-3.2.2-linux-x86_64.sh \
    && chmod +x inkstitch-3.2.2-linux-x86_64.sh \
    && ./inkstitch-3.2.2-linux-x86_64.sh --prefix=/usr/local --skip-license \
    && rm inkstitch-3.2.2-linux-x86_64.sh



# ==========================
# 4. Set workdir and copy app
# ==========================
WORKDIR /app
COPY requirements.txt .

# ==========================
# 5. Install Python requirements
# ==========================
# Allow pip installs inside this environment (PEP 668 workaround)
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

# ==========================
# 6. Copy the rest of the app
# ==========================
COPY . .

# ==========================
# 7. Expose port and run app
# ==========================
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000", "--reload", "--proxy-headers", "--log-level", "error", "--access-log"]
