"""Avisos del vigía en Google Chat (paso 8 de la guía).

- Un resumen por corrida, con el prefijo del país (`[COL]`, `[MEX]`, `[CRI]`, `[DOM]`).
- Tres colores: 🟢 nada que hacer, 🟡 algo que revisar una persona, 🔴 falló el proceso.
- Cada problema se avisa **una sola vez por día**: el estado de lo enviado queda en
  `paises/<vigía>/avisos-enviados.json`.
- El webhook se lee del entorno y **nunca** se escribe en archivos, commits ni mensajes.
  El nombre que usa el agente diario es `PDC_CHAT_WEBHOOK_URL`; la skill declara
  `GCHAT_WEBHOOK_URL`. Se aceptan los dos, en ese orden de preferencia.
- El envío se confirma por el `name` que devuelve la API de Chat, no por el código 200.
"""
from __future__ import annotations

import json
import os
import urllib.request

RAIZ = os.path.dirname(os.path.abspath(__file__))
PREFIJO = {"col": "[COL]", "mex": "[MEX]", "cri": "[CRI]", "dom": "[DOM]"}
VARIABLES = ("PDC_CHAT_WEBHOOK_URL", "GCHAT_WEBHOOK_URL")
# Lo que una persona tiene que mirar. `sin_cambios` no molesta.
AMARILLO = ("campana", "lectura_dudosa", "estructura_cambiada", "cambio_mercado")
VERDE = ("sin_cambios", "cambio_explicable")


def webhook() -> str | None:
    """URL del espacio de Chat, desde el entorno. Devuelve None si no hay."""
    for nombre in VARIABLES:
        valor = (os.environ.get(nombre) or "").strip()
        if valor:
            return valor
    # El agente diario guarda el webhook en ~/.pdc/chat.env (fuera del repositorio).
    ruta = os.path.join(os.path.expanduser("~"), ".pdc", "chat.env")
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            for linea in f:
                if "=" in linea and not linea.strip().startswith("#"):
                    clave, _, valor = linea.partition("=")
                    if clave.strip() in VARIABLES and valor.strip():
                        return valor.strip()
    return None


def color(resultados: list[dict]) -> str:
    estados = {r.get("resultado") for r in resultados}
    if "falla" in estados:
        return "🔴"
    if estados & set(AMARILLO):
        return "🟡"
    return "🟢"


def armar_mensaje(pais: str, fecha: str, resultados: list[dict], modo: str = "ensayo") -> str:
    """Texto del resumen. Una línea por fuente y un total arriba."""
    prefijo = PREFIJO.get(pais, f"[{pais.upper()}]")
    sin_registro = [r for r in resultados if r.get("resultado") == "sin_registro"]
    con_cambios = [r for r in resultados
                   if r.get("resultado") not in VERDE and r.get("resultado") != "sin_registro"]
    cabeza = f"Modo {modo} · {len(resultados)} fuentes"
    if con_cambios:
        cabeza += f" · {len(con_cambios)} con algo que revisar"
    if sin_registro:
        cabeza += f" · {len(sin_registro)} sin registro todavía"
    if not con_cambios and not sin_registro:
        cabeza += " · todo al día"
    lineas = [f"{color(resultados)} {prefijo} Vigía de precios · {fecha}", cabeza]
    for r in resultados:
        detalle = r.get("motivo") or ""
        if r.get("resultado") == "sin_cambios":
            detalle = f"{r.get('n_sin_cambios', 0)} planes sin cambios"
        elif r.get("resultado") == "cambio_explicable":
            detalle = f"{r.get('n_cambios', 0)} precios cambiaron: " + ", ".join(
                f"{c.get('plan')} {c.get('detalle')}" for c in (r.get("cambios") or [])[:3])
        lineas.append(f"· {r.get('fuente') or r.get('id')}: {r.get('resultado')} — {detalle}".rstrip(" —"))
    if modo == "ensayo":
        lineas.append("Ensayo: no se tocó WordPress.")
    return "\n".join(lineas)


def enviar(texto: str, url: str | None = None, transporte=None) -> dict:
    """Envía al espacio de Chat. El éxito se comprueba por el `name` de la respuesta."""
    url = url or webhook()
    if not url:
        return {"ok": False, "motivo": "no hay webhook configurado"}
    if transporte is None:
        def _post(u, cuerpo):
            peticion = urllib.request.Request(
                u, data=json.dumps({"text": cuerpo}).encode("utf-8"),
                headers={"Content-Type": "application/json; charset=UTF-8"}, method="POST")
            with urllib.request.urlopen(peticion, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8") or "{}")
        transporte = _post
    try:
        respuesta = transporte(url, texto)
    except Exception as e:  # red, 4xx, 5xx
        return {"ok": False, "motivo": str(e).splitlines()[0][:200]}
    nombre = (respuesta or {}).get("name")
    return {"ok": bool(nombre), "name": nombre,
            "motivo": None if nombre else f"la API no devolvió name: {str(respuesta)[:120]}"}


def clave_de(r: dict) -> str:
    """Identidad de un problema, para no avisarlo dos veces el mismo día."""
    detalle = r.get("motivo") or ""
    if r.get("resultado") == "estructura_cambiada":
        detalle = ", ".join(c.get("plan") or "" for c in (r.get("cambios") or [])
                            if c.get("resultado") == "estructura_cambiada")
    return f"{r.get('fuente')}|{r.get('resultado')}|{detalle[:80]}"


def avisar(pais: str, fecha: str, resultados: list[dict], modo: str = "ensayo",
           url: str | None = None, transporte=None, guardar: bool = True,
           estado_path: str | None = None) -> dict:
    """Manda el resumen y deja constancia. Un problema repetido el mismo día no se vuelve a avisar."""
    ruta = estado_path or os.path.join(RAIZ, "paises", pais, "avisos-enviados.json")
    estado = {}
    if os.path.exists(ruta):
        try:
            with open(ruta, encoding="utf-8") as f:
                estado = json.load(f)
        except json.JSONDecodeError:
            estado = {}
    del_dia = estado.get(fecha, {})
    nuevos = [r for r in resultados if clave_de(r) not in del_dia]
    if not nuevos:
        return {"ok": True, "enviado": False, "motivo": "todo avisado ya hoy"}

    texto = armar_mensaje(pais, fecha, resultados, modo)
    salida = enviar(texto, url=url, transporte=transporte)
    if salida["ok"] and guardar:
        del_dia.update({clave_de(r): True for r in nuevos})
        estado[fecha] = del_dia
        # se conservan solo los últimos 30 días
        for vieja in sorted(estado)[:-30]:
            estado.pop(vieja, None)
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(estado, f, ensure_ascii=False, indent=1)
    salida["texto"] = texto
    salida["enviado"] = bool(salida["ok"])
    return salida
