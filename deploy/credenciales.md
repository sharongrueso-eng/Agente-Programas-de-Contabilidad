# Conectar las credenciales

Guía para IT y para el responsable técnico del sitio. Al final de cada bloque hay una
verificación: si no pasa, no se sigue con la siguiente.

Todo se carga en **Coolify → Variables de entorno**. Nada en el repositorio, nada en un
chat, nada en un documento compartido.

---

## 1. LiteLLM de Alegra

**Quién:** IT.

1. Crear una **llave virtual** para el agente PdC en el LiteLLM de Alegra, con presupuesto
   mensual propio. La llave personal por defecto trae 10 USD al mes, insuficiente para dos
   piezas diarias: pedir un tope real y alerta al 80 %.
2. Confirmar los **nombres exactos de dos modelos**, de familias distintas:
   - `PDC_MODEL_PRODUCER` — el que redacta (el más capaz que el presupuesto permita).
   - `PDC_MODEL_JUDGE` — de otra familia, para que quien juzga no sea quien escribió.
3. Cargar en Coolify:

   | Variable | Valor |
   |---|---|
   | `OPENAI_BASE_URL` | URL del gateway, terminada en `/v1` |
   | `PDC_LLM_KEY` | La llave virtual |
   | `PDC_MODEL_PRODUCER` | Nombre del modelo redactor |
   | `PDC_MODEL_JUDGE` | Nombre del modelo juez |

**Verificación:** una llamada mínima que devuelva texto. Si responde 401, la llave está mal
copiada; si responde 404 en el modelo, el nombre no es el que expone el gateway.

---

## 2. WordPress

**Quién:** responsable técnico del sitio (Fabio, según la wiki).

1. Confirmar que el sitio tiene **HTTPS** y que la autenticación por contraseñas de
   aplicación está habilitada. Algunos plugins de seguridad la bloquean: si es el caso, hay
   que permitirla para el usuario de Leandro.
2. Entrar a `https://programascontabilidad.com/wp-admin/profile.php` **con el usuario de
   Leandro** (ID 17) y generar una **Application Password** llamada `agente-pdc`. Copiar el
   valor que muestra una sola vez.
3. Comprobar que el usuario puede: crear borradores, publicar, subir medios, asignar autor
   y fijar la etiqueta robots de Rank Math.
4. Comprobar que el plugin `custom-plugin-pdc` **expone en REST** los campos que el agente
   escribe: `pdc_run_id`, `pdc_target_country`, `pdc_estado`, `pdc_accion`,
   `pdc_focus_keyword`.

   > Sin esto la idempotencia falla en silencio: el agente escribe la meta, WordPress la
   > guarda, pero la búsqueda por `pdc_run_id` devuelve vacío y la siguiente corrida crea
   > un post duplicado. Se registra con `register_post_meta(..., ['show_in_rest' => true])`.

5. Cargar en Coolify:

   | Variable | Valor |
   |---|---|
   | `PDC_WP_URL` | `https://programascontabilidad.com` |
   | `PDC_WP_TOKEN` | La contraseña de aplicación (con o sin espacios) |
   | `PDC_WP_USER` | `leandro` — el usuario dueño del token |

**Verificación:** consulta de solo lectura al listado de posts del agente. Si devuelve 401,
el token o el usuario están mal; si devuelve 403 con `rest_forbidden`, el usuario no tiene
permiso para leer borradores.

---

## 3. Search Console

**Quién:** IT crea la cuenta de servicio; Growth da el acceso a la propiedad.

Es la ruta crítica y la que más se atasca en otros proyectos. Dos partes:

**a. La cuenta de servicio (IT, en Google Cloud):**
1. En el proyecto de Alegra, habilitar la **Search Console API**.
2. Crear una cuenta de servicio, por ejemplo `pdc-agent@<proyecto>.iam.gserviceaccount.com`.
3. Generar una **clave JSON** y guardarla como secreto de Coolify en
   `GSC_CUENTA_SERVICIO_JSON` (el contenido completo del archivo, en una línea).

**b. El permiso sobre la propiedad (Growth):**
4. En Search Console → Configuración → Usuarios y permisos → Agregar usuario, con el correo
   de la cuenta de servicio y permiso **Restringido** (solo lectura). Aplica a la propiedad
   `sc-domain:programascontabilidad.com`.

**Verificación:** una consulta de un día que devuelva 200. Si devuelve 403, el permiso de la
propiedad no está; si devuelve 404, el sitio no coincide con la propiedad declarada.

> Search Console publica con 2–3 días de retraso. El agente acepta datos de hasta 7 días y
> se detiene si son más viejos: eso es correcto, no es un fallo.

---

## 4. Webhook de Google Chat

**Quién:** quien administre el espacio de PdC.

1. En el espacio → **Apps e integraciones** → **Webhooks** → crear uno llamado
   `Agente PdC`.
2. Copiar la URL y cargarla en `PDC_CHAT_WEBHOOK_URL`.

**Verificación:** llega un mensaje de prueba al espacio. Los avisos salen como la app
«Agente PdC», no desde la cuenta de una persona.

---

## 5. Verificación conjunta

Con las cuatro cargadas, dentro del contenedor:

```bash
python scripts/smoke_adapters.py
```

El script comprueba, en orden y sin escribir en el sitio:

1. LiteLLM responde a una llamada mínima.
2. WordPress responde a una consulta de solo lectura.
3. Search Console devuelve filas de un día reciente.
4. El webhook de Chat acepta un mensaje de prueba (aparecerá en el espacio).

Si falta una variable, sale con código 2 y las nombra sin tocar la red.

Después, la cadena completa sin publicar:

```bash
python scripts/smoke_pipeline.py
```

---

## Lista de comprobación

- [ ] Llave de LiteLLM con presupuesto propio y alerta al 80 %
- [ ] Dos modelos confirmados, de familias distintas
- [ ] Contraseña de aplicación del usuario de Leandro (ID 17)
- [ ] El usuario puede publicar, asignar autor y fijar robots
- [ ] `custom-plugin-pdc` expone las cinco meta en REST
- [ ] Cuenta de servicio con clave JSON y API habilitada
- [ ] La cuenta de servicio es usuario restringido de la propiedad
- [ ] Webhook del espacio creado
- [ ] Las siete variables cargadas en Coolify
- [ ] `smoke_adapters.py` sin fallos
- [ ] `smoke_pipeline.py` termina en DONE
