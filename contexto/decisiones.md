# Decisiones y preguntas abiertas

## Aceptadas como base

- El blog busca presencia en etapa de evaluación/comparación; la métrica norte es Share of Voice.
- Mercados iniciales: Colombia, México, República Dominicana y Costa Rica.
- Contenido firmado por Leandro, con honestidad sobre pruebas no realizadas.
- La versión v2 propone dos slots diarios y publicación autónoma después de validaciones; la revisión del equipo es posterior.
- Fallo cerrado: ante falta de evidencia o control crítico fallido, no publicar.

## Decisiones confirmadas

- El scheduler autoritativo será Hermes cron dentro de la instancia alojada en Coolify.

## Resolver antes de producción

1. Importar y fijar la versión de `leandro`, `pdc-locale-signals` y referencias antes de producción; el DOCX disponible es un inventario, no los contenidos fuente.
2. Accesos: confirmar ruta de IT para GSC de solo lectura, Ahrefs, LiteLLM, WordPress API y webhook de Chat.
3. Riesgos documentados: publicación autónoma sin aprobación previa; reglas de marca blanca frente a divulgación de vínculos; decisiones de orden de Alegra en listados/tablas; hechos legales por país.
