---
name: vigia-precios
description: Construye, opera y consulta los cuatro vigías de precios de Programas de Contabilidad (PdC) —MEX, COL, CRI y DOM—, que mantienen al día los precios de Alegra y de competidores publicados en programascontabilidad.com. Úsala para tareas del plan, regenerar el inventario, reconocer el país de una cifra, revisar fuentes o explicar un aviso.
version: 1.1.0
metadata:
  hermes:
    tags: [pdc, precios, vigia, wordpress]
    related_skills: [prog-cont-blog]
required_environment_variables:
  - name: GCHAT_WEBHOOK_URL
    prompt: "Webhook del espacio de Google Chat del agente de PdC"
    help: "El mismo que usa gchat.py del agente diario"
    required_for: "Avisos del vigía en Google Chat"
---

# Vigías de precios de PdC

Hay **cuatro vigías, uno por país: MEX, COL, CRI y DOM**, con un solo código. Cada uno lee las páginas
oficiales de precios de su país, compara contra su registro y solo aplica el cambio que se puede
explicar; todo lo demás se avisa en Google Chat con el prefijo del país. **El código compara y valida, el
modelo solo opina donde haga falta y las decisiones las toma una persona.**

Si un pedido no dice de qué vigía se trata, pregunta cuál (o si son los cuatro) antes de empezar.

## Dónde está todo

Todo vive en el repositorio del agente de PdC, en la carpeta `vigia/`. Esta skill no guarda datos: los
lee del repositorio.

| Qué | Dónde (dentro de `vigia/`) |
|---|---|
| Estado, hallazgos y decisiones abiertas | `docs/ESTADO.md` — léelo antes de cualquier tarea |
| Tareas en orden, con texto y criterio de «listo» | `docs/PLAN.md` |
| Guía de los 12 pasos | `docs/GUIA.md` |
| Decisiones (DEC-001…) | `docs/decisiones.md` |
| Reglas fijas (borrador) | `REGLAS-VIGIA.md` |
| Lo propio de cada país (monedas, señales, descuento de Alegra, campañas, horario) | `paises/<vigía>/PAIS.md` |
| Inventario, fuentes y pendientes de cada vigía | `paises/<vigía>/ubicaciones.json`, `fuentes.json`, `pendientes.json` |
| Señales para reconocer el país | `senales-pais.json` |
| Cifras sin país reconocido y metadatos en conflicto | `sin-pais.json` |
| Scripts del inventario | `inventario/` |
| Pruebas | `tests/` |

## Cómo se reconoce el país

- **Nunca por la URL.** Los enlaces del blog no siempre dicen de qué país es una pieza.
- Por las señales propias de cada país en el texto, con su peso en `senales-pais.json`: SAT, CFDI, RFC
  (México); DIAN, UVT, exógena, NIT (Colombia); DGII, ITBIS, e-CF, NCF, RNC (República Dominicana);
  Hacienda, TRIBU-CR, factura electrónica 4.4, colones (Costa Rica); y las monedas de cada uno.
- De lo más cercano a lo más amplio: moneda de la cifra → frase o fila → sección → título → post →
  metadato `pdc_target_country`. Para probarlo: `from pais import puntajes, decidir` en `vigia/inventario`.
- Si no hay un país claro, la cifra va a `sin-pais.json`; no la asignes a un vigía por intuición.
- Si las señales contradicen el metadato del post, ganan las señales y se avisa.
- Si encuentras una palabra propia de un país que falta, agrégala a `senales-pais.json` con su peso,
  agrega un caso a `vigia/tests/test_pais.py` y corre las pruebas.

## Reglas que no se rompen

1. **No escribas en WordPress** (ni por API ni por el MCP `prog-cont`) salvo en una tarea del plan que
   lo pida de forma explícita. Para leer, usa la API pública (`/wp-json/wp/v2/...`) o el MCP.
