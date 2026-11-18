# Vigía CRI · Costa Rica

Uno de los cuatro vigías de precios de PdC. Comparte el código con los otros tres; lo propio de
Costa Rica está en esta carpeta.

| | |
|---|---|
| Código de país | `CR` |
| Autoridad fiscal | Ministerio de Hacienda (TRIBU-CR, ATV) |
| Monedas | USD en Alegra y en varias marcas; CRC (colones, ₡) en otras. La moneda esperada se fija por fuente. |
| Señales del país (resumen) | Hacienda, TRIBU-CR, ATV, factura electrónica 4.4, tiquete electrónico, cédula jurídica, CCSS, BCCR, colones, ₡, CRC, IVA 13 % |
| Página de precios de Alegra | https://www.alegra.com/costarica/precios/ |
| Descuento anual de Alegra (18-nov) | 25 % en Facturación, POS y ERP; 10 % en los planes para contadores. No es una promoción |
| Campañas que no son cambio de precio | Black Friday, Cyber Monday y fin de año |
| Corrida | Días 1 y 16, 7:30 hora de Bogotá (`30 12 1,16 * *` en UTC) |
| Modo | Variable `VIGIA_MODO_CRI`: `ensayo`, `aplicar` o `pausa` |
| Avisos | Espacio de Google Chat del agente, con el prefijo `[CRI]` |

La lista completa de señales, con sus pesos, está en `vigia/senales-pais.json`.

## Inventario (18-nov-2026)

- 127 cifras (127 precios y 0 límites) en 19 posts — `ubicaciones.json`.
- País reconocido con confianza alta: 37; media: 84; baja: 6.
- 16 fuentes (marca + país) — `fuentes.json`.
- 33 cifras pendientes y 5 rangos de mercado sin marca — `pendientes.json`.
- 13 cifras de Alegra (confianza alta) que no aparecen en su página de precios del 18-nov, en 10 posts.

## Fuentes de prioridad 1

| Marca | Cifras | Posts | URL de precios |
|---|---|---|---|
| Alegra | 42 | 15 | https://www.alegra.com/costarica/precios/ |
| Factura Profesional | 24 | 4 | por buscar |
| GTI | 20 | 5 | https://www.facturaelectronica.cr/Planes |

## Notas del país

- Muchas cifras de Costa Rica están en USD sin señal en la misma frase: el país sale de la sección (confianza media). Conviene revisarlas primero.
