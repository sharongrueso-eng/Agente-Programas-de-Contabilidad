# Vigía de precios — guía paso a paso

Agente de Programas de Contabilidad (programascontabilidad.com). Adaptada de la guía de elmejorsoftware.mx el 18-nov-2026. Este archivo es la versión viva de la guía; el estado de avance está en `ESTADO.md`.

> **Actualización 18-nov-2026 (DEC-007 y DEC-008):** el vigía se divide en cuatro, uno por país (MEX, COL, CRI y DOM), con un solo código. Donde la guía dice «el vigía», aplica a cada uno. El país de cada cifra se reconoce por las señales del país en el texto (`senales-pais.json`), no por la URL.

## La idea en una línea

> **El vigía lee, el código compara y valida, y solo se aplica el cambio que se puede explicar; todo lo demás se avisa.** Ningún precio cambia porque «el modelo lo leyó»: cambia porque pasó controles fijos (moneda, país, doble lectura, sin campaña activa) y porque el cambio quedó verificado en la página pública.

Es la misma lógica del sistema de elmejorsoftware.mx: reglas objetivas en código, juicio en un modelo solo donde haga falta y decisiones en una persona. La diferencia es que en PdC el contenido vive en WordPress, se publica para cuatro países y la publicación ya es 100 % autónoma (decisión del 5 de noviembre). Eso cambia varios pasos, y esta guía los ajusta.

## Qué cambia frente a elmejorsoftware.mx

| **Tema**                | **elmejorsoftware.mx**                                            | **PdC**                                                                                       | **Qué implica para el vigía**                                                                    |
|-------------------------|-------------------------------------------------------------------|-----------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------|
| Dónde viven los precios | Sanity: cada producto es una ficha con campos de planes y precios | WordPress: las cifras están dentro del HTML de reseñas, comparativas y «mejores herramientas» | Antes de automatizar necesitas un mapa de en qué post y en qué frase aparece cada cifra (paso 1) |
| Mercados                | Solo México                                                       | Colombia, México, República Dominicana y Costa Rica                                           | Cada fuente es marca + producto + país, con su moneda esperada                                   |
| Precio según IP         | Solo Odoo (se lee a mano desde México)                            | Probable en varias marcas, y el runner de GitHub sale desde EE. UU.                           | Regla de moneda obligatoria y un modo de lectura por fuente (paso 3)                             |
| Autonomía               | Noindex y veto de 48 horas                                        | Publicación autónoma, sin veto previo                                                         | El vigía aplica solo, pero arranca con dos corridas en modo ensayo (paso 10)                     |
| Precios de Alegra       | En el registro de precios                                         | Tablas manuales en los anexos E y F de la skill prog-cont-blog                                | Conviene que Alegra sea la primera fuente: es la más fácil y la que más se repite                |

## Las piezas del vigía

Los nombres de archivo son una sugerencia: acomódalos a la estructura que ya tiene el repositorio Agente-Programas-de-Contabilidad. Lo importante es que todo viva en el repositorio y nada en un computador.

| **Pieza**           | **Para qué sirve**                                                                     | **Dónde (sugerido)**                      |
|---------------------|----------------------------------------------------------------------------------------|-------------------------------------------|
| Fuentes             | Qué páginas oficiales se leen, desde qué país y con qué receta                         | vigia/fuentes.json                        |
| Registro de precios | Cada cifra vigente con su fuente, moneda, fecha de consulta y fórmula                  | vigia/registro-precios.json               |
| Ubicaciones         | En qué post, URL y frase aparece cada cifra del registro                               | vigia/ubicaciones.json                    |
| Reglas fijas        | Lo que bloquea o solo avisa, escrito para personas y luego como código                 | vigia/REGLAS-VIGIA.md + vigia/reglas.json |
| Lector              | Abre cada página con Chromium (Playwright), lee el DOM dos veces y guarda la evidencia | vigia/lector.py                           |
| Comparador          | Clasifica cada lectura contra el registro                                              | vigia/comparador.py                       |
| Actualizador        | Cambia posts, registro y fechas de consulta, todo o nada                               | vigia/actualizador.py                     |
| Capturas            | Renueva las capturas de precios viejas o desactualizadas                               | vigia/capturas.py                         |
| Avisos              | Un resumen por corrida en Google Chat, con tres colores                                | Reutiliza gchat.py del agente             |
| Programación        | Corre solo los días 1 y 16                                                             | .github/workflows/vigia-precios.yml       |
| Pruebas             | Un caso por cada error que ya pasó                                                     | tests/test_vigia_precios.py               |
| Decisiones          | Qué pasó, por qué y qué cambió (DEC-001 en adelante)                                   | decisiones.md                             |

