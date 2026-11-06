"""Cliente MCP mínimo sobre HTTP, para publicar sin depender del agente.

Habla JSON-RPC 2.0 contra el endpoint del MCP Adapter de WordPress:

    initialize  ->  (sesión)  ->  tools/call

El servidor exige dos cabeceras después del saludo: `Mcp-Session-Id`, que devuelve al
inicializar, y `MCP-Protocol-Version`, con la versión negociada. Sin la segunda responde
400 con «MCP-Protocol-Version header is required».

Solo usa la biblioteca estándar y recibe un transporte inyectable, así que se puede probar
entero sin red.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

VERSION_PROTOCOLO = "2025-06-18"
HERRAMIENTA_EJECUTAR = "mcp-adapter-execute-ability"


class McpError(RuntimeError):
    """El servidor MCP respondió con un error o con algo ilegible."""


class Transporte(Protocol):
    def request(
        self, method: str, url: str, *, headers: dict[str, str], body: bytes | None
    ) -> tuple[int, dict[str, str], bytes]: ...


class TransporteUrllib:
    def request(self, method, url, *, headers, body):
        peticion = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(peticion, timeout=self.timeout) as respuesta:
                cabeceras = {k.lower(): v for k, v in respuesta.headers.items()}
                return respuesta.status, cabeceras, respuesta.read()
        except urllib.error.HTTPError as error:
            cabeceras = {k.lower(): v for k, v in error.headers.items()}
            return error.code, cabeceras, error.read()

    def __init__(self, timeout: float = 120.0) -> None:
        self.timeout = timeout


def _cuerpo_json(texto: str) -> dict[str, Any]:
    """Acepta JSON plano o SSE (`data: {...}`), que es lo que manda el protocolo."""
    limpio = texto.strip()
    if not limpio:
        raise McpError("respuesta vacía del servidor MCP")

    if limpio.startswith("{"):
        return json.loads(limpio)

    for linea in limpio.splitlines():
        if linea.startswith("data:"):
            trozo = linea[5:].strip()
            if trozo.startswith("{"):
                return json.loads(trozo)

    raise McpError(f"respuesta no reconocida del servidor MCP: {limpio[:200]}")


@dataclass
class ClienteMcp:
    url: str
    headers: Mapping[str, str]
    transporte: Transporte | None = None
    timeout: float = 120.0
    sesion: str = field(default="", init=False)
    version: str = field(default=VERSION_PROTOCOLO, init=False)
    _siguiente_id: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self.transporte = self.transporte or TransporteUrllib(timeout=self.timeout)

    # -- transporte ---------------------------------------------------------------
    def _cabeceras(self, con_sesion: bool) -> dict[str, str]:
        cabeceras = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **{k: v for k, v in self.headers.items()},
        }
        if con_sesion and self.sesion:
            cabeceras["Mcp-Session-Id"] = self.sesion
            cabeceras["MCP-Protocol-Version"] = self.version
        return cabeceras

    def _rpc(self, metodo: str, params: dict[str, Any] | None, *, con_sesion: bool) -> dict:
        self._siguiente_id += 1
        cuerpo = {"jsonrpc": "2.0", "id": self._siguiente_id, "method": metodo}
        if params is not None:
            cuerpo["params"] = params

        estado, cabeceras, bruto = self.transporte.request(
            "POST",
            self.url,
            headers=self._cabeceras(con_sesion),
            body=json.dumps(cuerpo).encode("utf-8"),
        )

        nueva_sesion = (cabeceras or {}).get("mcp-session-id", "")
        if nueva_sesion:
            self.sesion = nueva_sesion

        try:
            datos = _cuerpo_json(bruto.decode("utf-8", "replace"))
        except (json.JSONDecodeError, McpError) as error:
            raise McpError(f"{metodo}: respuesta ilegible ({estado}): {error}") from error

        if estado >= 400 and "error" not in datos:
            raise McpError(f"{metodo}: HTTP {estado} sin error JSON")

        if "error" in datos:
            error = datos["error"]
            mensaje = error.get("message") if isinstance(error, dict) else error
            raise McpError(f"{metodo}: {mensaje}")

        return datos.get("result", {})

    # -- protocolo ----------------------------------------------------------------
    def inicializar(self) -> dict[str, Any]:
        resultado = self._rpc(
            "initialize",
            {
                "protocolVersion": VERSION_PROTOCOLO,
                "capabilities": {},
                "clientInfo": {"name": "pdc-agent", "version": "0.1"},
            },
            con_sesion=False,
        )
        self.version = str(resultado.get("protocolVersion") or VERSION_PROTOCOLO)
        return resultado

    def sesion_iniciada(self, sesion: str) -> None:
        """Fija la sesión que devolvió el servidor en la cabecera del saludo."""
        self.sesion = sesion

    def herramientas(self) -> list[dict[str, Any]]:
        return list(self._rpc("tools/list", {}, con_sesion=True).get("tools") or [])

    def llamar(self, nombre: str, argumentos: dict[str, Any]) -> Any:
        resultado = self._rpc(
            "tools/call",
            {"name": nombre, "arguments": argumentos},
            con_sesion=True,
        )
        return _desenvolver(resultado)

    # -- atajo para el publicador -------------------------------------------------
    def ejecutar(self, ability: str, parametros: dict[str, Any]) -> Any:
        return self.llamar(
            HERRAMIENTA_EJECUTAR, {"ability_name": ability, "parameters": parametros}
        )


def _desenvolver(resultado: Any) -> Any:
    """El MCP envuelve la respuesta en `content`; se devuelve el primer bloque útil."""
    if not isinstance(resultado, dict):
        return resultado

    if resultado.get("isError"):
        textos = [
            c.get("text", "")
            for c in resultado.get("content") or []
            if isinstance(c, dict)
        ]
        raise McpError("la ability falló: " + (" ".join(textos)[:300] or "sin detalle"))

    contenido = resultado.get("content")
    if isinstance(contenido, list) and contenido:
        bloque = contenido[0]
        texto = bloque.get("text") if isinstance(bloque, dict) else None
        if texto:
            try:
                return json.loads(texto)
            except json.JSONDecodeError:
                return texto

    if "structuredContent" in resultado:
        return resultado["structuredContent"]

    return resultado
