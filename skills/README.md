# Skills del blog PdC

Skills editoriales del agente, importadas desde los paquetes `.skill` de la cuenta de
Claude el 5 de noviembre de 2026 y **actualizadas el 6 de noviembre de 2026** para
alinearlas con la arquitectura v2 y las decisiones del equipo.

| Skill | Contenido | Estado |
|---|---|---|
| `leandro` | `SKILL.md` + `references/{competitors,content-competitors,legal-context}.md` | Actualizado |
| `pdc-locale-signals` | `SKILL.md` | Sin cambios |

## Decisiones aplicadas

1. **Alegra se nombra por su nombre.** Se retiró la regla de marca blanca que prohibía
   mencionarla en el CTA. El CTA la nombra y toda pieza lleva tres enlaces a Alegra —país,
   producto y término— con UTM completa.
2. **Cuatro mercados, sin Panamá.** Colombia, México, Costa Rica y República Dominicana.
   Se eliminó la ficha de Panamá del contexto legal.
3. **Autoría y firma de Leandro.** Se mantiene el autor `user ID 17` y el bloque de
   biografía al final de cada artículo.
4. **Publicación autónoma.** El módulo publicador sube la pieza tras los controles; la
   revisión del equipo es posterior. El texto de la skill ya no habla de MCP como
   requisito, sino del token de API de WordPress.
5. **Honestidad de la prueba.** Regla nueva: «probé» solo con evidencia documentada en el
   registro de datos; en el resto de los casos, «revisé».

## Correcciones legales

`references/legal-context.md` se reescribió con normativa verificada el 6 de noviembre
de 2026 y fuente oficial por mercado:

| Mercado | Norma vigente que faltaba o estaba mal |
|---|---|
| Colombia | Resolución DIAN 000165 de 2023 (reemplaza la 000042 de 2020), Resolución 000202 de 2025 y Resolución 000227 de 2025 |
| México | CFDI 4.0 en vigor desde el 1 de enero de 2022 y única versión válida desde el 1 de abril de 2023 |
| Costa Rica | TRIBU-CR; Ley 9416; Decreto Ejecutivo 44739-H; MH-DGT-RES-0027-2024 y MH-DGT-RES-0001-2025; versión 4.4 operativa desde el 1 de septiembre de 2025; D-150 |
| República Dominicana | Ley 32-23 y Decreto 587-24; cinco estados del e-CF; exclusividad del e-CF tipo «E» desde el 1 de noviembre de 2026 |

Se corrigieron además la terminología (el estándar es «negocios y empresas»), una
resolución mal citada en el ejemplo de intro (000227 de 2024 → de 2025) y la mención de
MCP como vía de publicación.

## Controles automáticos

`tests/test_skills_contract.py` verifica estas decisiones sobre el texto de las skills:
ausencia del término retirado, mención de Alegra en el CTA, los tres enlaces, la regla de
«probé», los cuatro mercados y las normas vigentes por país. Si alguien vuelve a meter una
regla retirada, la suite falla.

## Advertencia de versión

El `SKILL.md` base es la copia de 41.808 bytes (7 de mayo de 2026). El inventario del
equipo registra una versión posterior del 6 de agosto (57–58 KB) que no está en este
repositorio. Las correcciones de este commit se aplicaron sobre la versión disponible:
cuando llegue la de agosto, hay que fusionarla y volver a correr los controles.