## Paso a paso

### Paso 0. Decide el alcance y las reglas antes de escribir código

Escribe en vigia/REGLAS-VIGIA.md cuatro cosas. Cada regla que bloquee se convertirá después en código.

1.  **Qué se vigila:** las marcas y productos que tienen reseña o comparativa publicada, por país, más Alegra en los cuatro países.

2.  **Qué cuenta como cambio:** precio de lista, nombre de plan, plan nuevo o retirado, periodo (mensual/anual), moneda, impuesto incluido o aparte y límites que la pieza cite (usuarios, facturas, ingresos).

3.  **Qué no cuenta como cambio:** promociones de temporada (Black Friday, Cyber Monday, Buen Fin, fin de año), el descuento permanente por pago anual (por ejemplo, el 25 % de Alegra Colombia) y diferencias de formato («\$49.900» frente a «\$ 49.900»).

4.  **Qué hace solo y qué solo avisa:** aplica solo cuando cambia la cifra de un plan que ya existe, del mismo producto y en el mismo mercado. Avisa sin tocar nada cuando hay plan nuevo o retirado, campaña activa, lectura dudosa o cambio de mercado.

> **Listo cuando:** el archivo de reglas existe en el repositorio y lo aprobó quien responde por PdC.

### Paso 1. Haz el inventario de lo que hoy tiene WordPress

El vigía no puede actualizar lo que no sabe dónde está. Este paso arma el mapa.

1.  Lista las reseñas (categoría 15), las comparativas (16) y las piezas de «mejores herramientas». Con el MCP usa ewpa/get-posts (devuelve máximo 10 por consulta, así que busca por marca) o la API REST con el token: GET /wp-json/wp/v2/posts?categories=15&per_page=100&context=edit.

2.  De cada post extrae las frases con cifras, con la expresión del anexo G de la skill (\[^.\]{0,190}\\\s?\[\d.,\]+\[^.\]{0,190}\\), y agrega la búsqueda de ₡, US\$ y RD\$, que esa expresión no cubre.

3.  Etiqueta cada cifra con país del post, marca, producto, plan y periodo. Lo que no puedas atribuir con certeza va a una lista aparte de pendientes.

4.  Guarda el resultado en vigia/ubicaciones.json y saca de ahí la lista de pares marca + país para vigia/fuentes.json.

```json
{
  "post_id": 1234,
  "url": "https://programascontabilidad.com/...",
  "pais": "CO",
  "clave_registro": "alegra|facturacion|CO|pyme",
  "campo": "mensual",
  "texto_actual": "$49.900",
  "contexto": "El plan Pyme cuesta $49.900 al mes..."
}
```

Si la auditoría del portal (auditoria.json, 343 posts) ya tiene parte de esta información, úsala como punto de partida, pero vuelve a leer el contenido actual de cada post: la auditoría es una foto vieja.

> **Listo cuando:** cada cifra de precio publicada tiene una clave de registro o está en la lista de pendientes, y sabes cuántas marcas por país vas a vigilar.

### Paso 2. Arma el registro de precios (la línea base)

El registro es la única fuente de verdad. Cada edición cita el registro, nunca el post anterior, porque los posts viejos son justo lo que hay que corregir.

