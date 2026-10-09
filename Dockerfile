# Pinned base (patch + Debian release) so rebuilds are reproducible; bump deliberately.
FROM python:3.14.8-slim-trixie
LABEL org.opencontainers.image.title="Diet Pro Planner"
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DPP_UID=10001 \
    DPP_GID=10001
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-spa \
    tesseract-ocr-eng \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 10001 dpp \
 && useradd --system --uid 10001 --gid dpp --home-dir /nonexistent --no-create-home --shell /usr/sbin/nologin dpp
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Code is owned by root and read-only for the app user; only /app/data is writable.
# .dockerignore keeps .env, data/, .git and local caches out of the image.
COPY . .
EXPOSE 8099
HEALTHCHECK --interval=60s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8099/health', timeout=4).status == 200 else 1)"
# Starts as root only to chown existing root-owned files in /app/data, then drops to uid 10001.
ENTRYPOINT ["python", "/app/scripts/docker_entrypoint.py"]
CMD ["python", "dpp_entrypoint.py"]
