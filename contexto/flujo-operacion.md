# Flujo de operación del agente PdC

Documento de referencia: cómo funciona el agente de punta a punta, qué skills usa, con qué
datos trabaja y qué queda por documentar. Escrito el 14 de noviembre de 2026 contra el código
del commit `5db657b`.

## Qué es y qué no es

Es el agente editorial de `programascontabilidad.com`. **Elige** qué trabajar cada día a partir
de datos de Search Console, **escribe** la pieza con un modelo a través del gateway de Alegra,
**la valida** con controles deterministas, **la juzga** con un modelo de otra familia y la
**publica** en WordPress por su MCP.

No es un chat que redacta cuando se le pide: la decisión de qué publicar y la de si una pieza
sale son de código, no del modelo. El modelo escribe y opina; el código decide.

## Dónde vive cada cosa

| Pieza | Dónde | Notas |
|---|---|---|
| Código | GitHub privado `sharongrueso-eng/Agente-Programas-de-Contabilidad`, rama `main` | Coolify despliega de ahí |
| Imagen | Coolify, `deploy/Dockerfile` | Python puro, sin Hermes dentro; el contenedor duerme con `sleep infinity` para que la tarea tenga dónde correr |
| Estado | Volumen montado en `/data` | Corridas, mapas de publicación, caché de GSC, sitemap |
| Sitio | WordPress de producción, por el **MCP** (`ewpa/*`) | El MCP escribe meta y autor; la API REST solo se usa para leer y verificar |
| Datos de tráfico | Google Search Console, cuenta de servicio | Ventanas de 28 días |
| Modelos | LiteLLM de Alegra (`OPENAI_BASE_URL`) | Productor, juez y corrector de familias distintas |
| Avisos | Webhook de Google Chat | Un aviso por pieza, en el momento en que ocurre |

## El flujo de una corrida

Cada etapa devuelve el mismo contrato (`status`, `task_id`, `block_reason`, `resume_from`), así
que una corrida se puede retomar desde el punto donde se cortó.

| # | Etapa | Módulo | Qué produce |
|---|---|---|---|
| 1 | **Disparo** | Scheduled Task de Coolify → `scripts/corrida_diaria.py` | Comprueba pausa, ventana horaria y fin de semana; elige el mercado del día |
| 2 | **Rotación** | `orchestrator/rotation.py` | Slot y país como función pura de la fecha: 3 formatos × 4 países, seis días hábiles cubren las doce combinaciones, sin calendario guardado |
| 3 | **Preflight** | `scripts/corrida_diaria.py`, `corrida_completa.verificar_entorno` | Verifica todas las variables de una vez y nombra las que faltan; sin esto no se gasta un token |
| 4 | **Auditoría** | `orchestrator/gsc_io.py`, `gsc_api.py`, `gsc_mcp.py`, `audit.py` | Oportunidades tipadas con acción y puntaje **en clics**; se niega a trabajar con métricas viejas (máximo 7 días) |
| 5 | **Selección** | `assigner.py`, `decision.py`, `mercado.py` | Elige el trabajo más barato que mueve el número y **verifica que el artículo sea del mercado del slot** leyendo su contenido, no su URL |
| 6 | **Brief** | `brief_io.py` | Brief del día: URL, acción (`refresh_snippet`, `refresh_structure`, `refresh_by_decline`, `create`), keyword, intención |
| 7 | **Investigación** | `registry.py`, `directorio.py`, `competidores.py`, `recolector.py` | Carga las fichas del país y el registro legal; todo dato citable sale de ahí, con su fuente y fecha |
| 8 | **Producción** | `producer.py`, `sections.py`, `presentacion.py`, `linea_visual.py` | La pieza se genera **por bloques** con el mismo mensaje de sistema (para que el caché del gateway acierte); los componentes visuales los pone el código, no el modelo |
| 9 | **Validación** | `validator.py`, `formato.py` | 20 controles deterministas; devuelve un estado por control y el peor como veredicto |
| 10 | **Reparación** | `reparacion.py` | Arregla lo que tiene una sola respuesta correcta (tabla sin pie, meta de un carácter de más, enlaces que faltan) **antes** de pagar un juez |
| 11 | **Juez** | `judge.py` | Modelo de otra familia: intención, profundidad, y que la pieza cumpla lo que promete el título. Separa bloqueantes de advertencias |
| 12 | **Corrector** | `corrector.py` | Arreglos acotados por fragmento, con guarda de aceptación: mismos enlaces, ninguna cifra nueva, ninguna marca nueva, tamaño dentro de un cuarto |
| 13 | **Publicación** | `publisher.py`, `mcp_publish.py` | Compuertas → crear en borrador → escribir metas → releer → publicar. Si la relectura no coincide, revierte |
| 14 | **Aviso y cierre** | `notices.py`, `runner.py` | Aviso al Chat en el momento, checkpoint en la carpeta de la corrida |