```json
{
  "clave": "alegra|facturacion|CO|pyme",
  "marca": "Alegra", "producto": "Facturación electrónica",
  "pais": "CO", "plan": "Pyme", "moneda": "COP",
  "impuesto": "no especificado",
  "mensual": 49900,
  "anual_equivalente_mes": 37425,
  "anual_facturado": 449100,
  "formulas": { "anual_facturado": "12 * anual_equivalente_mes" },
  "fuente": "https://www.alegra.com/colombia/precios/",
  "fecha_consulta": "2026-10-22",
  "evidencia": "dom",
  "campana_activa": null
}
```

El ejemplo usa la tabla del anexo F de la skill (Alegra Colombia, leída el 22 de octubre). Para la línea base:

- Haz la primera lectura con el lector (paso 4) y que una persona la compare contra cada página antes de darla por buena.

- **Cuidado con la fecha:** entre hoy y comienzos de diciembre hay campañas de Black Friday y Cyber Monday. Si una página muestra campaña, registra el precio de lista (el tachado) y marca campana_activa; nunca el precio promocional.

- Guarda las fórmulas (por ejemplo, el total anual es 12 veces el mensual con pago anual) para que el código compruebe las cifras derivadas en lugar de copiarlas.

- Si una marca no publica precios (cotización o «contacta a ventas»), el registro dice «no publica», nunca «no tiene».

> **Listo cuando:** el registro cubre todas las claves del inventario y cada cifra tiene fuente y fecha.

### Paso 3. Define cada fuente y cómo se lee desde su país

Este es el paso que más pesa en PdC. El runner de GitHub Actions sale desde EE. UU.; si una marca muestra la moneda según la IP del visitante, el vigía leerá dólares y creerá que el precio cambió.

```json
{
  "id": "alegra-co-precios",
  "marca": "Alegra", "pais": "CO",
  "url": "https://www.alegra.com/colombia/precios/",
  "moneda_esperada": "COP",
  "senales_pais": ["DIAN", "IVA"],
  "modo_lectura": "ruta_pais",
  "receta": { "contenedor": "[class*='pricing-cards-']" },
  "claves": ["alegra|facturacion|CO|pyme", "..."]
}
```

| **Modo de lectura** | **Cuándo aplica**                                          | **Cómo se lee**                                                                                                                                                                                                      |
|---------------------|------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ruta_pais           | La URL ya trae el país (como alegra.com/colombia/precios/) | Directo, y se confirma moneda y señales del país                                                                                                                                                                     |
| selector_pais       | La página elige el país con cookie, parámetro o selector   | Playwright fija la cookie o el parámetro antes de leer                                                                                                                                                               |
| ip                  | La moneda depende de la IP del visitante (el caso Odoo)    | Opción A: proxy con salida en ese país (tiene costo mensual y un secreto por país). Opción B: aviso 🟡 los días 1 y 16 para que alguien del país guarde el HTML de la página en el repositorio y el vigía lo procese |
| no_publica          | Sin precio público                                         | Se comprueba que siga sin publicar; si aparece un precio, aviso 🟡                                                                                                                                                   |

#### La regla de moneda (bloquea siempre)

- La moneda leída debe ser la moneda_esperada de la fuente y debe aparecer al menos una señal del país (impuesto, ente fiscal, dominio). Si no, es **lectura dudosa** y no se toca nada.

- **Nunca se convierte la moneda** para que la tabla cuadre: eso es fabricar datos (regla de la skill).

- **Trampa de República Dominicana:** Alegra RD y varias marcas cobran en USD, y un runner en EE. UU. también ve USD. Ahí la moneda no basta: exige señales como ITBIS, DGII o RD\$.

- La moneda esperada se fija con la primera lectura verificada por una persona, no se supone por país: una marca puede cobrar en USD en Costa Rica.

#### Números según el país

Cada país escribe las cifras distinto: \$49.900 en Colombia (punto de miles), \$1,234.50 en México (coma de miles), ₡12 500 en Costa Rica (espacio) y US\$ 25 o RD\$ 1,500 en República Dominicana. El lector convierte cada cifra con la convención de su fuente, y cada formato tiene su prueba.

