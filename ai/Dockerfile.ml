# Varian "berat": image yang sama + stack inference CPU (torch/transformers).
# Dipakai mulai build step 4 (Qwen2-VL). Aktifkan lewat AI_DOCKERFILE=Dockerfile.ml.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    OMP_NUM_THREADS=4 \
    MKL_NUM_THREADS=4 \
    HF_HOME=/srv/ai/.cache/huggingface \
    TRANSFORMERS_OFFLINE=0 \
    CUDA_VISIBLE_DEVICES=""

WORKDIR /srv/ai

COPY requirements.txt requirements-ml.txt ./
# CPU wheel index is declared inside requirements-ml.txt.
RUN pip install --no-cache-dir -r requirements-ml.txt \
    && python -c "import torch; assert not torch.cuda.is_available(); assert '+cpu' in torch.__version__, torch.__version__"

# Dependensi sistem untuk cv2, yang ditarik ultralytics. Tanpa ini:
# ImportError libxcb.so.1 — dan karena vision jatuh ke mock secara diam-diam,
# kegagalannya tidak terlihat sampai seseorang memeriksa /vision/engine.
#
# Sengaja ditaruh SESUDAH pip install, berbeda dari Dockerfile.dev: menaruhnya
# di atas akan membatalkan cache layer torch, dan memasang ulang torch menuntut
# memori yang tidak selalu tersedia.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libxcb1 \
        libsm6 \
        libxext6 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/* \
    && python -c "import ultralytics; print('ultralytics siap:', ultralytics.__version__)"

COPY app ./app
# Bobot YOLO Modul 2 — di image inilah deteksi asli benar-benar berjalan.
COPY models ./models

RUN useradd --create-home --uid 1000 aiuser \
    && mkdir -p "$HF_HOME" \
    && chown -R aiuser:aiuser /srv/ai
USER aiuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=120s --retries=10 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
