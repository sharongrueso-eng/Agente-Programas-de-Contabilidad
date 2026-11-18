# programascontabilidad-studio

Repositorio inicial para el agente editorial de programascontabilidad.com.

## Estado

**En producción desde el 13-nov-2026, en modo gobernado.** Las piezas nuevas nacen con los
controles deterministas y la línea visual; el agente escribe en WordPress por el MCP. El estado
y los pendientes viven en `contexto/estado-2026-11-13.md` y `contexto/pendientes.md`.

**Cómo funciona de punta a punta** — etapas, módulos, skills, datos y estado:
`contexto/flujo-operacion.md`.

## Ejecutar

Desde la raíz del repositorio:

```bash
# Pruebas (562 en verde). El `-t tests` es obligatorio: sin él, unittest no importa el paquete.
python -m unittest discover -s tests -t tests -p "test_*.py"

# Controles deterministas sobre un post vivo, sin gastar tokens
python scripts/diagnosticar_post.py --respaldo state/respaldos/post-5309-....json

# Respaldo antes de tocar nada: archivo local con contenido y SEO (el duplicado en WordPress es opcional)
python scripts/respaldar_post.py --post 5309 --entorno prod

# Firma del autor en todo el archivo publicado
python scripts/firmar_posts.py --todos --aplicar
```

```bash
# Guardas de ejecución
python -m orchestrator.cli run --dry-run

# Plan del día a partir de una instantánea de Search Console
python -m orchestrator.cli plan --date 2026-11-06 --data datos/muestra/gsc-2026-11-05.json

# Prompt exacto que verá el productor, sin llamar al modelo
python -m orchestrator.cli produce --brief datos/muestra/brief-2026-11-06-A.json --dry-run

# Controles deterministas sobre un borrador
python -m orchestrator.cli validate --brief datos/muestra/brief-2026-11-06-A.json --draft datos/muestra/borrador-2026-11-06-A.json

# Prompt del juez, con el veredicto del validador y el registro de datos
python -m orchestrator.cli judge --brief datos/muestra/brief-2026-11-06-A.json --draft datos/muestra/borrador-2026-11-06-A.json --registro datos/muestra/registro-siigo-co.md --dry-run
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
| `orchestrator/cli.py` | Listo | `run` (guardas), `plan` (briefs y consolidaciones) y `produce` (prompt en seco) |
| `orchestrator/producer.py` | Listo | Arma el prompt, valida la salida del modelo y crea el borrador |
| `orchestrator/brief_io.py` | Listo | Lee el brief de la carpeta de la corrida |
| `orchestrator/adapters.py` | Escrito, sin probar contra las APIs | Clientes HTTP de LiteLLM y WordPress, con transporte inyectable |
| `orchestrator/validator.py` | Listo | Veinte controles deterministas sobre el borrador |
| `orchestrator/formato.py` | Listo | Presupuesto de tablas por formato y elenco que fija el título; alimenta dos controles bloqueantes |
| `orchestrator/linea_visual.py` | Listo | Componentes de la línea visual: cajas, tablas, FAQ, firma, listas con sangría y dos columnas |
| `orchestrator/judge.py` | Listo | Juez de otro modelo: intención/profundidad y QA final, con sugerencias aparte |
| `orchestrator/corrector.py` | Listo | Arreglos acotados con guarda automática de enlaces, cifras, marcas y largo |
| `orchestrator/publisher.py` | Listo | Compuertas, huella, publicación idempotente, relectura y reversión |
| `orchestrator/runner.py` | Listo | Encadena la corrida, escribe la carpeta de estado y retoma desde el punto de fallo |
| `orchestrator/watchers.py` | Listo | Cadencia de vigías, diff de precios todo-o-nada y caídas de GSC |
| `orchestrator/notices.py` | Listo | Plantillas fijas de aviso y envío al webhook de Chat |
| `orchestrator/gsc_api.py` | Escrito, sin probar contra la API | Ventanas de 28 días, consulta y armado de la instantánea |
| `orchestrator/gsc_mcp.py` | Listo, probado contra GSC el 17-nov | Instantánea del país: consultas, totales por URL, ventana previa y 16 meses, con filtro de país |
| `orchestrator/diagnostico.py` | Listo | Ranking del día, intención ambigua por modelo con memoria, solapamientos y calendario quincenal |
| `orchestrator/ahrefs.py` | Escrito, sin probar contra la API | Volumen, SERP y citas en IA como evidencia; no cambia ninguna decisión |
| `orchestrator/preparacion.py` | Listo | Prompt de portada por país, reintentos y respaldo |
| `orchestrator/registry.py` | Listo | Fichas por marca y país; bloquea cifras fuera del registro |
| `deploy/` | Escrito, sin probar en Coolify | Dockerfile, compose, variables, respaldo y tareas |

La cifra fuera de registro es el control más fuerte contra datos inventados: si el
borrador menciona un importe con moneda que no está en las fichas del mercado, la pieza
se bloquea antes de llegar al juez.

### Prueba de punta a punta

`python scripts/smoke_pipeline.py` recorre la cadena completa sin salir a internet: usa el
borrador de muestra como si lo hubiera escrito el modelo y un veredicto PASS como si lo
hubiera dado el juez. Prueba la plomería, no el criterio editorial.

```
production   DONE
validation   PASS
judge        PASS
publication  DONE

