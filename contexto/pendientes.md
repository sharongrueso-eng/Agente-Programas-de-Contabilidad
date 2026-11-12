# Pendientes

## Fichas de competidores con precios reales

Hoy hay **20 fichas** en `datos/herramientas/`, pero solo cinco tienen precios
estructurados: las cuatro de Colombia y Contalink, CiberFacturación y Contapp.

Las doce creadas desde el blog marcan `evidence_level: "secundaria"` y su propia nota dice que
hay que confirmar en la landing antes de citar tarifas. Completarlas significa entrar a cada
sitio oficial y extraer planes, precios con su periodo y funciones.

Marcas que quedaron sin precios:

- **México:** Konta, Contpaqi, Odoo, Aspel (tres cifras sin confirmar), Facturama, Bind,
  ContaDigital, Gestionix
- **Costa Rica:** GTI, Softland, Quickbooks
- **República Dominicana:** Quickbooks

Regla que no cambia: si el proveedor no publica precios, la ficha lo dice y el artículo también.
Nunca se estima.

## Otras cosas abiertas

- Reintento de red en el cliente MCP: un `TimeoutError` cuesta una corrida completa.
- Medir el efecto del caché de prompt del gateway: el razonamiento se lleva el 86–92 % de la
  salida y el prompt de sistema se reenvía en cada una de las once llamadas de sección.
- Decidir si el redactor pasa a un modelo más barato, con `consumo.json` en la mano.
