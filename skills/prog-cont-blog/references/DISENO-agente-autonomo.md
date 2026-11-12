# Diseño del agente autónomo — programascontabilidad.com

*Documento de diseño v1. Revisión hecha contra el sitio en vivo, WordPress por MCP, Ahrefs y Search Console.
Base original: 3 de noviembre de 2026. Versión para compartir.*

---

## 1. Punto de partida (verificado)

### Lo que ya funciona

| Pieza | Estado | Evidencia |
| --- | --- | --- |
| Publicar por MCP (post, media, Rank Math, schema FAQ) | Funciona | 12 piezas escritas y verificadas por este camino |
| Portadas generadas con Gemini | Funciona | 7 jpg + receta documentada |
| Capturas de landing con Chrome headless | Funciona | 14 png, 2 por pieza |
| Formato de marca (tablas con fondo, FAQ H3 + schema, ficha de autor) | Verificado en vivo | 1 portada, 2 capturas, 4/4 tablas con fondo en las piezas revisadas |
| Preflight anti-canibalización | Documentado y usado | Evitó 5 duplicados y canceló 3 redirecciones destructivas |
| Reporte a Google Chat | Funciona | Script `gchat.py` |
| Fuente de datos | Solo Ahrefs | DataForSEO se retiró |

### Lo que falta para que sea autónomo

| Falta | Por qué bloquea |
| --- | --- |
| **Search Console del dominio** | La cuenta tiene `alegra.com`, `blog.alegra.com`, `elmejorsoftware.mx` y `siemprealdia.co`, pero **no `programascontabilidad.com`**. Sin GSC el agente no puede medir ninguna URL: decide a ciegas y no cierra el bucle. Ahrefs actualiza una vez al mes y no atribuye el efecto de una intervención. |
| **Mapa de demanda** | No hay lista de oportunidades con volumen medido. La auditoría agrupó lo existente, pero no hay `backlog-temas.json` con «tema → país → volumen → dificultad → intención → URL que lo cubre». |
| **Motor de ciclo** | Hoy son 17 scripts de lote, uno por tarea. No hay un `ciclo.py` idempotente que decida, redacte, valide y publique en una sola corrida. |
| **Estado persistente** | No hay registro de trabajos por (país, tema) con clave normalizada. Sin eso, dos corridas producen el mismo artículo. |
| **Validador ejecutable** | El postflight está escrito en prosa. Un control que no es código no rechaza nada. |
| **Cron** | Las tareas programadas activas son de otro portal (IE Panamá). Este se dispara a mano en conversación. |
| **Medición AEO** | DataForSEO daba las menciones en asistentes. Ahrefs las da con Brand Radar, pero **no hay report del dominio**. |

### Estado del archivo

- 343 publicadas · 21 borradores · 6 pendientes.
- **171 de 343 entradas (50 %) sin una sola sesión orgánica en 30 días.**
- 176 sin ninguna imagen en el cuerpo · 69 con menos de 600 palabras · 31 sin imagen destacada.
- Cadencia 2026: enero 2 · marzo 14 · abril 13 · mayo 8 · junio 10 · julio 8 · agosto 9 · septiembre 5 · octubre 2.
- Tráfico: 1.500 sesiones orgánicas / 30 días, 1.169 usuarios, engagement 61,8 %.

**Conclusión:** el portal no necesita más artículos para crecer; necesita **arreglar y medir** lo que tiene
antes de sumar volumen. Un agente que solo escriba va a acelerar el problema.

---

## 2. El flujo, paso a paso (lo que hay que replicar)

```
[1] PREFLIGHT      Ahrefs: volumen + SERP del término en el país
                   + focus keyword de vecinos (Rank Math) + /posts?search=
                   → ¿la intención ya está publicada? refrescar : crear
[2] DATOS          Precios y funciones en la landing oficial, con fecha
                   + capturas con Chrome headless
[3] BRIEF          Ángulo, país, CTA por país, 2-4 interlinks reales
[4] REDACCIÓN      Reseña / comparativa / guía, bloques Gutenberg
[5] VALIDACIÓN     excerpt 138-160 · SEO title ≤60 · desc 140-160 · ≥6 H2 ·
                   ≥1 tabla con fondo · FAQ H3 == schema · autor correcto · UTM
[6] IMAGEN         Portada generada (revisada con visión) + 2 capturas en el cuerpo
[7] PUBLICACIÓN    crear post en draft → media → Rank Math → schema FAQ → ficha de autor
[8] POSTFLIGHT     Leer el sitio: imágenes dentro de <article>, tablas, H3, enlaces 200
[9] REPORTE        Google Chat con lo hecho, lo pendiente y el enlace de edición
```