> **Listo cuando:** cada fuente tiene modo de lectura, moneda esperada y señales de país, y las fuentes de modo ip tienen definida la opción A o B.

### Paso 4. Construye el lector (código, no modelo)

1.  Python + Playwright con Chromium, ventana de 1440 px (la misma de las capturas de la skill), idioma y zona horaria del país.

2.  **Los precios salen del DOM o del HTML, nunca de una captura** (regla de la skill: una cifra pequeña se confunde).

3.  **Lee dos veces** cada página, en contextos de navegador separados y con unos minutos de diferencia. Si las dos lecturas no coinciden, es lectura dudosa.

4.  Guarda cada lectura con fecha en vigia/lecturas/AAAA-MM-DD/\<fuente\>.json, junto con el HTML de la página como evidencia.

5.  **Detecta campañas** antes de entregar la lectura: insignias («Black Friday», «Cyber», «Buen Fin», «Navidad»), cuenta regresiva, precio tachado con vigencia o un «% OFF» con fecha. El descuento permanente por pago anual no cuenta como campaña.

6.  Si la receta no encuentra nada (la marca rediseñó la página), el aviso lo dice con el nombre de la página. Nunca se calla.

7.  Lee a ritmo bajo: una página a la vez y una pausa entre lecturas. Son dos corridas al mes sobre páginas públicas; no hace falta más.

Un modelo (por la llave única de LiteLLM) solo entra para proponer una receta nueva cuando una se rompe. Nunca decide un precio.

> **Listo cuando:** el lector corre sobre todas las fuentes, guarda la evidencia y marca bien una página con campaña y una con la moneda equivocada (pruébalo con HTML guardado).

### Paso 5. Construye el comparador (las puertas fijas)

| **Resultado**                     | **Condición**                                                          | **Qué hace el vigía**                                                                          |
|-----------------------------------|------------------------------------------------------------------------|------------------------------------------------------------------------------------------------|
| Sin cambios                       | Todo coincide con el registro                                          | Nada. Lo dice una sola vez en el resumen 🟢                                                    |
| Cambio de precio explicable       | Mismo producto, plan y moneda; las dos lecturas coinciden; sin campaña | Actualiza registro, posts y fechas de consulta (paso 6) y avisa 🟢 con antes, después y URLs   |
| Plan nuevo, retirado o renombrado | La estructura de planes cambió                                         | No toca los posts. Aviso 🟡 para decidir                                                       |
| Campaña activa                    | Insignia o vigencia en la página                                       | No toca nada y conserva la línea base. Un solo aviso 🟡 por página                             |
| Lectura dudosa                    | Moneda o país no coinciden, lecturas distintas o receta vacía          | No toca nada. Aviso 🟡 con el nombre de la página                                              |
| Cambio de mercado                 | Dominio, moneda, idioma o norma fiscal de otro país                    | No toca nada. Aviso 🟡 con prioridad: la pieza se reescribe con otro ángulo (skill §1, paso 3) |
| Falla del proceso                 | Error de código, de red o de WordPress                                 | Aviso 🔴                                                                                       |

> **Listo cuando:** cada uno de los siete resultados tiene al menos una prueba en tests/test_vigia_precios.py.

### Paso 6. Construye el actualizador todo o nada (WordPress)

Es el anexo G de la skill convertido en código. Por cada cambio aprobado por el comparador:

1.  Busca en ubicaciones.json los posts con la cifra vieja y haz además una búsqueda de texto completo para encontrar menciones que el inventario no tenga.

2.  Guarda el content.raw de cada post afectado como respaldo de la corrida.

3.  **Dry-run con conteos:** pares (viejo, nuevo) por post, y cada par debe aparecer al menos una vez. Un cero detiene todo: la cadena no es la que crees.

4.  Si los valores se pisan entre sí (el nuevo de un plan es el viejo de otro), usa marcadores (@@A@@, @@B@@) y cambia en dos pasadas.