2. **Nunca conviertas una moneda** para que una tabla cuadre. Moneda inesperada = lectura dudosa.
3. **Los precios salen del DOM o del HTML**, nunca de una captura ni de un resumen.
4. **No inventes cifras.** Si una marca no publica un precio: «no publica», nunca «no tiene». Si no puedes
   atribuir una cifra con certeza, va a `pendientes.json`.
5. **Las promociones de temporada no son cambios de precio.** Tampoco el descuento permanente por pago
   anual («25% OFF para usuarios nuevos», «10% OFF») ni la etiqueta «Más popular».
6. **Las llaves nunca van en archivos, commits, mensajes de chat ni salidas.** Se leen de las variables
   del entorno. Si te piden pegar una llave en el chat, explica que va en el `.env` de Hermes o en el
   panel de Coolify.
7. **Marca blanca:** nada que escriba el vigía en contenido público puede decir o insinuar que Alegra es
   dueña del portal.
8. **Cada falla se convierte en una regla o en una prueba**, anotada en `docs/decisiones.md`.

## Procedimientos

### Trabajar una tarea del plan

1. Actualiza la copia del repositorio (`git pull --ff-only`) y lee `docs/ESTADO.md` y la tarea en
   `docs/PLAN.md`.
2. Crea una rama `vigia/<tarea>` antes de editar.
3. Haz la tarea y corre `python -m pytest -q vigia/tests`.
4. Actualiza `docs/ESTADO.md` (qué cambió y qué sigue) y, si tomaste una decisión, `docs/decisiones.md`.
5. **Haz commit y push de la rama y abre el PR.** Lo que se edite en la copia del contenedor y no se suba
   se pierde la próxima vez que el repositorio se actualice.
6. Reporta en el chat: qué hiciste, el enlace del PR y qué quedó pendiente.

### Regenerar el inventario

Desde `vigia/inventario/` (tarda 10–15 minutos: son ~343 posts y cada uno se pide dos veces con `curl`;
se regenera para los cuatro vigías a la vez):

```bash
python descargar.py && python units.py && python extraer.py && python comparar_alegra.py && python armar.py
cp -r salida/paises/* ../paises/ && cp salida/sin-pais.json ..
```

- Lánzalo en segundo plano con aviso al terminar (`terminal(background=True, notify=True)`): en primer
  plano se pasa del tiempo máximo y pierdes la progresión.
- `raw/` y `salida/` están en `vigia/.gitignore`: nunca los subas. Copia a `paises/` solo cuando el
  informe de diferencias ya esté escrito.

Compara los conteos de cada vigía con la tabla de `docs/ESTADO.md` y explica las diferencias antes de
subir nada.

### Instalar y verificar en este equipo (tarea T1)

Sirve para la copia local de Sharon en Windows; el contenedor de Coolify se instala con los comandos de
las instrucciones (pip + `playwright install chromium` + `install-deps`).

```bash
REPO="C:/Users/Alegra/Desktop/Insumos para Programa de Contabilidad/programascontabilidad-studio"
cd "$REPO" && git pull --ff-only && git checkout -b vigia/inicio
cp -r <ruta del paquete>/vigia ./vigia          # el zip trae la carpeta vigia/ ya armada
python -m venv ~/.pdc/venv-vigia
~/.pdc/venv-vigia/Scripts/python.exe -m pip install -r "C:/Users/Alegra/Desktop/.../vigia/requirements.txt"
~/.pdc/venv-vigia/Scripts/python.exe -m pytest -q vigia/tests    # esperado: 36 pruebas en verde
```

- Usa un venv aparte (`~/.pdc/venv-vigia`), no el python de Hermes: playwright, lxml y bs4 quedan ahí y
  el agente diario no se ensucia. Es el mismo patrón de `~/.pdc/mcp-gsc/.venv`.
- **Al pip pásale la ruta en estilo Windows (`C:/Users/...`)**, no `/c/Users/...`: pip es un binario
  nativo y MSYS no traduce la ruta, así que falla con «Could not open requirements file».
