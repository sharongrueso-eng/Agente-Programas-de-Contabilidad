# Decisiones y preguntas abiertas

## Aceptadas como base

- El blog busca presencia en etapa de evaluación/comparación; la métrica norte es Share of Voice.
- Mercados iniciales: Colombia, México, República Dominicana y Costa Rica.
- Contenido firmado por Leandro, con honestidad sobre pruebas no realizadas.
- La versión v2 propone dos slots diarios y publicación autónoma después de validaciones; la revisión del equipo es posterior.
- Fallo cerrado: ante falta de evidencia o control crítico fallido, no publicar.

## Decisiones confirmadas

- El scheduler autoritativo será Hermes cron dentro de la instancia alojada en Coolify.
- **Skills y marca (6 nov 2026):** la skill nombra a Alegra por su nombre y cada pieza lleva tres enlaces con UTM. Se mantiene la autoría y la biografía de Leandro. La publicación es autónoma, con revisión posterior. Mercados: Colombia, México, Costa Rica y República Dominicana; Panamá queda fuera.
- **Normativa (6 nov 2026):** `legal-context.md` se reescribió con fuente oficial por país. Colombia cita la Resolución DIAN 000165 de 2023 y la 000227 de 2025; Costa Rica usa TRIBU-CR, Ley 9416 y MH-DGT-RES-0027-2024; República Dominicana cita la Ley 32-23 y el Decreto 587-24.
- **Honestidad (6 nov 2026):** «probé» solo con evidencia documentada en el registro; en el resto, «revisé».

## Resolver antes de producción

1. Importar y fijar la versión de `leandro`, `pdc-locale-signals` y referencias antes de producción; el DOCX disponible es un inventario, no los contenidos fuente.
2. Accesos: confirmar ruta de IT para GSC de solo lectura, Ahrefs, LiteLLM, WordPress API y webhook de Chat.
3. Riesgos documentados: publicación autónoma sin aprobación previa; reglas de marca blanca frente a divulgación de vínculos; decisiones de orden de Alegra en listados/tablas; hechos legales por país.

## Límite del gateway en piezas largas

Medido el 2026-11-06 contra el LiteLLM de Alegra, con el mismo prompt de 46.700 caracteres:

| Modelo | max_tokens | Resultado |
|---|---|---|
| deepseek/deepseek-v4-pro | 8.000 | contenido vacío (los tokens de razonamiento consumen el presupuesto) |
| deepseek/deepseek-v4-pro | 16.000 | 504 del gateway |
| deepseek/deepseek-v4-flash | 12.000 | JSON truncado |
| deepseek/deepseek-v4-flash | 20.000 | pieza completa, pero sin enlaces a Alegra, internos ni fuentes |
| zai/glm-5.3 | 20.000 | 504 del gateway |

Conclusión: una pieza de ~13.000 caracteres no se puede generar de una sola llamada por este
gateway. El siguiente paso es producir **por secciones**: la estructura de nueve bloques ya
está definida, así que cada bloque es una llamada corta que cabe en el tiempo del gateway y
cuyo reintento cuesta poco.
