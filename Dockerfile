# PenseFinances — Dockerfile otimizado
# Bypassa Railpack/Nixpacks (que estava travando builds)
# Imagem final ~150MB

FROM python:3.11-slim

# Não bufferiza output do Python (logs aparecem em tempo real no Railway)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 1) Copia requirements primeiro (camada cacheada se não mudar)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2) Copia código (camada que muda mais frequentemente)
COPY . .

# Railway define $PORT em runtime
EXPOSE 8080

CMD ["python", "main.py"]
