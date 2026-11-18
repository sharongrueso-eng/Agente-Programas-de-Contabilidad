# Estado de los vigías de precios

Actualizado: 18-nov-2026.

Hay cuatro vigías, uno por país (MEX, COL, CRI y DOM), con un solo código. El país de cada cifra se
reconoce por las señales propias del país (`senales-pais.json`), no por la URL.

| Paso de la guía | Estado |
|---|---|
| 0. Reglas | Borrador en `REGLAS-VIGIA.md`, pendiente de aprobar |
| 1. Inventario | Hecho (v2, por país). Falta revisar la confianza media y los pendientes |
| 2. Registro de precios | Sin empezar |
| 3. Fuentes | Borrador en `paises/<vigía>/fuentes.json`: solo Alegra tiene URL verificada |
| 4 a 12 | Sin empezar |

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
