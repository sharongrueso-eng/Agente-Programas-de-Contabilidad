#!/usr/bin/env bash
# Respaldo nocturno del estado de las corridas y del perfil de Hermes.
# Programar a las 23:30 dentro del contenedor. No imprime secretos.
set -euo pipefail

STATE_DIR="${PDC_STATE_DIR:-/data/state}"
HERMES_HOME="${HERMES_HOME:-/data/hermes}"
DESTINO="${PDC_BACKUP_DIR:-/data/backups}"
SELLO="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "$DESTINO"

echo "respaldando estado en $DESTINO/pdc-$SELLO.tar.gz"
tar -czf "$DESTINO/pdc-$SELLO.tar.gz" \
    -C "$STATE_DIR" . \
    -C "$HERMES_HOME" .

# Conserva 14 días: el contenido publicado vive en WordPress, esto es para retomar corridas.
find "$DESTINO" -name 'pdc-*.tar.gz' -mtime +14 -delete

echo "respaldo terminado: pdc-$SELLO.tar.gz"
