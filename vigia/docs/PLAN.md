# Plan de trabajo en Hermes

Una tarea por conversación con Hermes, en una rama propia, con PR al terminar. Cada tarea trae el texto
para pegarle a Hermes y su criterio de «listo». El orden sigue la guía (`docs/GUIA.md`). Empieza cada
pedido con «Carga la skill vigia-precios y…».

Hay cuatro vigías (MEX, COL, CRI y DOM) con un solo código. Las tareas de código (T4 a T9) se hacen una
vez para los cuatro; las de datos (T2 y T3) se hacen **una vez por vigía**: cambia `<vigía>` por `mex`,
`col`, `cri` o `dom`. Orden sugerido: COL, MEX, DOM y CRI (de más a menos cifras).

| # | Tarea | Paso de la guía | Necesita |
|---|---|---|---|
| T1 | Verificar el entorno | — | Dependencias instaladas en el contenedor de Hermes |
| T2 | Fuentes de prioridad 1, por vigía | 3 | Red con los dominios de las marcas |
| T3 | Registro de precios de Alegra, por vigía | 2 | Red con alegra.com |
| T4 | Lector con Playwright | 4 | Chromium instalado en el contenedor |
| T5 | Comparador | 5 | — |
| T6 | Comprobación en cada cambio (CI) | 9 | — |
| T7 | Avisos en Google Chat | 8 | `GCHAT_WEBHOOK_URL` en el entorno de Hermes |
| T8 | Corrida programada en modo ensayo | 9, 10 | T4, T5, T7 |
| T9 | Actualizador todo o nada | 6 | Aprobación explícita y un post de borrador para probar |
| T10 | Conectar el agente diario al registro | 11 | T3 |

---

## T1 · Verificar el entorno

> Carga la skill vigia-precios. Lee `vigia/docs/ESTADO.md`. Comprueba que estén instaladas las
> dependencias de `vigia/requirements.txt` y que Playwright tenga Chromium (no lo instales si falta:
> repórtalo). Corre las pruebas de `vigia/tests`. Después regenera el inventario con el procedimiento de
> la skill y compara los conteos con los de
> `ESTADO.md` (1.120 cifras, 64 fuentes y 16 sin país; por vigía, la tabla de ESTADO.md). No subas los archivos regenerados: solo
> reporta las diferencias y, si las hay, explica de dónde salen (posts nuevos, precios cambiados, una
> falla del entorno).

**Listo cuando:** las pruebas pasan y el informe dice si el inventario se reproduce igual.

## T2 · Fuentes de prioridad 1 de un vigía (paso 3)

> Carga la skill vigia-precios. Trabaja el vigía `<vigía>`: lee `vigia/paises/<vigía>/PAIS.md` y toma
> las fuentes con `"prioridad": 1` de `vigia/paises/<vigía>/fuentes.json`, empezando por las que no son
> de Alegra. Para cada una: encuentra la página oficial de precios de esa marca para ese país (usa
> `url_candidatas` como pista, no como verdad); ábrela y anota la moneda que se ve desde el entorno, las
> señales del país (impuesto, ente fiscal, dominio) y si la página elige el país por ruta, por
> cookie/selector o por IP. Llena `url`, `url_verificada`, `moneda_esperada`, `senales_pais` y
> `modo_lectura`. Las señales del país se comprueban con `vigia/senales-pais.json`: si la página
> muestra señales de otro país, anótalo. Si la moneda que ves no corresponde al país, marca
> `modo_lectura: "ip"` y no adivines el precio. Si la marca no publica precios, usa
> `modo_lectura: "no_publica"`. Guarda el HTML de cada página en
> `vigia/paises/<vigía>/lecturas/<fecha>/<id>.html` como evidencia.

**Listo cuando:** las fuentes de prioridad 1 del vigía tienen esos campos llenos o una nota de por qué
no, y el PR resume cuáles necesitan lectura manual o proxy.

## T3 · Registro de precios de Alegra (paso 2)

> Crea `vigia/paises/<vigía>/registro-precios.json` con los planes de Alegra de ese país, leídos de su
> página de precios (está en `PAIS.md`). En Colombia cada producto está en un
> contenedor `pricing-cards-<producto>`; en los otros países los planes siguen el patrón
> «<plan> $X $Y / mes … Facturado $Z anualmente». Por plan guarda: clave, marca, producto, país, plan,
> moneda, mensual, anual_equivalente_mes, anual_facturado, fórmula, límites, fuente, fecha_consulta y
> `campana_activa`. Usa el esquema del paso 2 de la guía. Agrega pruebas que comprueben las fórmulas
> (facturado = 12 × equivalente mensual) y que el descuento anual de cada país coincida con
> `REGLAS-VIGIA.md`.

