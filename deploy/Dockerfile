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
# El vigía de precios y sus registros: la corrida de las 05:00 los necesita dentro de la imagen.
COPY vigia ./vigia

# Pillow solo para recomprimir la portada: el gateway entrega ~1,3 MB y la web necesita
# menos de 300 KB. Es la única dependencia externa del proyecto. google-analytics-data es
# para GA4: sin ese paquete la corrida sigue, pero se queda sin las visitas de la página.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir "pillow>=11" "google-api-python-client>=2" "google-auth>=2" \
       "google-analytics-data>=0.18"

# El vigía de precios lee páginas con navegador (varias son SPA y no traen precios en el HTML).
# Chromium entra en la imagen, no se instala por corrida: descargarlo cada mañana añadiría
# minutos y una descarga de red a una tarea que debe ser corta y predecible.
# --with-deps trae las librerías de sistema que Chromium necesita en Debian slim.
# La ruta va en ENV **antes** de instalar, para que el navegador quede donde el contenedor lo
# busca (el usuario pdc no puede leer /root) y con permisos de lectura para ese usuario.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN pip install --no-cache-dir "playwright>=1.40" \
    && python -m playwright install --with-deps chromium \
    && chmod -R a+rx /ms-playwright

# El estado vive fuera de la imagen y se monta como volumen: corridas, mapas de publicación
# y cachés sobreviven al contenedor.
# Los registros de precios se leen del volumen para que el comparador conserve su línea base
# entre despliegues; el código del vigía se queda en la imagen, de solo lectura.
ENV VIGIA_RAIZ=/data/vigia
RUN mkdir -p /data/state /data/sitio /data/gsc /data/vigia \
    && ln -sfn /data/state /app/state \
    && useradd -m -u 10001 pdc \
    && chown -R pdc:pdc /app /data

USER pdc

# El contenedor queda encendido y en espera. Coolify no crea cron dentro de la imagen: entra
# al contenedor y lanza el comando de la tarea programada, así que necesita encontrarlo vivo.
# Si el contenedor terminara al arrancar -como hacía antes-, la tarea no tendría dónde correr.
# La cadena se ejecuta con: docker exec <contenedor> python scripts/corrida_diaria.py
ENTRYPOINT ["sleep", "infinity"]
