# Inventario de precios publicados (paso 1 del vigía)

Primera versión, generada el 18-nov-2026. Mapea cada cifra de dinero publicada en programascontabilidad.com
y la atribuye a país, marca, producto y plan.

Se corre desde `vigia/inventario/`. Las descargas quedan en `raw/` y los resultados en `salida/`
(las dos carpetas están en `.gitignore`). Los resultados salen separados por vigía en
`salida/paises/<vigía>/` y se copian a `vigia/paises/`; `salida/sin-pais.json` se copia a `vigia/`.

## Archivos de datos

| Archivo | Qué tiene |
|---|---|
| `paises/<vigía>/ubicaciones.json` | Cifras del vigía (precios y límites) con marca, producto, plan, país y cómo se reconoció el país. En total 1.120 |
| `paises/<vigía>/fuentes.json` | Pares marca + país en borrador: URL candidata, monedas vistas y campos por completar. En total 64 |
| `paises/<vigía>/pendientes.json` | Cifras sin marca o con confianza baja, y rangos de mercado sin marca |
| `sin-pais.json` | Cifras sin país reconocido, cifras fuera de alcance (PE, PA, ES) y posts cuyo metadato de país contradice sus señales |

## Cómo se regenera

```
python descargar.py          # posts, señales de país, redirecciones y páginas de Alegra (usa curl)
python units.py              # HTML -> párrafos, ítems y filas de tabla con su encabezado
python extraer.py            # cifras -> país, marca, producto, plan, periodo, tipo y confianza
python comparar_alegra.py    # cifras de Alegra contra su página de precios de hoy
python armar.py              # por vigía: ubicaciones, fuentes y pendientes; más sin-pais.json
cp -r salida/paises/* ../paises/ && cp salida/sin-pais.json ..
```

`pais.py` reconoce el país de una cifra con las señales de `vigia/senales-pais.json` (lo prueba
`vigia/tests/test_pais.py`). `numeros.py` lee monedas y cifras según la convención de cada país (lo prueban `vigia/tests`).
`marcas.py` es el léxico de marcas (patrones y dominios oficiales). Cuando aparezca una marca nueva,
se agrega ahí.

## Límites conocidos

- Las cifras salen de `content.rendered`. El actualizador debe buscarlas en `content.raw` (Gutenberg)
  antes de reemplazar: el texto puede venir con entidades o etiquetas en medio.
- La atribución es heurística. En la muestra revisada, la confianza alta salió casi siempre bien y la
  media acertó cerca de 9 de cada 10. Revisar la media antes de dar el inventario por bueno.
- `alegra_hoy` compara contra los montos que aparecen en la página de precios de Alegra del país; una
  cifra mal atribuida también puede salir como «no_coincide».
- La fecha de modificación de los posts no sirve para saber si un precio está viejo: muchos posts se
  tocaron en lote el 14-nov-2026.
