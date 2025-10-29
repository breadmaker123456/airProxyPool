# syntax=docker/dockerfile:1

FROM python:3.11-slim

ARG GLIDER_VERSION=0.16.4
ARG GLIDER_ARCH=linux_amd64

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl; \
    GLIDER_DIR="glider_${GLIDER_VERSION}_${GLIDER_ARCH}"; \
    GLIDER_TARBALL="${GLIDER_DIR}.tar.gz"; \
    mkdir -p /app/glider; \
    curl -fsSL "https://github.com/nadoo/glider/releases/download/v${GLIDER_VERSION}/${GLIDER_TARBALL}" -o /tmp/glider.tar.gz; \
    tar -xzf /tmp/glider.tar.gz -C /app/glider --strip-components=1 "${GLIDER_DIR}/glider"; \
    chmod +x /app/glider/glider; \
    rm -rf /tmp/glider.tar.gz; \
    rm -rf /var/lib/apt/lists/*

ENV APP_DATA_DIR=/data
VOLUME ["/data"]

EXPOSE 8000

CMD ["uvicorn", "proxychain.main:app", "--host", "0.0.0.0", "--port", "8000"]
