"""Llamadas al modelo con red: el gateway falla de forma intermitente.

Síntomas que ya hemos visto con el LiteLLM de Alegra, todos con el mismo prompt:

- `200` con contenido vacío (el modelo gastó el presupuesto en razonamiento).
- `504` cuando la generación pasa de ~180 segundos.
- JSON con llaves duplicadas (`{{`) al pedir objetos.
- Respuesta cortada a mitad de una frase.

Este envoltorio no arregla el gateway: hace que el proceso no muera al primer tropiezo.
Recorta lo que se envía, reintenta con otro modelo y limpia lo que vuelve.
"""

from __future__ import annotations

from typing import Any, Sequence

FIN_TEXTO = "[FIN DEL TEXTO EVALUADO]"


class ModeloConReintentos:
    """Envuelve uno o varios clientes y devuelve la primera respuesta usable."""

    def __init__(
        self,
        clientes: Sequence[Any],
        *,
        max_caracteres: int = 12_000,
        intentos_por_modelo: int = 2,
    ) -> None:
        if not clientes:
            raise ValueError("hace falta al menos un cliente")
        self.clientes = list(clientes)
        self.max_caracteres = max_caracteres
        self.intentos_por_modelo = intentos_por_modelo
        self.intentos = 0
        self.ultimo_error = ""

    def _recortar(self, mensajes: list[dict[str, str]]) -> list[dict[str, str]]:
        ajustados = []
        for mensaje in mensajes:
            contenido = mensaje.get("content", "")
            if len(contenido) > self.max_caracteres:
                corte = contenido[: self.max_caracteres]
                # terminar en un cierre de bloque evita que el modelo vea una frase partida
                for marca in ("</p>", "</h2>", "</li>", "\n\n"):
                    posicion = corte.rfind(marca)
                    if posicion > self.max_caracteres * 0.6:
                        corte = corte[: posicion + len(marca)]
                        break
                contenido = corte + "\n\n" + FIN_TEXTO
            ajustados.append({"role": mensaje.get("role", "user"), "content": contenido})
        return ajustados

    @staticmethod
    def _limpiar(texto: str) -> str:
        limpio = texto.strip()
        if limpio.startswith("```"):
            partes = limpio.split("```")
            limpio = partes[1] if len(partes) > 1 else limpio
            limpio = limpio.split("\n", 1)[1] if "\n" in limpio else limpio
        return limpio.replace("{{", "{").replace("}}", "}").strip()

    def complete(self, mensajes: list[dict[str, str]]) -> str:
        ajustados = self._recortar(mensajes)
        for cliente in self.clientes:
            for _ in range(self.intentos_por_modelo):
                self.intentos += 1
                try:
                    crudo = cliente.complete(ajustados)
                except Exception as error:  # noqa: BLE001 - se reporta al final
                    self.ultimo_error = f"{type(error).__name__}: {error}"[:200]
                    continue
                limpio = self._limpiar(crudo or "")
                if limpio:
                    return limpio
                self.ultimo_error = "respuesta vacía"
        raise RuntimeError(
            f"ningún modelo devolvió contenido usable tras {self.intentos} intentos: "
            f"{self.ultimo_error}"
        )