carpeta de la corrida: borrador.json · veredictos.json · publicacion.json · checkpoint.json
checkpoint: {'last_step': 'publication', 'resume_from': ''}
```

Si un paso falla, el checkpoint guarda `resume_from` y la siguiente corrida arranca ahí sin
repetir lo anterior. La carpeta vive fuera del repositorio, en el volumen persistente.

### Compuertas del publicador

Publica solo si pasan las cinco. Cualquier fallo deja la pieza sin tocar el sitio.

| Compuerta | Motivo del bloqueo |
|---|---|
| Pausa global | `pausa global activa` |
| Chequeo del día | `el chequeo del día no pasó` |
| Tope diario | `tope diario alcanzado (2/2)` |
| Ventana horaria | `fuera de la ventana de publicación (06:00–17:30)` |
| Huella del contenido | `la huella del contenido no coincide con la aprobada` |

Después de escribir, relee la URL pública y compara título, H1, meta, robots e imagen
destacada. Si algo no coincide, revierte —a borrador si la pieza era nueva, al contenido
anterior si era un reencauche— y reporta el motivo.

### Controles deterministas

`validate` corre antes del juez y no publica nada por sí solo. Devuelve un estado por
control y el peor de ellos como veredicto.

| Control | Severidad | Qué verifica |
|---|---|---|
| `slug_keyword` | BLOQUEADO | Todas las palabras de la keyword foco están en el slug |
| `presupuesto_tablas` | BLOQUEADO | El formato admite un máximo de tablas (comparativa 3, guía 2, lista 4) |
| `marcas_del_formato` | BLOQUEADO | El título cierra el elenco y el cuerpo nombra otra marca del mercado |
| `slug_year` | CORREGIR | Una URL nueva no lleva año en el slug |
| `title_keyword` | CORREGIR | Keyword foco completa en el título SEO |
| `meta_keyword` / `meta_length` | CORREGIR | Keyword en la meta y entre 100 y 165 caracteres |
| `h1_keyword` | CORREGIR | Keyword foco en el H1 |
| `intro_keyword` | CORREGIR | Keyword foco en el primer párrafo |
| `alegra_links` | CORREGIR | Tres enlaces a Alegra con UTM completa |
| `internal_links` | CORREGIR | Cinco enlaces internos |
| `sources` | CORREGIR | Dos fuentes externas (los enlaces a Alegra no cuentan) |
| `country_norms` | BLOQUEADO | Ninguna autoridad de otro mercado; en RD, nunca la sigla «RD» |
| `testing_claims` | CORREGIR | «Probé» sin evidencia registrada |
| `internal_jargon` | CORREGIR | GSC, run_id, compuerta y demás jerga visible |
| `snippet_body` | BLOQUEADO | Un reencauche de snippet no reescribe el cuerpo |

La UTM «completa» se comprueba con `utm_source`, `utm_medium` y `utm_campaign`; si el
equipo usa otra convención, se cambia en un solo lugar (`validator._has_full_utm`).

### Cómo decide la auditoría

Solo las reglas deterministas viven en código; el criterio editorial queda para el juez.

Los datos salen de Search Console con el filtro del país de la corrida (búsquedas hechas desde
ese país) y en cuatro consultas: página × consulta de los últimos 28 días (las 25 principales de
cada URL), totales por URL de esos 28 días (la suma de consultas se queda corta por las
anónimas), totales de los 28 días anteriores (para la regla de caída) y totales de 16 meses
(promedio por cada 28 días, en el diagnóstico). Si la intención de la consulta principal queda
ambigua con las reglas, la decide un modelo (`PDC_MODEL_INTENCION`) y la respuesta se guarda en
`$PDC_STATE_DIR/intenciones.json`, que arranca con `datos/referencia/intenciones-semilla.json`.
Con `AHREFS_API_KEY`, las primeras oportunidades del ranking llevan volumen, SERP y citas en IA
como evidencia; GSC decide.

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

## Bloqueos antes de activar la corrida programada

- Scheduler decidido por el equipo: tareas de Hermes dentro de la instancia alojada en Coolify;
  Coolify es el entorno de despliegue, no el scheduler autoritativo.
- **Estado al 13-nov-2026: el scheduler no está creado.** En la instancia de Hermes no hay
  ninguna tarea programada; las de `deploy/cron.md` siguen siendo comandos por ejecutar.

Lo que falta, en orden:

1. **Redesplegar la imagen** para que la corrida programada lleve los controles del 13-nov
   (`formato.py`, la excepción de Alegra, la firma, los componentes de lista y columnas). Una
   tarea creada hoy sobre una imagen vieja publicaría con las reglas anteriores.
2. **Crear las tareas** de `deploy/cron.md` en el contenedor y comprobar las variables de
   entorno en modo `script`.
3. **Una corrida manual en modo borrador** desde Coolify, leyendo el registro y el aviso de
   Google Chat, antes de pasar `PDC_MODO=publicar`.
4. Cerrar los pendientes de contenido de `contexto/pendientes.md` —el 5309 en borrador, sus seis
   tablas, el post 154 que no se puede escribir por tamaño—.

La autonomía de publicación descrita en v2 es una decisión del diseño; la corrida programada
sigue en modo borrador hasta que los cuatro pasos anteriores estén hechos.