5.  Reemplaza solo el texto, no las etiquetas que lo envuelven, y actualiza también la fecha de consulta de la tabla.

6.  Cuenta aperturas y cierres de cada bloque Gutenberg (wp:list, wp:list-item, wp:table): deben coincidir.

7.  Sube el contenido completo con ewpa/update-post (no con ewpa/search-replace, que falla con tildes, emojis y bloques anidados).

8.  **Verifica en la página pública**, no solo en la API. Si el HTML servido sigue viejo, ewpa/clear-cache con el post_id y vuelve a comprobar.

9.  Si cualquier paso falla en cualquier post, **restaura todos los posts de la corrida** desde el respaldo y avisa 🔴.

10. Solo cuando todo quedó verificado, actualiza el registro y deja el cambio en el repositorio (commit).

- **Auditoría de residuos:** busca las cifras viejas en todo el portal y revisa cada acierto. Algunos son legítimos (el precio de un competidor que casualmente coincide con la cifra vieja de Alegra).

- El vigía solo cambia cifras y fechas. No agrega texto nuevo a los posts, así que no altera la regla de marca blanca del portal.

- **A futuro:** si el inventario muestra la misma tabla de precios repetida en muchos posts, considera pasarla a un patrón sincronizado de WordPress (/wp/v2/blocks): se edita una vez y cambia en todos. Antes confirma que el token o el MCP pueden editarlo.

> **Listo cuando:** una prueba con un post de borrador cambia la cifra, la verifica en la página y, si fuerzas un error, deja todo como estaba.

### Paso 7. Renueva las capturas (segunda etapa)

- Vuelve a tomar las capturas de precios con más de 40 días o cuyo precio cambió, con Chrome headless a 1440 px.

- Antes de reemplazar, comprueba que la imagen muestre el precio del registro (con un modelo de visión por LiteLLM o con OCR). Si no coincide, conserva la anterior y avisa 🟡.

- Sube la imagen a medios, cambia la URL en todos los posts y conserva el texto alternativo («\<Marca\> precios»).

- **Una captura nunca frena una actualización de precios:** lo que no es esencial no detiene lo esencial.

> **Listo cuando:** una captura renovada aparece en todos los posts que la usaban, con su alt.

### Paso 8. Conecta los avisos de Google Chat

Usa el mismo espacio del agente diario y el gchat.py que ya existe, con el webhook en el secreto GCHAT_WEBHOOK_URL.

| **Color**   | **Significa**       | **Ejemplos del vigía**                                                                                        |
|-------------|---------------------|---------------------------------------------------------------------------------------------------------------|
| 🟢 Verde    | Informativo         | «Vigía de precios: sin cambios», «3 precios actualizados en 7 posts» con antes, después y URLs                |
| 🟡 Amarillo | Conviene revisar    | Campaña activa, lectura dudosa, plan nuevo o retirado, cambio de mercado, lectura manual pendiente en un país |
| 🔴 Rojo     | Falló o se restauró | Error del proceso, actualización revertida, el workflow no pudo correr                                        |

- Un mensaje de resumen por corrida y cada problema una sola vez por día. Las pestañas de una misma página se agrupan en un solo aviso (lección del 13-nov en elmejorsoftware.mx: una campaña generó seis avisos que listaban 16 piezas cada uno).

- Arranca por lo que la persona tiene que hacer, usa enlaces completos y no pases de 4.000 caracteres.

- Confirma el envío por el name que devuelve la API de Chat (spaces/.../messages/...), no por el código 200.

> **Listo cuando:** una corrida de prueba deja en el espacio un resumen 🟢 y un aviso 🟡 simulado.

### Paso 9. Prográmalo en GitHub Actions

> **Actualización 18-nov-2026 (DEC-005):** el vigía vive en Hermes. La corrida de los días 1 y 16 es una tarea programada de Coolify dentro del contenedor de Hermes, que ve las variables del entorno. GitHub Actions, como se describe abajo, queda como alternativa si el contenedor no puede tener Chromium. En ningún caso va en el cron de Hermes.

