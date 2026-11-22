#!/usr/bin/env bash
# Respaldo nocturno del estado de las corridas y del perfil de Hermes.
# Programar a las 23:30 dentro del contenedor. No imprime secretos.
set -euo pipefail

STATE_DIR="${PDC_STATE_DIR:-/data/state}"
HERMES_HOME="${HERMES_HOME:-/data/hermes}"
DESTINO="${PDC_BACKUP_DIR:-/data/backups}"
SELLO="$(date -u +%Y%m%dT%H%M%SZ)"

# Conserva 14 días: el contenido publicado vive en WordPress, esto es para retomar corridas.
# Solo se respalda lo que existe: la imagen del agente no instala Hermes, así que /data/hermes
# puede no estar, y un `tar` con un directorio inexistente haría fallar el respaldo entero.
FINDES=()
if [ -d "$STATE_DIR" ]; then FINDES+=(-C "$STATE_DIR" .); fi
if [ -d "$HERMES_HOME" ]; then FINDES+=(-C "$HERMES_HOME" .); fi
if [ ${#FINDES[@]} -eq 0 ]; then
    echo "respaldo sin origen: no existe ni $STATE_DIR ni $HERMES_HOME"
    exit 0
fi

echo "respaldando estado en $DESTINO/pdc-$SELLO.tar.gz"
mkdir -p "$DESTINO"
tar -czf "$DESTINO/pdc-$SELLO.tar.gz" "${FINDES[@]}"

find "$DESTINO" -name 'pdc-*.tar.gz' -mtime +14 -delete

echo "respaldo terminado: pdc-$SELLO.tar.gz"
