# Vigía MEX · México

Uno de los cuatro vigías de precios de PdC. Comparte el código con los otros tres; lo propio de
México está en esta carpeta.

| | |
|---|---|
| Código de país | `MX` |
| Autoridad fiscal | SAT |
| Monedas | MXN (pesos mexicanos). Algunas marcas también publican en USD. |
| Señales del país (resumen) | SAT, CFDI, RFC, RESICO, DIOT, Carta Porte, complemento de pago, timbrado, e.firma, IMSS, MXN, IVA 16 % |
| Página de precios de Alegra | https://www.alegra.com/mexico/precios/ |
| Descuento anual de Alegra (18-nov) | 25 % en Facturación, POS y ERP; 10 % en Soy Contador. No es una promoción |
| Campañas que no son cambio de precio | Buen Fin (noviembre), Hot Sale (mayo-junio), Black Friday, Cyber Monday y fin de año |
| Corrida | Días 1 y 16, 7:15 hora de Bogotá (`15 12 1,16 * *` en UTC) |
| Modo | Variable `VIGIA_MODO_MEX`: `ensayo`, `aplicar` o `pausa` |
| Avisos | Espacio de Google Chat del agente, con el prefijo `[MEX]` |

La lista completa de señales, con sus pesos, está en `vigia/senales-pais.json`.

## Inventario (18-nov-2026)

- 299 cifras (299 precios y 0 límites) en 33 posts — `ubicaciones.json`.
- País reconocido con confianza alta: 275; media: 22; baja: 2.
- 19 fuentes (marca + país) — `fuentes.json`.
- 54 cifras pendientes y 10 rangos de mercado sin marca — `pendientes.json`.
- 11 cifras de Alegra (confianza alta) que no aparecen en su página de precios del 18-nov, en 7 posts.

## Fuentes de prioridad 1

| Marca | Cifras | Posts | URL de precios |
|---|---|---|---|
| Alegra | 103 | 22 | https://www.alegra.com/mexico/precios/ |
| CONTPAQi | 61 | 8 | por buscar |
| Facturama | 42 | 4 | https://facturama.mx/planes-facturacion |
| Miskuentas | 24 | 3 | https://www.miskuentas.com/tienda/ |
| Aspel | 8 | 4 | por buscar |

## Notas del país

- Los planes de POS de Alegra que muestra la página del 18-nov son POS Lite, POS Pro y POS Restobar; el anexo E de la skill prog-cont-blog todavía dice Inicial, Pro y Gastrobar.
- El post 2157 (Miskuentas) es de México por sus señales, pero su metadato de país dice Colombia.