El repositorio ya está en GitHub y nada debe vivir en tu equipo, así que el vigía corre en GitHub Actions, como en elmejorsoftware.mx. No lo pongas en el programador de Hermes: filtra las credenciales a propósito y las tareas no ven las llaves.

```yaml
name: Vigía de precios
on:
  schedule:
    - cron: "0 12 1,16 * *"   # días 1 y 16, 7:00 de Bogotá (12:00 UTC)
  workflow_dispatch:
    inputs:
      modo:
        description: "ensayo o aplicar"
        default: "ensayo"
permissions:
  contents: write
concurrency:
  group: vigia-precios
  cancel-in-progress: false
jobs:
  vigia:
    runs-on: ubuntu-latest
    timeout-minutes: 45
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r vigia/requirements.txt
      - run: python -m playwright install --with-deps chromium
      - run: python -m vigia.correr --modo "${{ inputs.modo || vars.VIGIA_MODO }}"
        env:
          WP_API_TOKEN: ${{ secrets.WP_API_TOKEN }}
          GCHAT_WEBHOOK_URL: ${{ secrets.GCHAT_WEBHOOK_URL }}
      - name: Guardar registro y lecturas
        run: |
          git config user.name "vigia-precios"
          git config user.email "vigia-precios@users.noreply.github.com"
          git add vigia/registro-precios.json vigia/lecturas
          git diff --cached --quiet || git commit -m "Vigía de precios: lectura $(date +%F)"
          git push
```

- **Secretos (solo nombres, los valores van en GitHub → Settings → Secrets):** el token de WordPress con el mismo nombre que usa el agente, GCHAT_WEBHOOK_URL, OPENAI_BASE_URL y OPENAI_API_KEY de LiteLLM (solo si usas modelo para recetas o capturas) y uno por país si eliges proxy.

- La variable de repositorio VIGIA_MODO (ensayo, aplicar o pausa) te deja cambiar de etapa o pausar sin tocar código.

- concurrency es el candado: dos corridas nunca se pisan.

- Agrega un segundo workflow que, en cada cambio al repositorio, compile todo el código (python -m compileall) y corra las pruebas, y avise 🔴 si falla. En elmejorsoftware.mx un script con una línea mal escrita falló en silencio.

- El horario de GitHub puede retrasarse unos minutos; para el vigía no importa. Revisa en tu plan cuántos minutos de Actions incluye el repositorio privado: dos corridas al mes consumen poco.

> **Listo cuando:** el workflow corre a mano en modo ensayo, deja el commit de lecturas y el resumen en Chat.

### Paso 10. Suelta el control por etapas

El agente diario ya publica sin veto, pero un precio mal leído en 30 posts es el error más caro del portal. Por eso el vigía gana autonomía por etapas:

| **Etapa**                   | **Qué hace el vigía**                                          | **Pasa a la siguiente cuando**                                                             |
|-----------------------------|----------------------------------------------------------------|--------------------------------------------------------------------------------------------|
| 1\. Ensayo (corridas 1 y 2) | Lee, compara y avisa lo que cambiaría, sin tocar WordPress     | Una persona comprobó cada propuesta contra la página y no hubo falsas alarmas sin explicar |
| 2\. Aplicar precios         | Aplica solo los cambios de precio explicables; lo demás, aviso | Dos corridas sin restauraciones ni residuos                                                |
| 3\. Capturas                | Suma la renovación automática de capturas                      | Etapa final                                                                                |

Cada falsa alarma o error se convierte en una regla nueva o en una prueba, y queda anotado en decisiones.md.

### Paso 11. Conéctalo con el agente diario

- **Productor:** toma los precios de competidores del registro si la fecha de consulta tiene 16 días o menos. Si falta un precio, lo lee con el mismo lector y lo registra antes de escribir.

- **Validador del agente diario:** bloquea cualquier pieza con un precio que no esté en el registro o que no se pueda atribuir con certeza. Es el control fijo que justifica publicar sin veto.