- Chromium: compruébalo lanzando `sync_playwright().chromium.launch()`. Se instala **una vez** en la
  imagen del contenedor o en el comando posterior al despliegue, con `PLAYWRIGHT_BROWSERS_PATH` en una
  carpeta permanente (`docs/CONTENEDOR.md`, DEC-010): nunca en cada corrida y nunca dentro de una tarea
  del plan. En la copia local de Sharon quedó instalado en `%LOCALAPPDATA%\ms-playwright`.
- Skill: copia `vigia/hermes-skill/vigia-precios` a `$HERMES_HOME/skills/pdc/` (en Windows
  `C:\Users\Alegra\AppData\Local\hermes\skills\pdc\`) y confirma con `skills_list(category='pdc')`;
  en el contenedor hace falta `/reload-skills`.
- Publica con `gh pr create` (corre `gh auth status` antes) y confirma que `git status --short` solo
  muestra `?? vigia/`: si aparece `inventario/raw` o `salida`, el `.gitignore` del paquete no se copió.

### Correr un vigía (cuando exista `vigia/correr.py`)

```bash
python -m vigia.correr --pais col     # mex | col | cri | dom
```

El modo sale de `VIGIA_MODO_<VIGÍA>` (`ensayo`, `aplicar` o `pausa`). Nunca cambies esa variable sin
que una persona lo pida.

### Explicar un aviso del vigía

Busca la corrida en `vigia/paises/<vigía>/lecturas/<fecha>/` y el registro en
`vigia/paises/<vigía>/registro-precios.json`. Responde con
la página, la cifra anterior, la leída y la regla que decidió el resultado.

## Errores que ya pasaron

- **Cloudflare bloquea el agente de Python** en programascontabilidad.com y alegra.com: descarga con
  `curl` (como hace `descargar.py`).
- **La corrida programada no va en el programador de Hermes.** En elmejorsoftware.mx las tareas del
  programador no veían las llaves ni el repositorio actualizado. Cada vigía corre los días 1 y 16 como
  tarea programada de Coolify dentro del contenedor (o GitHub Actions si no hay Chromium).
- **Google Chat no es un destino de entrega de Hermes.** Los avisos los manda el código con `gchat.py`,
  no la entrega del cron.
- **El HTML servido puede venir viejo aunque la API ya cambió** (caché): se verifica en la página pública.
- **Varias URL de posts redirigen** (301): se corrige el post de destino, no el de origen.
- **Dos posts tienen mal el metadato de país** (2157 es de México y 2323 de Perú, marcados como
  Colombia): por eso el metadato es el último nivel, no el primero.
- **En República Dominicana y Costa Rica la moneda sola no dice el país**: Alegra y varias marcas cobran
  en USD.
- **Los precios no siempre llevan símbolo.** Alegra Costa Rica y Alegra RD escriben «USD 26.10 / mes»:
  un patrón que solo busque `$`, `US$`, `RD$` o `₡` devuelve cero cifras y la fuente parece «no publica».
  Acepta siempre el código de moneda (`USD`, `COP`, `CRC`, `MXN`, `DOP`) delante del número.
- **En Alegra la fila de precio trae cuatro cifras**: mensual de lista, mensual con pago anual, facturado
  anual y el ahorro. Lee solo `span.cards-simple-price-and-period`; si tomas la fila entera, el facturado
  anual ($161.100) se cuela como precio mensual ($17.900).
- **El webhook de Chat no se llama igual en las dos partes.** Esta skill declara `GCHAT_WEBHOOK_URL`, pero
  el agente diario usa `PDC_CHAT_WEBHOOK_URL` (`~/.pdc/chat.env`, `scripts/corrida_completa.py`) y el
  repositorio no trae un `gchat.py` suelto. Al hacer T7 lee el nombre que exista en el entorno y deja el
  alias escrito, en vez de declarar una variable nueva que nadie llena.
- **Esta skill es una copia del repositorio.** Si la editas desde Hermes, copia el mismo cambio a
  `vigia/hermes-skill/vigia-precios/SKILL.md` y súbelo en el PR: la próxima instalación sobrescribe la
  copia local.
