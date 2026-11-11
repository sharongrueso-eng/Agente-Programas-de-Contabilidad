# Agente PdC — imagen de ejecución diaria en Coolify.
#
# No instala Hermes: la cadena es Python puro y el calendario lo pone Coolify con sus tareas
# programadas. Menos superficie, nada sin verificar dentro de la imagen. Los secretos no
# viven aquí: entran como variables de entorno.

FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=America/Bogota \
    PDC_STATE_DIR=/data/state \
    PYTHONPATH=/app

WORKDIR /app

COPY pyproject.toml README.md SYSTEM.md ./
COPY orchestrator ./orchestrator
COPY skills ./skills
COPY rules ./rules
COPY datos ./datos
COPY scripts ./scripts
COPY mcp-gsc ./mcp-gsc

# Pillow solo para recomprimir la portada: el gateway entrega ~1,3 MB y la web necesita
# menos de 300 KB. Es la única dependencia externa del proyecto.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir "pillow>=11" \
    && pip install --no-cache-dir -e .

# El estado vive fuera de la imagen y se monta como volumen: corridas, mapas de publicación
# y cachés sobreviven al contenedor.
RUN mkdir -p /data/state /data/sitio /data/gsc \
    && ln -sfn /data/state /app/state \
    && useradd -m -u 10001 pdc \
    && chown -R pdc:pdc /app /data

USER pdc

ENTRYPOINT ["python", "scripts/corrida_diaria.py"]
