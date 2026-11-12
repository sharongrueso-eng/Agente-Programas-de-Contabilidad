# Estrategia editorial del agente PdC

## Qué aporta este blog de marca blanca

programascontabilidad.com no compite por tráfico de marca: compite por las búsquedas donde
alguien está decidiendo qué software usar. Su valor es triple.

**Captura demanda de decisión.** Quien busca «alegra vs siigo» o «mejores software contable
Colombia» está a un paso de contratar. Es el tráfico más caro de conseguir por publicidad y el
que mejor convierte.

**Da autoridad prestada a Alegra sin que parezca publicidad.** Un blog de marca que compara,
reconoce límites y cita normativa gana la confianza que una landing propia no puede fingir.

**Alimenta a los asistentes de IA.** Los artículos con respuesta directa, tablas y datos
citables son los que Google y los LLM citan. Ese es el canal que crece, y el blog es la única
propiedad de Alegra que puede competir ahí con contenido editorial.

## Cómo se mide si un artículo merece trabajo

Con Search Console, ventana de 28 días cerrados. Un artículo entra en la cola cuando cumple al
menos dos de estas tres:

| Señal | Umbral | Qué indica |
|---|---|---|
| Impresiones | por encima del mínimo del mercado | hay demanda demostrada |
| CTR frente a su posición | por debajo de lo esperable | el título no se hace clic |
| Posición | entre 5 y 15 | está en la frontera: se puede subir |

Y una cuarta que no depende de GSC: **antigüedad**. Un artículo de hace más de cuatro meses en un
tema con normativa cambiante se revisa aunque sus números estén bien.

## Qué se hace con él, y no siempre es el título

| Situación del artículo | Trabajo |
|---|---|
| Responde bien, pero no se hace clic | título y meta |
| Le falta comparativa: no tiene tabla, ni ficha por marca, ni veredicto | **cuerpo completo** |
| Tiene datos viejos o normativa derogada | **cuerpo**: cifras y secciones afectadas |
| Le faltan bloques visuales, imágenes o resumen | **cuerpo**: enriquecimiento |
| El tema no existe en el blog | **artículo nuevo** |

Regla dura: **un reencauche nunca cambia el slug ni crea una URL nueva**. La versión anterior
queda en el historial de revisiones de WordPress.

Y una regla que nació de un error real: **el mercado se lee en el contenido del artículo**, no en
la URL ni en la keyword. Un post sobre el SAT es mexicano aunque su ruta no lo diga. Si no hay
señal suficiente, el agente se abstiene.

## Cómo se ve un artículo bien hecho

Los seis últimos publicados marcan el estándar. Nuestro agente debe caber en él:

| Medida | Rango del blog | Regla para el agente |
|---|---|---|
| Palabras | 1.300 – 2.950 | **sin objetivo**: manda la calidad, no la extensión |
| H2 | 6 – 15 | 7 – 10 |
| H3 | 4 – 20 | al menos uno por herramienta comparada |
| Tablas | 1 – 3 | la comparativa y, si hay planes, la de precios |
| Imágenes | 0 – 4 | portada + 1 a 3 capturas con pie fechado |
| Enlaces internos | 5 – 31 | mínimo 5 |

**Decisión tomada:** solo se usan capturas de la interfaz de Alegra, y van sin ficha al pie.
No se guardan imágenes de sitios de competidores.

**Sobre las capturas:** las de la interfaz de Alegra y de los competidores son lo que más
diferencia un artículo de una lista. Se toman del sitio oficial, con alt descriptivo y pie
«consultada el {fecha}». Si no hay captura posible, se dice; no se simula.

**Sobre Alegra:** se destaca por lo que el registro demuestra —precio, funciones, facilidad— y
siempre con un límite honesto al lado. Nunca un elogio sin dato.

## Los cuatro bloques que no pueden faltar

1. **Respuesta rápida** en la primera pantalla: la pregunta del título contestada en una frase.
2. **Puntos clave** en caja de color: tres o cuatro viñetas con lo que decide la compra.
3. **Tabla comparativa** con columna destacada «mejor para…» y pie de fuente y fecha.
4. **Veredicto** por perfil de negocio, separado del CTA.

La línea visual está en `orchestrator/linea_visual.py`; estos bloques se construyen en código y
el modelo solo aporta el texto.

## El aviso de Google Chat

Cada corrida avisa con: título, slug, estado (nuevo / actualizado en la misma URL), el porqué con
cifras de GSC —impresiones, CTR, posición y clics potenciales—, el resultado del control de
calidad, el enlace directo a wp-admin y los campos SEO escritos.

## Aprendizajes de los seis últimos posts

- El blog publica **1.300–2.950 palabras**. No se impone un largo: un texto citado por un
  modelo de lenguaje no gana por tener más, y alargar por alargar añade ruido.
- Las comparativas llevan **tres tablas y tres imágenes**; los artículos de un solo tema, una.
- El blog mezcla dos paletas antiguas (`#CCE4F7`, `#129CD8`). La línea visual nueva las sustituye
  por los componentes de `linea_visual.py`, sin romper el historial.
- Los artículos con más enlaces internos (15 y 31) son los de mayor recorrido: el enlazado no es
  relleno, es navegación.
