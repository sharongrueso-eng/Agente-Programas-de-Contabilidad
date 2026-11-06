# Imagen del agente PdC en Coolify.
# ADVERTENCIA: la instalación de Hermes y la ruta del binario no están verificadas en esta
# imagen base. IT debe confirmarlas antes de usarla en producción.

FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Hermes: instalador oficial. Deja el binario en ~/.local/bin según la documentación.
RUN curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash \
    && ln -sf /root/.local/bin/hermes /usr/local/bin/hermes

WORKDIR /app
COPY . /app

ENV PYTHONPATH=/app \
    PDC_STATE_DIR=/data/state \
    HERMES_HOME=/data/hermes \
    PYTHONUNBUFFERED=1

RUN mkdir -p /data/state /data/hermes

# La cadena se ejecuta por tarea programada de Hermes; el contenedor mantiene el gateway.
CMD ["hermes"]