Cada paso existe y está probado. La autonomía **no** requiere inventar nada: requiere que los pasos 1 y 5
sean código, que el paso 2 se alimente de una cola de temas con datos, que el paso 3 lo decida una regla y
no una persona, y que haya estado para no repetir.

---

## 3. Arquitectura (v1: un solo motor, configuración por país)

Misma decisión que en otros portales del equipo: **el coste depende de cuántos artículos se producen, no de
cuántos programas los produzcan**. Un motor con `--pais` y un archivo de configuración por mercado.

```
prog-cont/
├─ agent/
│  ├─ ciclo.py            # orquestador: detectar → decidir → brief → redactar → validar → publicar → verificar
│  ├─ datos/
│  │  ├─ ahrefs.py        # volumen, SERP, keywords del sitio, unidades gastadas
│  │  ├─ gsc.py           # clics, impresiones, posición por URL (cuando exista la propiedad)
│  │  └─ inventario.py    # los 343 posts: slug, título, keywords, palabras, imágenes
│  ├─ decidir.py          # ranking de oportunidades + anti-canibalización
│  ├─ brief.py            # ángulo, CTA por país, interlinks reales
│  ├─ redactar.py         # modelo → HTML con bloques
│  ├─ validar.py          # GATE: devuelve ok/errores; sin ok no se publica
│  ├─ medios.py           # portada + capturas + alt
│  ├─ publicar.py         # MCP del portal
│  ├─ verificar.py        # lee el HTML publicado y cuenta lo que debe contar
│  └─ estado.json         # trabajos, intentos, tokens, URLs intervenidas con fecha
├─ backlog-temas.json     # la cola: tema, país, volumen, dificultad, intención, URL que lo cubre
└─ crons                  # 3 jobs: propuesta diaria, producción, refresco de precios
```

### Regla de oro: primero que corra, después que crezca

1. **Un** país produce y publica sin intervención.
2. **Tres corridas limpias seguidas** antes de abrir el segundo país.
3. Cada regla nueva entra con una corrida real, no con un plan.

### Los tres modos

| Modo | Qué hace | Coste |
| --- | --- | --- |
| `--plan` | Lee Ahrefs + inventario y muestra **qué escribiría hoy y por qué**, sin llamar al modelo | ~50 unidades Ahrefs, 0 tokens |
| `--borrador` | Escribe el artículo completo y lo deja en WordPress como draft + aviso en Chat | ~12k tokens por artículo |
| `--publicar` | Igual, pero publica si el validador da `ok` | Igual + riesgo editorial |

**Arranque recomendado:** dos semanas en `--plan` y `--borrador`. La publicación automática entra cuando el
validador lleve 10 piezas sin un solo fallo en postflight.

### Lo que el agente NO puede hacer (reglas no negociables)

1. **Nunca cambia un slug ni una URL publicada.** En un refresco no se envía `slug`.
2. **Nunca borra ni mueve contenido** sin aprobación explícita; la poda se propone con evidencia (0 sesiones
   en 90 días), no se ejecuta.
3. **Los borradores salen a nombre del autor del portal** (no de la cuenta que autentica por API).
4. **Ninguna cifra la produce el modelo**: precios y datos salen de la landing oficial con fecha de consulta.
5. **Un solo enlace de Alegra en el cuerpo + un CTA con UTM**, y ningún módulo que Alegra no tenga en ese país.
6. **Una URL intervenida espera 15 días** antes de volver a tocarse (el reloj va por URL, no por tema).
7. **Un fallo no cuenta como terminado**: el estado guarda el paso y el error, y el reintento reanuda.

### Cómo elige el tema

El agente no elige «el tema con más volumen». Ordena por:

```
prioridad = (volumen × intención comercial) / dificultad
            + bonus si ya tenemos URL con posición 5-20 (intervenir rinde más que crear)
            - penalización si el slug o el título se solapan con un vecino (>0,75)
```

Y solo crea contenido nuevo cuando la intención **no** está cubierta. Lo ya cubierto se refresca: es más
barato y el portal tiene 171 URLs sin tráfico que primero hay que rescatar.

---

## 4. Datos: cómo se usa Ahrefs

