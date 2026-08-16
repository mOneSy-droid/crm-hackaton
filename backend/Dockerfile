FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Avval faqat requirements — kod o'zgarganda qatlam qayta ishlatiladi
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts

# Rasm yuklamalari uchun. Railway'da shu yo'lga volume ulang,
# aks holda har deployda rasmlar yo'qoladi.
ENV MEDIA_ROOT=/app/media
RUN mkdir -p /app/media

EXPOSE 8000

# Railway $PORT ni o'zi beradi
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
