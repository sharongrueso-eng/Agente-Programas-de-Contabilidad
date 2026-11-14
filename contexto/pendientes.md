# Pendientes

Actualizado el 13 de noviembre de 2026. El detalle de la sesión está en
`contexto/estado-2026-11-13.md`.

## Artículos

| Qué | Dónde | Qué falta |
|---|---|---|
| **5309** está en borrador y su URL responde 404 | wp-admin post 5309 | Decidir si se republica; el contenido está íntegro y verificado |
| **5309** tiene 6 tablas | mismo post | Con el control `presupuesto_tablas` quedaría bloqueado: hay dos tablas de Loggro duplicadas y hay que elegir cuáles tres se quedan |
| **154** (Efact vs Alegra, Perú) no se puede escribir por API | wp-admin post 154 | 4,4 MB de contenido: 4,2 MB son nueve imágenes en base64 incrustadas. nginx responde 413 a cualquier actualización. Sacarlas desde el editor o subir el límite del servidor |
| Huecos de prosa donde el saneador retiró cifras | 1957 y 5309 | «facturación 24 + nómina electrónica  y su POS Esencial .» y frases equivalentes: hay que reescribirlas con la cifra registrada |
| Tabla de precios del 3106 sin símbolo de dólar en la celda | 3106 | El encabezado dice USD; decidir si la cifra lleva `$` en cada celda |

## Fichas de competidores

Treinta y tres fichas en `datos/herramientas/`. Las de **Colombia** (Siigo, Alegra, Loggro,
Siesa, World Office Cloud y Escritorio) y la de **Adm Cloud** (RD) quedaron con sus tarifas
leídas de la página oficial el 13-nov-2026.

Siguen sin precios estructurados:

- **México:** Konta, Contpaqi, Odoo, Aspel, Facturama, Bind, ContaDigital, Gestionix
- **Costa Rica:** GTI, Softland, Quickbooks
- **República Dominicana:** Quickbooks y el resto del directorio

Regla que no cambia: si el proveedor no publica precios, la ficha lo dice y el artículo también.
Nunca se estima.

## Infraestructura

- **El scheduler no está creado.** En la instancia de Hermes no hay ninguna tarea programada;
  las de `deploy/cron.md` y la de Coolify son comandos a ejecutar. Antes de activarlas hay que
  redesplegar la imagen para que lleve los controles del 13-nov.
- **Reintento de red en el cliente MCP.** Se agregó a `scripts/firmar_posts.py` después de que
  el lote de firmas muriera en la pieza 257 con `WinError 10054`; el mismo reintento falta en
  `orchestrator/runner.py`, donde un corte de red cuesta la corrida completa.
- **Tareas en modo `script` y variables de entorno**: confirmar con IT que el programador las
  pasa al proceso.

## Costo

- Medir el efecto del caché de prompt del gateway: el razonamiento se llevó el 86–92 % de la
  salida y el prompt de sistema se reenvía en cada llamada de sección.
- Decidir si el redactor pasa a un modelo más barato, con `consumo.json` en la mano. La última
  corrida medida: 35 llamadas, 491.395 tokens de entrada, 162.354 de razonamiento.