| Pregunta | Herramienta | Coste medido |
| --- | --- | --- |
| Volumen, dificultad, intención | `keywords_explorer_overview` | 41 unidades / fila |
| Top 10 real del país | `serp_overview` con `type=organic` | 3 unidades / fila (~30 por SERP) |
| Keywords de un competidor | `site_explorer_organic_keywords` | Por fila |
| Rendimiento de nuestras URLs | GSC (`gsc_pages`, `gsc_keywords`) — **falta la propiedad** | 0 |
| Menciones en asistentes de IA | `brand_radar_ai_responses` — **falta el report** | Según report |
| Saldo | `subscription_info_limits_and_usage` | 0 |

Con el saldo del plan actual, un preflight son ~50 unidades: el ciclo diario no llega al 1 % del plan.

Trampas comprobadas: sin `type=organic` el SERP trae filas duplicadas y filas con `url: null`; `positions`
omite huecos (si el puesto 1 es un anuncio, empieza en 2); `select` es obligatorio.

---

## 5. Plan de arranque 30/60/90

### Semana 1 — cerrar los dos huecos de datos

Sin ellos no hay agente, hay generador de texto.

1. **Agregar el dominio a Search Console** y dar permiso de lectura a la cuenta de servicio del equipo. Es la
   acción que solo puede hacer alguien con permiso de propietario en la consola de Google.
2. **Construir `backlog-temas.json`**: keywords del portal (Ahrefs `site_explorer_organic_keywords`) + huecos
   frente a los competidores relevantes, por país. Es una corrida de ~15 consultas.
3. **Crear el report de Brand Radar** del dominio para medir AEO (opcional esta semana, obligatorio antes de
   cualquier informe de visibilidad en IA).

### Semanas 2-3 — motor en seco

4. `ciclo.py --plan` corriendo a diario en cron y mandando a Chat «hoy escribiría esto y por esto», con
   volumen, dificultad, SERP y URL que ya responde.
5. Validar 10 propuestas seguidas con criterio editorial. Si la mitad no sirve, el problema está en el
   ranking, no en la redacción.

### Semanas 4-6 — producción a borrador

6. `--borrador` con un país, 2 piezas por semana, con aviso y enlace de edición.
7. Validador en código con los 10 checks del postflight. Nada se publica sin `ok`.
8. Medición: tokens por artículo, unidades Ahrefs por corrida, tiempo de corrida.

### Semanas 7-12 — publicar y refrescar

9. Auto-publicación cuando haya 10 piezas limpias seguidas.
10. **Segundo cron: refresco de precios a 90 días** (el procedimiento por lotes ya existe y es el que más
    rápido paga: hay piezas con las cuatro tarifas mal).
11. Tercer cron: informe mensual con GSC (antes/después por URL intervenida).

---

## 6. Decisiones abiertas

| # | Decisión | Opciones | Recomendación |
| --- | --- | --- | --- |
| D1 | ¿Publica solo o deja borrador? | (a) borrador siempre · (b) borrador las primeras 10 y luego auto-publicación · (c) publica desde el día 1 | **(b)** |
| D2 | Países y cadencia de arranque | MX+CO 2/semana cada uno · solo MX 3/semana · los 6 países 1/semana | **MX+CO, 2/semana** |
| D3 | ¿Qué prioriza al principio? | crear temas nuevos · refrescar las 171 sin tráfico · precios viejos | **refrescar + precios**, crear 1 de cada 3 |
| D4 | ¿Se retira el conector DataForSEO? | quitarlo entero · dejarlo instalado sin usar | **quitarlo**, pero es global: lo usan otros flujos, así que va después de confirmar |

---

## 7. Riesgos y cómo se mitigan

- **Canibalización acelerada.** El ranking excluye lo ya cubierto *antes* de elegir, no después. Un tema
  repetido no entra en la cola.
- **Precios inventados.** El modelo nunca escribe una cifra: las extrae el código del HTML de la landing y las
  guarda con fecha. Si la extracción falla, la pieza queda en `necesita_datos`.
- **HTML roto o portada duplicada.** El validador cuenta las figuras con la `src` de la portada: debe ser
  exactamente 1 (es el error que ya costó 5 artículos).
- **Coste del modelo descontrolado.** Techo diario de tokens con acumulador; si se alcanza, la corrida no
  arranca y avisa. Y `--plan` para los días en que solo se quiere criterio.
- **El agente toca una URL que rankea.** Prohibido por regla: el refresco no envía slug, y una URL intervenida
  espera 15 días.
