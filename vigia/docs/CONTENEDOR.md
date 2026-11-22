# Instalar el vigía en el contenedor (Coolify)

Chromium y las dependencias se instalan **una vez** con la imagen, no en cada corrida del vigía
(DEC-010). Reinstalarlo en cada corrida suma minutos a la tarea programada y la deja a merced de la red
del momento.

## 1. Dependencias de Python

```bash
cd <REPO>
pip install -r vigia/requirements.txt
```

Van al mismo intérprete que ejecuta `python -m vigia.correr`. Si el contenedor se recrea desde la imagen,
esto se repite en el arranque o se agrega a la imagen.

## 2. Chromium, en una carpeta permanente

```bash
# 1) la carpeta vive fuera de la imagen y sobrevive a los reinicios
export PLAYWRIGHT_BROWSERS_PATH="$HERMES_HOME/ms-playwright"

# 2) el binario, una sola vez
python -m playwright install chromium

# 3) librerías del sistema (necesita root; se pierden si la imagen se recrea)
python -m playwright install-deps chromium
```

En Coolify:

1. Servicio de Hermes → **Environment Variables** → agregar `PLAYWRIGHT_BROWSERS_PATH` con el valor de
   arriba. Sin esa variable, Playwright buscará el navegador en la carpeta del usuario y lo volverá a
   bajar en el siguiente reinicio.
2. Servicio de Hermes → **Post-deployment Command** (o el `RUN` del Dockerfile, que es lo preferible):

```bash
PLAYWRIGHT_BROWSERS_PATH=/opt/data/ms-playwright python -m playwright install --with-deps chromium
```

`--with-deps` junta el paso 3 en un solo comando y es el que hay que poner en la imagen: las librerías
del sistema (libnss3, libatk, fuentes) no sobreviven a una recreación del contenedor si se instalaron a
mano.

## 3. Comprobar que quedó

```bash
python -c "from playwright.sync_api import sync_playwright as s; \
b=s().start().chromium.launch(); print('chromium', b.version); b.close()"
```

Debe imprimir la versión sin errores. Después, la tarea T1 de `docs/PLAN.md` confirma lo demás.

Para saber si de verdad es permanente: apunta la fecha de la carpeta
(`ls -la "$PLAYWRIGHT_BROWSERS_PATH"`), reinicia el servicio y vuelve a mirar. Si no cambió y el
navegador sigue abriendo, quedó en la imagen o en la carpeta permanente; si se volvió a descargar, se
está instalando por corrida.

## 4. Si IT no puede instalar Chromium

El vigía no se detiene: la corrida programada pasa a GitHub Actions (paso 9 de `docs/GUIA.md`) y Hermes
sigue haciendo las tareas del plan. Lo que no se puede es correr el lector (T4) sin navegador.

## 5. Tareas programadas

Después de T8, una tarea por vigía en Coolify → Scheduled Tasks, separadas 15 minutos (servidor en UTC):

| Nombre | Frecuencia | Comando |
|---|---|---|
| vigia-col | `0 12 1,16 * *` | `cd <REPO> && git pull --ff-only && python -m vigia.correr --pais col` |
| vigia-mex | `15 12 1,16 * *` | `cd <REPO> && git pull --ff-only && python -m vigia.correr --pais mex` |
| vigia-cri | `30 12 1,16 * *` | `cd <REPO> && git pull --ff-only && python -m vigia.correr --pais cri` |
| vigia-dom | `45 12 1,16 * *` | `cd <REPO> && git pull --ff-only && python -m vigia.correr --pais dom` |

Van en el contenedor de Hermes para que vean las variables del entorno y el navegador. Nunca en el
programador de Hermes: allí no ve las llaves ni el repositorio actualizado.
