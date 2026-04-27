# PenseFinances — Dockerfile otimizado
# Bypassa Railpack/Nixpacks (que travavam em builds longos)
# Build determinístico em ~90s, imagem final ~200MB

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8080

WORKDIR /app

# Pacotes do sistema para fallback de compilação (Pillow, cryptography)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
        libssl-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

# 1) Requirements primeiro (cache de layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2) Código (muda em cada deploy, mas é rápido)
COPY . .

EXPOSE 8080

CMD ["python", "main.py"]
