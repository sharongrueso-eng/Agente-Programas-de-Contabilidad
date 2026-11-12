# Cómo compartir esto con un colega que también usa Hermes

Hay tres niveles. Elige según qué quieras que tenga la otra persona.

---

## Opción 1 — Solo el conocimiento (no necesita Hermes)

Manda estos dos documentos. Se abren en cualquier editor de texto, en Notion, en Google Docs o en Word:

- **`INFORME-programascontabilidad.md`** — el estado del portal: inventario, qué está automatizado y qué falta.
- **`DISENO-agente-autonomo.md`** — cómo iba a funcionar el agente: flujo de 9 pasos, arquitectura, tres modos
  de ejecución, reglas no negociables, fórmula de priorización, plan 30/60/90 y riesgos.

Es la opción correcta si la persona solo necesita entender el proyecto o continuarlo desde otro lado.

---

## Opción 2 — La skill completa (recomendada si va a producir contenido)

Manda **`prog-cont-blog.zip`**. La otra persona:

1. Descomprime el archivo.
2. Copia la carpeta `prog-cont-blog` dentro de su carpeta de skills de Hermes:

   - **Windows:** `C:\Users\<su usuario>\AppData\Local\hermes\skills\`
   - **macOS / Linux:** `~/.hermes/skills/`

3. Reinicia Hermes (o abre una conversación nueva).
4. Comprueba que aparece escribiendo en el chat: `/prog-cont-blog` (o pidiendo "lista mis skills").

**No contiene credenciales.** Verificado: la skill no tiene contraseñas, tokens ni claves. Cada quien usa
su propio conector MCP y sus propias credenciales.

**Lo que la skill NO trae:** los archivos del proyecto (`tracker.md`, `auditoria.json`, las portadas, las
capturas, los scripts de lote). Viven fuera de la skill, en
`C:\Users\ferna\AppData\Local\hermes\prog-cont\`.

Los scripts de lote **no llevan credenciales dentro**: leen el token del conector desde la configuración de
Hermes (`mcp_servers.prog-cont`). Aun así, no se comparten a ciegas: solo funcionan si la otra persona tiene
ese conector dado de alta con sus propias credenciales. Lo que sí hay que pasar es el conector MCP
(`https://programascontabilidad.com/wp-json/mcp/mcp-adapter-default-server`), no el script.

Si el equipo va a usar esto de forma recurrente, lo mejor es publicarlo como *tap* de skills en un repo
privado de GitHub:

```bash
# una vez: subir la carpeta de la skill a un repo con layout  skills/prog-cont-blog/SKILL.md
hermes skills tap add <usuario>/<repo>      # en la máquina del colega
hermes skills install prog-cont-blog        # instala desde ese tap
```

---

## Opción 3 — El agente completo (skills + MCP + tareas programadas + configuración)

Esto copia el entorno entero, no solo una skill. Dos caminos:

### A) Archivo `.tar.gz` (rápido, para una entrega puntual)

```bash
hermes profile export default -o prog-cont-agent.tar.gz
```

Se manda el archivo y la otra persona hace:

```bash
hermes profile import prog-cont-agent.tar.gz
```

**Advertencia importante:** un export **sí incluye** `sessions/`, `memories/`, `MEMORY.md` y `USER.md` —
es decir, historial de conversaciones y notas personales. Las credenciales se filtran por nombre de archivo,
pero el contenido no se revisa. Antes de mandar un export, ábrelo y mira qué lleva dentro.

### B) Distribución por git (duradera, para un equipo)

Es la vía recomendada cuando varias personas van a mantener lo mismo. Se crea un repo con
`distribution.yaml` y un `.gitignore`, y la otra persona instala con:

```bash
hermes profile install github.com/<org>/<repo>
hermes profile update          # para recibir mejoras después
```

Ventaja: **nunca** incluye credenciales (`.env`, `auth.json`), memorias, sesiones ni logs. Cada instalador
pone sus propias claves y conserva sus propias conversaciones.

---

## Resumen

| Quiero compartir… | Mándale | Reversible / seguro |
| --- | --- | --- |
| El estado del proyecto | `INFORME-programascontabilidad.md` | Sí, no tiene nada sensible |
| La forma de trabajar (skill) | `prog-cont-blog.zip` | Sí, sin credenciales |
| Todo el agente tal como está | `hermes profile export` | **Cuidado:** lleva sesiones y memorias |
| Un entorno de equipo con updates | Repo git + `profile install` | Sí, excluye datos personales por diseño |
