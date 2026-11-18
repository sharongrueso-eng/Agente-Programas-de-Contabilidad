# Estado de los vigías de precios

Actualizado: 18-nov-2026.

Hay cuatro vigías, uno por país (MEX, COL, CRI y DOM), con un solo código. El país de cada cifra se
reconoce por las señales propias del país (`senales-pais.json`), no por la URL.

| Paso de la guía | Estado |
|---|---|
| 0. Reglas | Aprobadas el 18-nov-2026 por Sharon Grueso (`REGLAS-VIGIA.md`) |
| 1. Inventario | Hecho (v2, por país). Falta revisar la confianza media y los pendientes |
| 2. Registro de precios | Sin empezar |
| 3. Fuentes | Los cuatro países: prioridad 1 verificada (T2). Queda prioridad 2 y 3 |
| 4 a 12 | Sin empezar |

## T1 · Entorno verificado (18-nov-2026)

Corrido en la copia local (Windows). El contenedor de Coolify se verifica aparte: ver
`docs/CONTENEDOR.md`.

- **36 pruebas en verde** en `vigia/tests`, con Python 3.14.9 y un venv aparte (`~/.pdc/venv-vigia`)
  con lo que pide `requirements.txt` (playwright, beautifulsoup4, lxml, pytest).
- **Chromium 159.0.8154.6** (Playwright 1.65.2) abre `https://www.alegra.com/colombia/precios/` a
  1440 px, ve DIAN y lee las cifras en COP ($37.425, $449.100…).
- **El inventario se reproduce.** Regenerado el 18-nov con los 343 posts y el recurso: 1.120
  ubicaciones (COL 508, MEX 299, DOM 186, CRI 127), 64 fuentes (MEX 19, CRI 16, COL 15, DOM 14), 41
  rangos de mercado, 33 cifras fuera de alcance (PE 22, PA 7, ES 4) y las mismas 85 cifras de Alegra
  que no coinciden con su página en 50 posts (MEX 11 en 7, COL 35 en 15, CRI 13 en 10, DOM 26 en 18).
- **Una sola diferencia: sin país son 15, no 16.** Es «$100 mil dólares» del post 16 (*Pequeñas
  empresas, segmento que crece en América Latina*): hoy queda con país CO y confianza baja por las
  señales del propio post («Colombia» 4 frente a «Perú» 2), y la foto del inventario v2 la había dejado
  sin país. Con la regla aprobada (≥3 puntos y el doble del segundo) el resultado correcto es CO, así
  que esa cifra se mueve a los pendientes de COL: 39 en vez de 38, y el total 150 en vez de 149.
- Los archivos regenerados **no se subieron**: T1 solo pide el informe. Se subirán cuando se revise la
  confianza media.

## T2 · Fuentes de prioridad 1 de Colombia (18-nov-2026)

Las cinco fuentes de prioridad 1 de COL quedaron con URL verificada, moneda esperada, señales del país y
modo de lectura. El HTML de cada una está en `paises/col/lecturas/2026-11-18/` como evidencia.

| Fuente | Cifras leídas | Moneda | Modo | Receta |
|---|---|---|---|---|
| Alegra | 106 | COP | ruta_pais | `[id^='pricing-cards-']` (la que ya usa el agente) |
| Siigo | 71 | COP | ruta_pais | se fija en T4 (clases CSS-module con hash) |
| Vendty | 8 | COP | ruta_pais | se fija en T4 (columnas `div.dmRespCol.large-3`) |
| Loggro | 142 | COP | ruta_pais | se fija en T4 (tarjetas y tablas, con bloques ocultos) |
| World Office | 2 | COP | por_definir | la home no tiene tabla de planes |

- **Ninguna fuente de prioridad 1 de COL depende de la IP.** Los precios leídos desde este equipo y los
  leídos por un servicio externo (otra salida de red) coinciden: son dominios o rutas de país, no
  selectores de moneda. No hace falta nadie leyendo a mano en Colombia.
