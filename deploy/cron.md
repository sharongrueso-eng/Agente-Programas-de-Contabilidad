# Tareas programadas

Zona horaria: `America/Bogota`.

**Quién programa: Coolify, no Hermes.** La imagen (`deploy/Dockerfile`) no instala Hermes: es
Python puro y deja el contenedor encendido con `sleep infinity` para que la tarea tenga dónde
ejecutarse. Por eso las corridas se crean como **Scheduled Tasks de Coolify**, que entran al
contenedor y lanzan el comando. Las tareas de `hermes cron` solo aplican si en algún momento se
instala Hermes dentro de la imagen.

## El día hábil

> Cada pieza avisa al espacio de Chat **en el momento en que queda publicada**, no al cierre.
> La tarea de las 17:30 es solo el resumen del día.

| Tarea | Comando | Cron | Qué hace |
|---|---|---|---|
| `pdc-slot-a` | `python scripts/corrida_diaria.py` | `10 6 * * *` | Produce, valida, juzga, corrige y publica el artículo del día |
| `pdc-reporte` | `python scripts/corrida_diaria.py --resumen` | `30 17 * * *` | **No existe todavía**: `--resumen` no está implementado. No crear la tarea hasta que lo esté. |

El wrapper `corrida_diaria.py` comprueba la ventana, la pausa y el mercado del día antes de
trabajar: una ejecución a deshora no hace nada y lo deja escrito en el registro.

**Cadencia diaria:** el cron es de domingo a domingo, así que hay que abrir el fin de semana con
`PDC_FIN_DE_SEMANA=1`; sin esa variable el wrapper se niega a trabajar sábado y domingo y lo
deja dicho en el registro. El mercado rota entre los cuatro del portal (`PDC_PAISES`); un código
que no sea CO, MX, CR o DO se ignora con aviso, porque no hay directorio ni registro de datos
contra el que verificar la pieza.

## Vigías y respaldo

Las tres tareas existen en Coolify (verificado por API el 22-nov-2026):

| Tarea | Comando | Cron (UTC) | Hora Bogotá | Estado |
|---|---|---|---|---|
| `vigias-precios` | `python scripts/corrida_diaria.py --vigias` | `0 10 * * *` | 05:00 | activa |
| `corrida-diaria` | `python scripts/corrida_diaria.py` | `10 11 * * 1-5` | 06:10 L-V | activa |
| `respaldo-estado` | `bash deploy/backup.sh` | `30 4 * * *` | 23:30 | activa |

Los vigías corren **antes** del redactor a propósito: a las 06:10 la corrida editorial ya
encuentra las fichas de precios al día. `VIGIA_MODO` vale `ensayo` por defecto, así que la
primera corrida lee y avisa pero no cambia precios; se pasa a `aplicar` cuando se revise.

### Comprobar el despliegue, no suponerlo

Un build fallido deja el contenedor con la imagen anterior y **la tarea sigue «funcionando»**:
ejecuta código viejo sin protestar. Antes de encender una tarea nueva, verificarlo dentro del
contenedor con una tarea desechable (`enabled:false`) que solo importe y liste:

```bash
python -c "import vigia, playwright; print(vigia.__file__); print(__import__('os').listdir('/ms-playwright'))"
```

Se ejecuta con `POST /api/v1/applications/<app>/scheduled-tasks/<tarea>/execute`, se lee la salida
en `.../executions` y se borra la tarea. Si dice `No module named 'vigia'`, el despliegue no entró.

## Si algún día se instala Hermes en la imagen

```bash
hermes cron add "pdc-slot-a" --cron "10 6 * * 1-5" --prompt "Produce, valida, juzga, corrige y publica el slot A siguiendo el runner."
```

## Lo que falta confirmar con IT

- Que la tarea programada de Coolify herede las variables de entorno de la aplicación. Si el
  programador las filtra, el módulo lee los secretos de un archivo del perfil con
  `load_dotenv`, y eso hay que probarlo antes de la primera corrida real.
- Que dos tareas no arranquen a la vez sobre el mismo estado: el runner tiene candado y la
  segunda falla con `LockHeld`, que es el comportamiento buscado.
