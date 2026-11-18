# Vigía COL · Colombia

Uno de los cuatro vigías de precios de PdC. Comparte el código con los otros tres; lo propio de
Colombia está en esta carpeta.

| | |
|---|---|
| Código de país | `CO` |
| Autoridad fiscal | DIAN |
| Monedas | COP (pesos colombianos). Algún post antiguo cita Alegra Colombia en USD: es un precio viejo. |
| Señales del país (resumen) | DIAN, UVT, exógena, CUFE, RADIAN, UGPP, PILA, retención en la fuente, ReteICA, Régimen Simple, documento soporte, NIT, RUT, COP, IVA 19 % |
| Página de precios de Alegra | https://www.alegra.com/colombia/precios/ |
| Descuento anual de Alegra (18-nov) | 25 % en todos los productos. No es una promoción |
| Campañas que no son cambio de precio | Black Friday, Cyber Monday, Cyberlunes y fin de año |
| Corrida | Días 1 y 16, 7:00 hora de Bogotá (`0 12 1,16 * *` en UTC) |
| Modo | Variable `VIGIA_MODO_COL`: `ensayo`, `aplicar` o `pausa` |
| Avisos | Espacio de Google Chat del agente, con el prefijo `[COL]` |

La lista completa de señales, con sus pesos, está en `vigia/senales-pais.json`.

## Inventario (18-nov-2026)

- 508 cifras (483 precios y 25 límites) en 30 posts — `ubicaciones.json`.
- País reconocido con confianza alta: 312; media: 193; baja: 3.
- 15 fuentes (marca + país) — `fuentes.json`.
- 38 cifras pendientes y 16 rangos de mercado sin marca — `pendientes.json`.
- 35 cifras de Alegra (confianza alta) que no aparecen en su página de precios del 18-nov, en 15 posts.

## Fuentes de prioridad 1

| Marca | Cifras | Posts | URL de precios |
|---|---|---|---|
| Alegra | 234 | 29 | https://www.alegra.com/colombia/precios/ |
| Siigo | 124 | 18 | https://www.siigo.com/precios-siigo/ |
| Vendty | 43 | 4 | https://www.vendty.com/precios |
| Loggro | 25 | 8 | https://loggro.com/pymes/planes/ |
| World Office | 14 | 5 | por buscar |

## Notas del país

- La tabla de precios de Alegra Colombia del anexo F de la skill (22-oct) coincide con la página del 18-nov.
- Es el vigía con más límites de plan citados («ingresos hasta $40M»): también hay que vigilarlos.