- **Corrector:** solo puede usar cifras que ya estén en la pieza o en el registro, copiadas exactas. En elmejorsoftware.mx, prohibirle tocar cifras bloqueaba arreglos válidos.

- **Skill prog-cont-blog:** los anexos E y F pasan a apuntar al registro en lugar de mantener tablas propias. Dos fuentes de precios terminan contradiciéndose.

### Paso 12. Documenta

- decisiones.md con número por decisión (DEC-001…): qué pasó, por qué y qué cambió.

- En el runbook: cómo pausar (VIGIA_MODO=pausa o desactivar el workflow), cómo correr a mano, dónde ver la última lectura y cómo restaurar una corrida.

- Si el equipo replica esto en otro portal, que la wiki apunte al repositorio como documento vivo.

## Errores ya pagados y cómo se evitan aquí

| **Qué pasó**                                            | **Dónde**                     | **Cómo lo evita el vigía de PdC**                                 |
|---------------------------------------------------------|-------------------------------|-------------------------------------------------------------------|
| Los precios cambiaban según el país del visitante       | elmejorsoftware.mx (Odoo)     | Modo de lectura por fuente y regla de moneda con señales del país |
| Una campaña de temporada generó avisos masivos          | elmejorsoftware.mx, 13-nov    | Campaña = no tocar, conservar la línea base y un aviso por página |
| Un script falló en silencio                             | elmejorsoftware.mx            | Workflow de compilación y pruebas en cada cambio, con aviso 🔴    |
| Prohibir cambiar cifras bloqueaba arreglos válidos      | elmejorsoftware.mx            | El corrector usa cifras del registro, copiadas exactas            |
| Lo no esencial detenía la publicación                   | elmejorsoftware.mx (portadas) | Una captura fallida nunca frena la actualización de precios       |
| El programador del agente no veía las llaves            | elmejorsoftware.mx            | Corre en GitHub Actions, no en el programador de Hermes           |
| Posts con tarifas por debajo del precio real            | PdC (skill, §1)               | Registro único y auditoría de residuos en cada cambio             |
| El HTML servido traía la copia vieja                    | PdC (anexo G)                 | Verificación en la página pública y ewpa/clear-cache              |
| Valores que se pisaban al reemplazar                    | PdC (anexo G)                 | Marcadores en dos pasadas                                         |
| Bloques Gutenberg abiertos que se tragaban el siguiente | PdC (anexo G)                 | Conteo de aperturas y cierres antes de subir                      |

## Lo que te toca decidir

1.  **Fuentes que dependen de la IP:** proxy por país (más automático, con costo mensual) o lectura manual por alguien en cada país (sin costo, con aviso los días 1 y 16).

2.  **Quién hace las lecturas manuales** en Colombia, México, República Dominicana y Costa Rica, si eliges esa opción.

3.  **Si Alegra entra como fuente.** Lo recomiendo: es la cifra que más se repite en el portal y la más fácil de leer.

4.  **Si las tablas repetidas pasan a patrones sincronizados** de WordPress, una vez veas el inventario.

## Fuentes

- Guía para replicar este sistema en tu proyecto: https://wiki.alegra.com/doc/guia-para-replicar-este-sistema-en-tu-proyecto-2693yRbpxN

- Fichas, precios y vigías — elmejorsoftware.mx: https://wiki.alegra.com/doc/fichas-precios-y-vigias-elmejorsoftwaremx-EkHdYhTwma

- Flujos automáticos y avisos — elmejorsoftware.mx: https://wiki.alegra.com/doc/flujos-automaticos-y-avisos-elmejorsoftwaremx-yHYp2XVXxp

- Arquitectura y operación — elmejorsoftware.mx: https://wiki.alegra.com/doc/arquitectura-y-operacion-elmejorsoftwaremx-Z63wHorKEl

Skill prog-cont-blog: secciones 1, 7 y 7b y anexos E, F y G (precios, refresco en lote y reportes a Google Chat).
