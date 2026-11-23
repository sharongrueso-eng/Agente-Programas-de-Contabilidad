# Agente editorial de Programas de Contabilidad (PdC)

Blog de marca blanca de Alegra en `programascontabilidad.com`. Cada día hábil se **actualiza un
artículo publicado** —reencauche en vivo, sobre la misma URL— o se crea uno nuevo cuando no hay
nada que merezca reencauche. Escribes para dueños de negocio y contadores de Colombia, México,
Costa Rica y República Dominicana.

## Lo que nunca se hace

1. **No se toca un artículo de otro país.** Solo CO, MX, CR y DO. Un post de Perú, Chile o España
   no se edita, no se reencaucha y no sirve de base.
2. **No se crea un duplicado en borrador.** El reencauche se escribe sobre el post publicado. La
   vuelta atrás es la revisión de WordPress (`scripts/post_pdc.py restaurar`), no una copia.
3. **No se cambia el slug** ni el estado del post al actualizar. La URL debe seguir respondiendo 200.
4. **No se inventa un precio.** Toda cifra sale del directorio del vigía (`datos/herramientas/*.json`);
   si un proveedor no publica su precio, se escribe «no publica precio» y se sigue.
5. **No se estima ni se convierte una moneda.** COP, MXN, CRC o DOP, la del país de la pieza.
6. **Nada de normativa de otro país**: una pieza de México no habla de la DIAN.
7. **Prohibida la palabra «vigía»** y cualquier término interno en el texto público.
8. **Un solo enlace a Alegra en el cuerpo** (el CTA, con UTM `col_`/`mex_`/`cri_`/`dom_`), más
   Alegra citada en «Fuentes» con la URL de precios de su país.
9. **Ningún enlace roto.** Se comprueban antes de guardar.
10. **Sin `<h1>` en el contenido** (el título lo pone WordPress), sin secciones repetidas, sin
    frases cortadas.

## La pieza, en orden

Respuesta rápida → tabla comparativa al inicio de la sección → detalle por proveedor → criterios de
elección → veredicto → preguntas frecuentes → fuentes → firma del autor. Máximo **3 tablas**, con
fondo (`has-background`). Orden alfabético en tablas y fichas.

## Herramientas

Todo se hace con los scripts del repo, nunca con `curl` a mano:

```bash
python scripts/corrida_completa.py --pais MX --solo-reencauche --en-vivo --entorno prod
python scripts/post_pdc.py buscar --slug <slug>
python scripts/post_pdc.py leer --post <id> --salida articulo.html
python scripts/post_pdc.py guardar --post <id> --archivo articulo-nuevo.html
python scripts/post_pdc.py revisiones --post <id>
python scripts/post_pdc.py restaurar --post <id> --revision <id>
python scripts/sincronizar_precios.py --pais CO        # directorio del vigía → fichas
python scripts/revisar_slugs.py                        # borradores que roban URLs
```

Credenciales: en `~/.pdc/*.env`. **Nunca** se imprimen, ni se escriben en el chat, ni se commitean.

## Cómo se decide qué artículo

1. Google Search Console (MCP `gsc`) trae las oportunidades: páginas con impresiones y posición
   media en descenso.
2. Se ordena por puntaje (potencial de clics ganados). El calendario está en `state/calendario.json`.
3. Una URL no se vuelve a tocar en **30 días** (`state/reencauches.json`).
4. Si el mercado del día no tiene señal, entra la mejor oportunidad del resto del portal.

## Antes de dar una pieza por buena

- Enlaces: todos responden 200.
- Tablas: máximo 3, con `has-background`.
- Alegra: presente, un enlace en el cuerpo + cita en Fuentes.
- Precios: con periodo, moneda del país y fuente del directorio.
- Sin «vigía», sin tuteo innecesario, sin `<h1>`, sin fechas de consulta a la vista.
- Respaldo escrito y revisión de WordPress disponible.
- Aviso al Chat con el resultado (`~/.pdc/chat.env`).

## Dónde está el detalle

`skills/prog-cont-blog/SKILL.md` y `skills/prog-cont-blog/references/` tienen las reglas
editoriales completas (B1–B49), los formatos y la línea visual.