### Las compuertas del publicador

Publica solo si pasan cinco, y cualquier fallo deja el sitio sin tocar: pausa global, chequeo
del día, tope diario, ventana horaria y huella del contenido (lo aprobado tiene que ser
exactamente lo que se escribe).

Después de escribir **relee la URL pública** y compara título, H1, meta, robots e imagen
destacada. Un `200` del MCP no prueba nada: el MCP puede aceptar una escritura y no aplicarla.

## Los controles deterministas

Veinte controles, cada uno con su severidad. `BLOQUEADO` detiene la pieza; `CORREGIR` la manda
al corrector.

| Grupo | Controles | Severidad |
|---|---|---|
| Estructura del formato | `presupuesto_tablas` (comparativa 3, guía 2, lista 4), `marcas_del_formato` | BLOQUEADO |
| Mercado y normativa | `country_norms` (ninguna autoridad de otro país; en RD nunca la sigla «RD») | BLOQUEADO |
| Elenco | `elenco_cerrado`, `marca_desconocida` | BLOQUEADO / CORREGIR |
| Cifras | `registry_amounts`: una cifra con moneda que no está en las fichas del mercado | CORREGIR |
| SEO | `slug_keyword`, `slug_year`, `title_keyword`, `meta_keyword`, `meta_length`, `h1_keyword`, `intro_keyword` | Mixto |
| Enlazado | `alegra_links` (tres con UTM completa; exento cuando el título cierra el elenco sin Alegra), `internal_links` (5), `sources` (2 externas) | CORREGIR |
| Honestidad | `testing_claims` («probé» sin evidencia), `improvement_claims` (porcentajes sin respaldo) | CORREGIR |
| Presentación | `linea_visual`: pie de fuente y fecha en cada tabla, FAQ en `<details>`, un solo CTA al cierre | CORREGIR |
| Jerga | `internal_jargon`: GSC, `run_id`, «compuerta» y compañía no se leen en el artículo | CORREGIR |

La cifra fuera de registro es el control más fuerte contra datos inventados: si la pieza
menciona un importe con moneda que no está en las fichas del mercado, no llega al juez.

## Las skills que usa

Las skills son la voz editorial del portal. Viven en `skills/` y se editan como documento, no
como código; `tests/test_skills_contract.py` vigila que las decisiones del equipo sigan escritas
ahí.

| Skill | Qué gobierna | Dónde se usa |
|---|---|---|
| `skills/prog-cont-blog/SKILL.md` | Formato de reseñas, comparativas y guías; la regla de la sugerencia sutil de Alegra; módulos de Alegra por país; capturas de landings; pitfalls comprobados (portada duplicada, autor 17, tablas con formato de marca, redirecciones en tabla propia de Rank Math) | Productor, juez y las reparaciones |
| `references/` de esa skill | `formatos.md` (plantillas exactas), `wordpress-prog-cont.md` (receta de publicación), `alegra-modulos-por-pais.md`, `precios-alegra-{co,mx,cr,do}.md`, `refresco-de-precios.md` (procedimiento por lotes), `portada-y-medios.md`, `auditoria-blog-seo-aeo.md`, `migracion-colombia.md`, `kit_visual_html_programas_contabilidad_hermes.md` | Se cargan según la etapa |
| `skills/marco-legal/legal-context.md` | Normativa vigente por mercado con número exacto y enlace oficial: DIAN 000165/2023 y 000227/2025 en Colombia, CFDI 4.0 en México, TRIBU-CR y MH-DGT-RES-0027-2024 en Costa Rica, Ley 32-23 y Decreto 587-24 en RD | Se extrae la sección del país de la pieza y **falla** si no está |
| `skills/pdc-locale-signals/SKILL.md` | Señales de idioma y localidad por página: `html lang`, `og:locale` e `inLanguage`/`areaServed` en el JSON-LD | Al cerrar la pieza |

**Pendiente:** la skill `leandro` y sus referencias completas nunca llegaron a este equipo; el
inventario del 6-nov las da por ciertas y `skills/README.md` les asigna correcciones legales. Ese
README está desactualizado respecto de la carpeta: menciona `leandro` donde hoy está
`prog-cont-blog`, y da por hecho un `SKILL.md` de 41.808 bytes que no es el que se usa.

## Los datos con los que trabaja

