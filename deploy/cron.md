# Tareas programadas de Hermes

Zona horaria: `America/Bogota`. Se crean dentro del contenedor y viven en el volumen de
Hermes, no en el repositorio.

## El día hábil

```bash
hermes cron add "pdc-chequeo"   --cron "40 5 * * 1-5" --prompt "Corre el chequeo del día: conectores, frescura de Search Console y salud de WordPress. Si algo falla, avisa con la plantilla chequeo_fallido y detén la producción de hoy."
hermes cron add "pdc-auditoria" --cron "45 5 * * 1-5" --prompt "Descarga la instantánea de Search Console de los cuatro mercados, calcula las oportunidades del día y deja el diagnóstico en la carpeta de la corrida."
hermes cron add "pdc-plan-a"    --cron "0 6 * * 1-5"  --prompt "Arma el brief del slot A con la rotación de hoy, la mejor oportunidad compatible y el registro de datos."
hermes cron add "pdc-plan-b"    --cron "0 7 * * 1-5"  --prompt "Arma el brief del slot B con la rotación de hoy, la mejor oportunidad compatible y el registro de datos."
hermes cron add "pdc-slot-a"    --cron "10 6 * * 1-5" --prompt "Produce, valida, juzga, corrige y publica el slot A siguiendo el runner."
hermes cron add "pdc-slot-b"    --cron "10 7 * * 1-5" --prompt "Produce, valida, juzga, corrige y publica el slot B siguiendo el runner."
hermes cron add "pdc-reporte"   --cron "30 17 * * 1-5" --prompt "Envía el reporte del día al espacio de Chat con las plantillas fijas."
```

## Vigías

```bash
hermes cron add "pdc-vigias" --cron "0 5 * * *" --prompt "Corre los vigías que toquen según watchers_due: precios los días 1 y 16, funciones lunes y viernes, regulación y caídas todos los días. Avisa solo si hay cambios."
```

## Respaldo

```bash
hermes cron add "pdc-respaldo" --cron "30 23 * * *" --script "deploy/backup.sh" --no-agent
```

## Lo que falta confirmar con IT

- Que una tarea en modo `script` reciba las variables de entorno del contenedor. Si el
  programador las filtra, el módulo lee los secretos de un archivo del perfil con
  `load_dotenv`, y eso hay que probarlo antes de la primera corrida real.
- Que dos tareas no arranquen a la vez sobre el mismo estado: el runner tiene candado y la
  segunda falla con `LockHeld`, que es el comportamiento buscado.
