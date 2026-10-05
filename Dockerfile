FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data FRONTEND_DIR=/app/frontend

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

RUN useradd --system --uid 10001 --no-create-home app \
    && mkdir /data && chown app:app /data
COPY backend/app ./app
COPY frontend ./frontend

USER app
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

# Ein Worker: Rate-Limits und Live-Streams (SSE) leben im Prozess-Speicher.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--no-server-header"]