- **World Office** solo muestra $220.000 en una sección de contadores de la home. Buscar `/planes` en
  T4; si no publica, queda `no_publica`, nunca «no tiene».
- **Siigo**: el -25 %/-30 % es el descuento por pago anual («descuento aplica para cliente nuevo»), no
  campaña. El título de la página dice «Ecomm Mes - Beneficios Exclusivos Online»: si aparece insignia de
  campaña, el lector tiene que marcarla.
- **Loggro** publica 142 cifras y muchas están duplicadas en bloques `.hidden`: el lector debe leer solo
  lo visible o contará dos veces.
- **Hallazgo que toca a MEX**: `aspel.com.mx` ya no es Aspel, redirige a `siigo.com/mx/` (Siigo compró
  Aspel). Hay que decidir si sigue como fuente propia o se trata como Siigo.

## T2 · Fuentes de prioridad 1 de México (18-nov-2026)

| Fuente | Cifras visibles | Moneda | Modo | Qué hay que saber |
|---|---|---|---|---|
| Alegra | 76 | MXN | ruta_pais | Mensual con pago anual ($186,75) y facturado anual ($2,241) |
| Miskuentas | 19 | MXN | ruta_pais | `/tienda/` redirige; la página con precios vive en `/contabilidad/` |
| Facturama | 4 | MXN | ruta_pais | Paquetes prepago de folios ($55 a $1.650): pago único por documento |
| Siigo (ex Aspel) | 9 | MXN | por_definir | `aspel.com.mx` redirige a `siigo.com/mx/` |
| CONTPAQi | 0 | MXN | no_publica | Probadas `/`, `/productos` y `/tienda` (404): cotiza por socios |

- **Ninguna depende de la IP**: son dominios o rutas de país, igual que en Colombia.
- **La receta de Colombia no se hereda.** En México, `pricing-cards-af/-pos/-contabilidad/-contador`
  son anclas del menú, no ids de contenedor: `[id^='pricing-cards-']` devuelve 0 elementos. La receta de
  Alegra México se fija en T4 contra el HTML guardado.
- **El HTML guardado trae más menciones que las visibles** (Alegra 147 frente a 76; es el mismo aviso que
  Loggro en COL): el lector debe leer el DOM visible o contará cifras duplicadas.
- **CONTPAQi no publica precios.** Se comprueba en cada corrida que siga así; si aparece un precio, aviso
  🟡. Nunca se escribe «no tiene».
- **Facturama** vende paquetes prepago, no planes mensuales: el registro debe guardarlos como pago único
  por documento.
- **Aspel es de Siigo.** Decisión pendiente: fusionarla con una fuente Siigo de MEX (hoy no existe) o
  dejarla con su clave y su nombre.

## T2 · Fuentes de prioridad 1 de República Dominicana (18-nov-2026)

| Fuente | Cifras | Moneda | Modo | Qué hay que saber |
|---|---|---|---|---|
| Alegra | 90 | USD | ruta_pais | Escribe «USD 26.10 / mes», sin símbolo `$` |
| Citrus | 0 | USD | no_publica | Home, `/productos/erp` y `/pruebaGratis` sin precios |

- **La moneda no dice el país en RD.** Alegra cobra en USD: el país lo confirman DGII, ITBIS, e-CF,
  TSS y los formatos 606/607.
- **Citrus no publica precios**: solo prueba gratis y el login del ERP. Se comprueba cada corrida.

## T2 · Fuentes de prioridad 1 de Costa Rica (18-nov-2026)

| Fuente | Cifras | Moneda | Modo | Qué hay que saber |
|---|---|---|---|---|
| Alegra | 105 | USD | ruta_pais | «USD 7,50 / mes», con coma decimal |
| Factura Profesional | 9 | USD | ruta_pais | `/precios` da 404; la página buena es `/planes-tarifas` |
| GTI | 5 | CRC | ruta_pais | Colones con punto de miles (₡ 7.650 a ₡ 76.500), sin IVA indicado |

