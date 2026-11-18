# Decisiones del vigía de precios

Formato: número, fecha, qué se decidió y por qué. Las propuestas sin aprobar no entran aquí: viven en
`ESTADO.md` → «Decisiones abiertas».

## DEC-001 · nov-2026 · Para qué existe el vigía
Un agente aparte, el vigía de precios, mantiene actualizados los precios de las fichas de competidores
de PdC.

## DEC-002 · nov-2026 · Nada vive en un equipo local
Todo el sistema vive en el repositorio privado `Agente-Programas-de-Contabilidad` y en servicios en la
nube. Nada se guarda ni se ejecuta solo en un computador.

## DEC-003 · 5-nov-2026 · WordPress solo con un token de API
El acceso de escritura a WordPress es por token de API. Aplica al actualizador del vigía.

## DEC-004 · nov-2026 · Avisos en el espacio de Google Chat del agente
Los resultados del agente de PdC salen en su espacio de Google Chat. El vigía usa el mismo espacio y el
mismo `gchat.py`.

## DEC-005 · 18-nov-2026 · El vigía se construye y opera en Hermes
El vigía vive en Hermes, junto al agente diario de PdC (no en Codex ni en Claude Code). Las instrucciones
para el agente son la skill `vigia-precios`, versionada en `vigia/hermes-skill/`.

## DEC-006 · 18-nov-2026 · Inventario v1 desde la API pública
El inventario lee `content.rendered` de la API pública de WordPress, sin credenciales. Consecuencia: el
actualizador (paso 6) debe ubicar cada cifra en `content.raw` antes de reemplazar, porque el texto puede
venir con entidades o etiquetas en medio.

## DEC-007 · 18-nov-2026 · Un vigía por país, un solo código
Hay cuatro vigías: MEX, COL, CRI y DOM. Cada uno tiene su carpeta (`paises/<vigía>/`), sus fuentes, su
registro, su horario, su modo y sus avisos. El código es uno solo para los cuatro.

## DEC-008 · 18-nov-2026 · El país se reconoce por señales del contenido, no por la URL
Los enlaces del blog no siempre dicen de qué país es una pieza. El país de cada cifra se reconoce por
las palabras propias de cada país (SAT, DIAN, DGII, Hacienda, CFDI, e-CF, UVT, ITBIS, monedas y otras),
guardadas con su peso en `senales-pais.json`. Se mira de lo más cercano a lo más amplio: moneda, frase o
fila, sección, título, post y, al final, el metadato `pdc_target_country`. Si las señales contradicen el
metadato, ganan las señales y se avisa.
