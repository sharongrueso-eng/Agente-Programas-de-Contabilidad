# programascontabilidad-studio

Repositorio inicial para el agente editorial de programascontabilidad.com.

## Estado

**Scaffold local, exclusivamente dry-run.** No consulta Google Search Console, Ahrefs, WordPress, LiteLLM ni Google Chat; no genera ni publica contenido. La configuración parte pausada y cualquier ejecución sin `--dry-run` se bloquea.

## Ejecutar

Desde la raíz del repositorio:

```bash
# Pruebas
python -m unittest discover -s tests -v

# Guardas de ejecución
python -m orchestrator.cli run --dry-run

# Plan del día a partir de una instantánea de Search Console
python -m orchestrator.cli plan --date 2026-11-06 --data datos/muestra/gsc-2026-11-05.json
```

El comando emite JSON con `side_effects: false`. El modo de producción queda deshabilitado hasta implementar y probar los conectores, persistencia, controles editoriales/técnicos, publicación idempotente y reversión.

## Módulos

| Módulo | Estado | Qué hace |
|---|---|---|
| `orchestrator/rotation.py` | Listo | Rotación formato/país por fecha; 6 días hábiles cubren las 12 combinaciones |
| `orchestrator/audit.py` | Listo | Convierte métricas de GSC en oportunidades: declive, snippet, estructura |
| `orchestrator/assigner.py` | Listo | Asigna la mejor oportunidad compatible con cada slot y registra desvíos |
| `orchestrator/gsc_io.py` | Listo | Lee instantáneas de GSC y aplica la regla de frescura (máximo 7 días) |
| `orchestrator/cannibalization.py` | Listo | Detecta URLs que compiten por las mismas consultas y propone dueña y 301 |
| `orchestrator/state.py` | Listo | Diario de reencauches: una URL no se reencauza dos veces en 30 días |
| `orchestrator/cli.py` | Listo | `run` (guardas) y `plan` (briefs, consolidaciones y bloqueos del día) |
| Conector GSC en vivo | Pendiente | Requiere cuenta de servicio de IT |
| Productor, juez, corrector, publicador | Pendiente | Requieren LiteLLM y token de WordPress |

### Cómo decide la auditoría

Solo las reglas deterministas viven en código; el criterio editorial queda para el juez.

1. **Umbral de señal** — menos impresiones que el mínimo del país (100 en CO/MX, 30 en DO/CR): no hay oportunidad.
2. **Declive** — clics a 70 % o menos de los 28 días previos (con al menos 20 clics antes), o posición que empeora 3 o más puestos.
3. **Estructura** — la intención dominante pide un formato distinto al publicado (por ejemplo, la gente compara y la pieza es una reseña).
4. **Snippet** — posición entre 4 y 20 con CTR por debajo del 70 % del esperado para esa posición.

El puntaje se expresa en clics: los que la página deja de ganar o los que ya perdió.

### Canibalización y reencauches

Dos URLs del mismo país se consideran competidoras cuando comparten al menos dos consultas y su solapamiento (Jaccard sobre el conjunto de consultas) llega a 0,3. El agente nombra la dueña y deja las 301 sugeridas en el reporte; **no aplica redirecciones**.

La dueña se elige por clics, después por impresiones y después por URL. Es un criterio provisional: la arquitectura pide validar también backlinks, enlaces internos y canonical antes de consolidar, y esos datos todavía no están conectados.

El diario de reencauches (`state/refreshes.json`) impide trabajar la misma URL dos veces en 30 días. Vive fuera del repositorio clonado, se escribe de forma atómica y falla cerrado: si el archivo está corrupto, el plan se bloquea en lugar de asumir que la URL está libre.


## Diseño tomado como base

- `PdC_Arquitectura_agente_Hermes_v2.docx` (5 nov 2026): cuatro mercados (CO, MX, DO, CR), formatos en rotación, dos slots diarios, priorización diaria desde GSC/Ahrefs, estado persistente fuera del checkout, reintentos y publicación autónoma con fail-closed.
- `Documentación de programas de contabilidad.docx`: rol de marca blanca, Share of Voice, audiencia, territorio editorial y reglas del activo.
- `Skills de claude de PDC.docx`: inventario y dependencias de skills; no incluye los archivos fuente completos de las skills.

Los documentos originales se mantienen fuera del repositorio. La skill `leandro` y sus referencias completas deben importarse desde la fuente vigente antes de habilitar redacción.

## Bloqueos antes de producción

- Scheduler confirmado por el equipo: tareas de Hermes dentro de la instancia alojada en Coolify; Coolify es el entorno de despliegue, no el scheduler autoritativo.
1. Obtener la skill Leandro vigente y referencias de país/competidores desde Claude/Drive/Wiki, verificando versiones.
2. Provisionar y probar credenciales de servicio por IT; los secretos solo van en Coolify, nunca en Git.
3. Implementar lecturas de GSC/Ahrefs, estado persistente, idempotencia, juez de otra familia, validadores y publicador con readback/reversión.
4. Completar pruebas end-to-end en dry-run y revisar discrepancias editoriales/técnicas antes de activar publicación.

La autonomía de publicación descrita en v2 es una decisión del diseño, pero este scaffold no la activa.