- **Alegra cobra en USD en Costa Rica**: TRIBU-CR y Hacienda son las señales de país, no la moneda.
- En Costa Rica el `$` es USD; los colones van con `₡`.

### Lección para T4, en los cuatro países

El patrón de precios tiene que aceptar **el código de moneda delante** (`USD 13.50`, `COP 49.900`), no
solo el símbolo. Con el patrón que solo buscaba `$`, Alegra Costa Rica y Alegra RD devolvían **cero
cifras aunque las tienen**: una lectura vacía que parece «no publica» y que habría mandado dos fuentes a
`no_publica` por error.

## Inventario v2 (18-nov-2026)

Fuente: API pública de WordPress (`content.rendered`) de los 343 posts publicados más el único recurso,
y las páginas públicas de cada post.

| Vigía | Cifras (precios + límites) | Posts | Fuentes | Pendientes | Alegra que no coincide con su página |
|---|---|---|---|---|---|
| MEX | 299 (299 + 0) | 33 | 19 | 54 | 11 en 7 posts |
| COL | 508 (483 + 25) | 30 | 15 | 38 | 35 en 15 posts |
| CRI | 127 (127 + 0) | 19 | 16 | 33 | 13 en 10 posts |
| DOM | 186 (177 + 9) | 34 | 14 | 24 | 26 en 18 posts |
| **Total** | **1.120** | **115** | **64** | **149** | **85 en 50 posts** |

- **Cómo se reconoció el país** (precios): por la moneda de la cifra 484, por la frase o fila 371, por la
  sección 351, por el título 39 y por el post completo 19. Quedaron 16 sin país (`sin-pais.json`).
- Frente al inventario v1, solo 19 cifras cambiaron de país o quedaron sin país; ninguna pasó de un país
  a otro.
- Fuera de alcance: 33 cifras de Perú, Panamá y España.
- Pendientes por motivo (todos los países): 107 sin marca, 38 con marca de confianza baja, 4 dudosas;
  más 41 rangos de mercado sin marca ni fuente.

## Hallazgos

- **Dos posts tienen mal el metadato de país** (`pdc_target_country`): el 2157 (Miskuentas) es de México
  y el 2323 (Susii vs Alegra) es de Perú, pero los dos están marcados como Colombia. Detalle en
  `sin-pais.json` → `metadato_pais_en_conflicto`.
- **85 cifras de Alegra, en 50 posts, no aparecen en la página de precios de Alegra del 18-nov**
  (solo confianza alta). Ejemplos: Contabilidad Emprendedor de Colombia a $69.900 (hoy $74.900); un post
  de Colombia con planes de 30, 50 y 80 USD; 13 precios de Alegra RD en RD$, cuando cobra en USD.
- **Cinco posts con precios redirigen (301) y uno da 404 estando publicado** (post 3544).
- **Solo 28 posts tienen `pdc_target_country`**, y dos de ellos están mal.
- **La fecha de modificación de los posts no sirve para saber si un precio está viejo**: muchos se
  tocaron en lote el 14-nov-2026.
- **El anexo E de la skill prog-cont-blog está desactualizado en un punto**: los planes de POS México
  que muestra la página del 18-nov son POS Lite, POS Pro y POS Restobar.
- Lo propio de cada país (monedas, señales, descuento anual de Alegra, campañas) está en
  `paises/<vigía>/PAIS.md`.

## Decisiones abiertas

1. Fuentes cuya moneda depende de la IP: proxy por país (costo mensual) o lectura manual por alguien en
   el país.
2. Quién hace las lecturas manuales en cada país, si se elige esa opción.
3. Si las tablas de precios repetidas pasan a patrones sincronizados de WordPress.
4. Corregir el metadato de país de los posts 2157 y 2323.

## Siguiente paso

Instalar la skill `vigia-precios` en Hermes y pedirle la tarea T1 de `docs/PLAN.md` (verificar el
entorno); después T2 para cada vigía, empezando por COL (el de más cifras).
