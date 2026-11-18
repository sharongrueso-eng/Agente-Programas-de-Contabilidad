# Vigía DOM · República Dominicana

Uno de los cuatro vigías de precios de PdC. Comparte el código con los otros tres; lo propio de
República Dominicana está en esta carpeta.

| | |
|---|---|
| Código de país | `DO` |
| Autoridad fiscal | DGII |
| Monedas | USD en Alegra y en varias marcas; DOP (RD$) en otras. La moneda sola no basta: un lector desde EE. UU. también ve USD. |
| Señales del país (resumen) | DGII, ITBIS, e-CF, e-NCF, NCF, RNC, Ley 32-23, TSS, IT-1, IR-17, formatos 606/607/608, RD$, DOP, Facturador Gratuito |
| Página de precios de Alegra | https://www.alegra.com/rdominicana/precios/ |
| Descuento anual de Alegra (18-nov) | 10 % en todos los productos. No es una promoción |
| Campañas que no son cambio de precio | Black Friday, Cyber Monday y fin de año |
| Corrida | Días 1 y 16, 7:45 hora de Bogotá (`45 12 1,16 * *` en UTC) |
| Modo | Variable `VIGIA_MODO_DOM`: `ensayo`, `aplicar` o `pausa` |
| Avisos | Espacio de Google Chat del agente, con el prefijo `[DOM]` |

La lista completa de señales, con sus pesos, está en `vigia/senales-pais.json`.

## Inventario (18-nov-2026)

- 186 cifras (177 precios y 9 límites) en 34 posts — `ubicaciones.json`.
- País reconocido con confianza alta: 101; media: 81; baja: 4.
- 14 fuentes (marca + país) — `fuentes.json`.
- 24 cifras pendientes y 10 rangos de mercado sin marca — `pendientes.json`.
- 26 cifras de Alegra (confianza alta) que no aparecen en su página de precios del 18-nov, en 18 posts.

## Fuentes de prioridad 1

| Marca | Cifras | Posts | URL de precios |
|---|---|---|---|
| Alegra | 98 | 29 | https://www.alegra.com/rdominicana/precios/ |
| Citrus | 8 | 4 | por buscar |

## Notas del país

- 13 cifras de Alegra RD están publicadas en RD$, cuando Alegra RD cobra en USD: son precios viejos o convertidos.
