# Skills importadas

Copia sin modificar de las skills que usa la cuenta de Claude, extraídas de
`leandro.skill` y `pdc-locale-signals.skill` (paquetes ZIP) el 5 de noviembre de 2026.

| Skill | Archivos | SKILL.md | Notas |
|---|---|---|---|
| `leandro` | `SKILL.md` + `references/{competitors,content-competitors,legal-context}.md` | 41.808 bytes | Persona editorial y reglas de redacción |
| `pdc-locale-signals` | `SKILL.md` | 4.405 bytes | `pdc_target_country` y señales de localidad |

No se editó ningún archivo: son la fuente de verdad del equipo y varias correcciones
necesitan verificación legal, no criterio del agente.

## Ambigüedad de versión

`leandro/SKILL.md` pesa 41.808 bytes, que corresponde a la versión instalada en Claude
el 7 de mayo. El inventario del 3 de noviembre registra una versión posterior, del 6 de
agosto, de 57–58 KB, y señala que la Wiki referencia la variante de `Sub-agents`.
**Falta confirmar si esta copia es la vigente.** Si no lo es, el texto que se produzca
seguirá reglas que el flujo Codex ya cambió.

## Defectos conocidos, confirmados en estos archivos

| Hallazgo | Evidencia | Consecuencia |
|---|---|---|
| Costa Rica contradice su propia skill | `references/legal-context.md` líneas 97–103: «Administración Tributaria Virtual», «Resolución DGT-R-48-2016» | La skill exige TRIBU-CR y D-150. Un artículo de CR puede publicar la norma equivocada |
| República Dominicana sin normativa vigente | No aparecen la Ley 32-23 ni el Decreto 587-24 | El e-CF se describe como «en transición» |
| Terminología | 9 apariciones de «pyme/pymes» en 3 archivos | El estándar de Leandro es «negocios y empresas» |
| Panamá ausente | `pdc-locale-signals` cubre DO, CO, MX y CR | Un post de PA hereda `es` / `es_419` |

## Conflictos con la arquitectura v2, que necesitan decisión

1. **CTA contra enlaces a Alegra.** La skill tiene una regla dura: «el CTA nunca menciona
   Alegra por su nombre» (líneas 38, 50 y 111). La arquitectura v2 exige tres enlaces a
   Alegra con UTM en toda pieza nueva o actualizada. Son incompatibles tal como están.
2. **Biografía obligatoria.** La skill ordena insertar un bloque HTML de biografía con
   afirmaciones de independencia editorial (líneas 117–127 y 615). La v2 dejó abierta la
   decisión sobre divulgación de vínculos comerciales.
3. **Publicación desde la skill.** La skill asume publicación directa por MCP con autor
   `user ID 17`. En v2 el productor solo crea borradores con el token de API; publicar es
   del publicador.
4. **Honestidad de la prueba.** La skill no distingue «probé» de «revisé». Esa regla vive
   hoy solo en `SYSTEM.md` y debe entrar al brief del productor.

Ninguno de estos puntos se resolvió por cuenta del agente.
