# Reglas del vigía de precios

> **Aprobadas el 18-nov-2026 por Sharon Grueso** (responsable de PdC). Cada regla que bloquea se
> convierte en código (`reglas.json` y pruebas) al construir el lector y el comparador (T4 y T5).

## 1. Cuatro vigías, un solo código

- Hay **un vigía por país**: MEX, COL, CRI y DOM. Cada uno tiene su carpeta en `paises/<vigía>/` con su
  perfil (`PAIS.md`), sus fuentes, su inventario, sus pendientes y, después, su registro de precios.
- Cada vigía corre por separado (`--pais mex|col|cri|dom`), con su propio horario, su propio modo
  (`VIGIA_MODO_MEX`, `VIGIA_MODO_COL`, `VIGIA_MODO_CRI`, `VIGIA_MODO_DOM`) y sus propios avisos, con el
  prefijo del país. Uno puede estar en `aplicar` mientras otro sigue en `ensayo`.
- El código es uno solo para los cuatro: una corrección se hace una vez y sirve para todos.
- Se vigilan las marcas con precio publicado en una reseña, comparativa o pieza de «mejores
  herramientas» de ese país, más Alegra. Perú, Panamá y España quedan fuera.

## 1b. Cómo se reconoce el país

- **El país nunca sale de la URL**: los enlaces del blog no siempre dicen de qué país es una pieza.
- Sale de las **señales propias de cada país** que aparecen en el texto, guardadas en
  `senales-pais.json` con su peso: entes fiscales (SAT, DIAN, DGII, Hacienda), documentos (CFDI, e-CF,
  factura electrónica 4.4, documento soporte), identificaciones (RFC, NIT, RNC, cédula jurídica),
  impuestos y tarifas (ITBIS, UVT, IVA 16 % / 19 % / 13 %), monedas (MXN, COP, RD$, ₡) y otras.
- Se mira de lo más cercano a lo más amplio, y gana el primer nivel con un país claro: **moneda de la
  cifra → frase o fila → sección → título del post → post completo → metadato `pdc_target_country`**.
- Un país es claro si suma al menos 3 puntos y al menos el doble que el segundo (en una frase basta 2,
  por ejemplo «en Colombia», si ningún otro país aparece).
- Si ningún nivel da un país claro, la cifra va a `sin-pais.json` y no entra a ningún vigía hasta que
  una persona la asigne o se agregue la señal que faltaba.
- Si el metadato del post contradice las señales, **ganan las señales** y se avisa para corregir el
  metadato.

## 2. Qué cuenta como cambio

- Precio de lista de un plan.
- Nombre de un plan, plan nuevo o plan retirado.
- Periodo (mensual, anual, pago único, por documento).
- Moneda, o impuesto incluido frente a aparte.
- Límites que la pieza cite: usuarios, facturas, ingresos, bodegas, RFC.

## 3. Qué no cuenta como cambio

- Promociones de temporada: Black Friday, Cyber Monday, Buen Fin, fin de año o cualquier campaña con
  insignia, cuenta regresiva o vigencia.
- El descuento permanente por pago anual, aunque la página lo muestre como «25% OFF para usuarios
  nuevos» o «10% OFF». El de Alegra en cada país está en `paises/<vigía>/PAIS.md`.
- La etiqueta «Más popular» o «Recomendado».
- Diferencias de formato: «$49.900» frente a «$ 49.900».

## 4. Qué hace solo y qué solo avisa

| Caso | El vigía |
|---|---|
| Cambia la cifra de un plan que ya existe, mismo producto y mismo mercado, dos lecturas iguales y sin campaña | Aplica el cambio (todo o nada) y avisa 🟢 |
| Plan nuevo, retirado o renombrado | No toca nada. Aviso 🟡 |
| Campaña activa | No toca nada y conserva la línea base. Un aviso 🟡 por página |
| Lectura dudosa (moneda o país no coinciden, lecturas distintas, receta vacía) | No toca nada. Aviso 🟡 con el nombre de la página |
| Cambio de mercado (dominio, moneda, idioma o norma fiscal de otro país) | No toca nada. Aviso 🟡 con prioridad: la pieza se reescribe con otro ángulo |
| Falla del proceso | Aviso 🔴; si alcanzó a editar algo, restaura todo |

## 5. Reglas fijas (bloquean siempre)

- **País:** la página leída debe mostrar señales del país del vigía (las mismas de `senales-pais.json`).
  Si muestra señales de otro país, es una lectura dudosa o un cambio de mercado.
- **Moneda:** la moneda leída debe ser la `moneda_esperada` de la fuente y debe aparecer al menos una
  señal del país (impuesto, ente fiscal, dominio). En República Dominicana la moneda no basta, porque un
  lector desde EE. UU. también ve USD: se exigen señales como ITBIS, DGII o RD$.
- **Nunca se convierte la moneda.**
- **Los precios salen del DOM o del HTML**, nunca de una captura.
- **Si una marca no publica precios**, el registro dice «no publica», nunca «no tiene».
- **Todo o nada:** si cualquier edición falla, se restauran todos los posts de la corrida.
- **Se verifica en la página pública**, no solo en la API.
