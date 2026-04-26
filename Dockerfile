# PenseFinances — Dockerfile otimizado
# Bypassa Railpack/Nixpacks (que estava travando builds)
# Build determinístico em ~90s, imagem final ~200MB

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8080

WORKDIR /app

# Pacotes do sistema necessários para compilar wheels caso falte
# (Pillow, cryptography, etc. — geralmente usam wheels pré-compilados,
#  mas estes pacotes garantem fallback de compilação)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
        libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Atualiza pip primeiro (versão antiga em images antigas pode falhar)
RUN pip install --upgrade pip

# 1) Copia só requirements pra cache de layer
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2) Copia código (essa layer muda em todo deploy, mas é rápida)
COPY . .

EXPOSE 8080

CMD ["python", "main.py"]
