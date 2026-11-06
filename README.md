# programascontabilidad-studio

Repositorio inicial para el agente editorial de programascontabilidad.com.

## Estado

**Scaffold local, exclusivamente dry-run.** No consulta Google Search Console, Ahrefs, WordPress, LiteLLM ni Google Chat; no genera ni publica contenido. La configuración parte pausada y cualquier ejecución sin `--dry-run` se bloquea.

## Ejecutar

Desde la raíz del repositorio:

```bash
python -m orchestrator.cli run --dry-run
python -m unittest discover -s tests -v
```

El comando emite JSON con `side_effects: false`. El modo de producción queda deshabilitado hasta implementar y probar los conectores, persistencia, controles editoriales/técnicos, publicación idempotente y reversión.

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
