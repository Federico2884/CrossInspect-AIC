FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    OMP_NUM_THREADS=4 \
    MKL_NUM_THREADS=4

WORKDIR /srv/ai

# Dependensi di-install sebelum COPY app/ supaya layer cache tidak invalid
# setiap kali kode diedit.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
# Bobot Modul 2 (~6 MB). Image slim tidak punya torch, jadi vision di sini
# berjalan sebagai mock — bobotnya tetap disertakan supaya pindah ke
# Dockerfile.ml tidak perlu menyiapkan apa pun lagi.
COPY models ./models

RUN useradd --create-home --uid 1000 aiuser \
    && chown -R aiuser:aiuser /srv/ai
USER aiuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