| Ruta | Qué es | Regla |
|---|---|---|
| `datos/herramientas/*.json` | Fichas de competidores por mercado: planes con precio, moneda, periodo, funciones, fuente y fecha de consulta | Única fuente citable. Si el proveedor no publica precio, la ficha lo dice y el artículo también. Nunca se estima |
| `datos/competidores/directorio.json` | Qué marcas existen en cada país y con qué nivel (A con ficha, B mención, C no se nombra) | Una marca que no está no se nombra |
| `datos/competidores.json` | Relación aprobada de competidores con su URL de precios | Solo esas reciben enlace |
| `skills/marco-legal/legal-context.md` | Normativa por mercado | Se cita con número y enlace, no de memoria |
| `contexto/estrategia-editorial.md` | Qué se refresca y qué se crea; medidas del blog (H2, tablas, imágenes, enlaces) | Fija el presupuesto de forma |
| `contexto/decisiones.md` | Decisiones fechadas del equipo | Manda sobre la interpretación del modelo |
| `rules/gsc.json` | Frescura máxima de los datos, ventanas, mínimo de impresiones por mercado | Umbrales en configuración, no en ramas del código |
| `rules/limits.json` | Pausa, `dry_run_only`, tope diario, ventana | **Ojo:** hoy está en `paused: true` y `dry_run_only: true`; lo lee el CLI (`orchestrator/cli.py`), no el wrapper de Coolify |

## El estado que sobrevive

```
/data/state/
  corridas/<task_id>/
    brief.json          qué se decidió hacer y por qué
    borrador.json       la pieza, con su huella
    consumo.json        llamadas, tokens de entrada, salida y razonamiento
    veredictos.json     controles y juez
    publicacion.json    post_id, URL, estado
    checkpoint.json     last_step y resume_from
    progreso.json       qué bloques van escritos, cuáles faltan — la única evidencia si la tarea se agota
    interrupcion.json   motivo y último paso, cuando el proceso recibe SIGTERM
    respaldo.json       título y extracto previos, si se tocó un vivo
  refreshes.json        diario de reencauches: una URL no se repite en 30 días
  publicados.json       run_id → post_id (el MCP no sabe buscar por meta)
```

Todo se escribe de forma atómica (archivo temporal + reemplazo) y falla cerrado: un archivo
corrupto bloquea la corrida en vez de tratarse como vacío.

## Los avisos

Un aviso por pieza **en el momento** en que ocurre, no al cierre. Plantillas fijas en
`notices.py`: `slot_publicado`, `borrador_listo`, `bloqueo`, `corrida_fallida`,
`chequeo_fallido`, `registro_vencido`, `reporte_diario`, `sin_reporte`.

El aviso lleva lo que hace falta para decidir en diez segundos: título, slug, si es nueva o
actualización en la misma URL, las cifras de GSC que justificaron la elección, el veredicto con
sus conteos y el enlace a wp-admin.

## Cómo se opera

| Quiero… | Comando |
|---|---|
| Ver si el sitio está como creo | `python scripts/diagnosticar_post.py --respaldo state/respaldos/post-XXXX-....json --brief datos/muestra/brief-XXXX.json` |
| Respaldar antes de tocar | `python scripts/respaldar_post.py --post 5309 --entorno prod` (archivo local; `--duplicado` si de verdad hace falta copia en el CMS) |
| Probar el webhook | `python scripts/corrida_completa.py --probar-aviso` |
| Revertir un cambio | `python scripts/corrida_completa.py --revertir <post_id>` |
| Correr a mano fuera de ventana | `PDC_FORZAR=1 python scripts/corrida_diaria.py` |
| Pausar todo | `PDC_PAUSA=1` y redesplegar |
| Poner la firma a una pieza | `python scripts/firmar_posts.py --posts 5309,1957` (`--aplicar` para escribir) |
| Probar la suite | `python -m unittest discover -s tests -t tests -p "test_*.py"` |

## Qué falta documentar

1. **La skill `leandro`**: no está y `skills/README.md` la describe como si estuviera. Hay que
   traer la versión vigente y reconciliar el README con la carpeta.
2. **Un mapa de credenciales**: qué variable usa cada módulo, quién la custodia y cada cuánto se
   rota. Hoy está repartido entre `deploy/credenciales.md` y el código.
3. **El calendario de vigías**: precios los días 1 y 16, funciones lunes y viernes, regulación y
   caídas a diario — está en la intención de `watchers.py`, no en una tabla que alguien pueda leer.
4. **El costo por pieza en el tiempo**: `consumo.json` se escribe, pero no hay serie histórica ni
   una tabla de referencia (la última medida: 35 llamadas, 491.395 tokens de entrada, 162.354 de
   razonamiento).
5. **Los umbrales editoriales de `rules/`**: hoy `limits.json` sigue en modo seco y no lo lee el
   wrapper; hay que decidir cuál de las dos puertas manda en producción.