**Listo cuando:** el registro cubre los cuatro países, las pruebas pasan y el PR lista los planes cuyo
nombre no coincide con los anexos E y F de la skill prog-cont-blog.

## T4 · Lector con Playwright (paso 4)

> Construye `vigia/lector.py`, que recibe el vigía (`--pais mex|col|cri|dom`) y lee solo sus fuentes:
> abre cada una con Chromium (Playwright) a 1440 px, idioma y zona horaria del país; comprueba que la
> página tenga señales del país con `vigia/inventario/pais.py`; lee los precios del DOM con la receta de la fuente; lee **dos veces** en contextos
> separados; detecta campañas según `REGLAS-VIGIA.md`; aplica la regla de moneda; y guarda cada lectura
> con fecha en `vigia/paises/<vigía>/lecturas/AAAA-MM-DD/<fuente>.json` junto con su HTML. Las pruebas deben correr
> sobre HTML guardado (sin red): una página normal, una con campaña, una con la moneda equivocada y una
> con la receta rota.

**Listo cuando:** el lector corre sobre las fuentes de Alegra y las pruebas cubren los cuatro casos.

## T5 · Comparador (paso 5)

> Construye `vigia/comparador.py`, que clasifica cada lectura contra el registro en los siete
> resultados de la guía: sin cambios, cambio explicable, plan nuevo/retirado/renombrado, campaña
> activa, lectura dudosa, cambio de mercado y falla. Una prueba por resultado en
> `vigia/tests/test_comparador.py`.

**Listo cuando:** las siete pruebas pasan.

## T6 · Comprobación en cada cambio

> Agrega `.github/workflows/vigia-comprobar.yml`: en cada push y PR que toque `vigia/`, instala
> `vigia/requirements.txt`, corre `python -m compileall vigia` y `python -m pytest -q vigia/tests`.

**Listo cuando:** el workflow corre en el PR y queda en verde.

## T7 · Avisos en Google Chat (paso 8)

> Conecta el vigía con el `gchat.py` que ya usa el agente (búscalo en el repositorio o en la carpeta de
> scripts de Hermes). Un
> resumen por corrida y cada problema una sola vez por día, con los colores 🟢 🟡 🔴 de la guía. El
> webhook se lee de `GCHAT_WEBHOOK_URL` y nunca se escribe en archivos. Cada vigía firma sus avisos
> con su prefijo (`[MEX]`, `[COL]`, `[CRI]`, `[DOM]`). Confirma el envío por el `name`
> que devuelve la API de Chat, no por el código 200. En las pruebas, simula el envío.

**Listo cuando:** las pruebas cubren el resumen, la deduplicación y los tres colores.

## T8 · Corrida programada en modo ensayo (pasos 9 y 10)

> Crea `vigia/correr.py`, el punto de entrada de una corrida de **un** vigía: `python -m vigia.correr
> --pais <vigía>`. Lleva candado por vigía (dos corridas del mismo país no se pisan; las de países
> distintos sí pueden convivir), lector, comparador, avisos y commit de lecturas y registro en una rama
> `vigia/lecturas-<vigía>`. Arranca en `ensayo`: lee, compara y avisa lo que cambiaría, sin tocar
> WordPress. El modo sale de `VIGIA_MODO_<VIGÍA>` (por ejemplo `VIGIA_MODO_COL`) y, si no existe, de
> `VIGIA_MODO`. No lo programes en el cron de Hermes: deja en `docs/ESTADO.md` los cuatro comandos para
> las tareas programadas de Coolify.

**Listo cuando:** los cuatro vigías corren en modo ensayo, cada uno deja sus lecturas y su resumen en
Chat, y las cuatro tareas de Coolify quedaron creadas por una persona.

## T9 · Actualizador todo o nada (paso 6)

> Solo con aprobación explícita. Construye `vigia/actualizador.py` siguiendo el paso 6 de la guía y el
> anexo G de la skill prog-cont-blog: respaldo de `content.raw`, dry-run con conteos, marcadores cuando
> los valores se pisan, conteo de bloques Gutenberg, verificación en la página pública con limpieza de
> caché y restauración total si algo falla. Pruébalo contra un post de borrador, nunca contra uno
> publicado.

**Listo cuando:** la prueba sobre el borrador cambia la cifra, la verifica y, con un error forzado,
deja todo como estaba.

## T10 · Conectar el agente diario al registro (paso 11)

> Haz que el productor del agente diario tome los precios de competidores del registro (si la fecha de
> consulta tiene 16 días o menos) y que su validador bloquee cualquier pieza con un precio que no esté
> en el registro. El corrector solo puede usar cifras de la pieza o del registro, copiadas exactas.

**Listo cuando:** una pieza de prueba con un precio inventado queda bloqueada.
