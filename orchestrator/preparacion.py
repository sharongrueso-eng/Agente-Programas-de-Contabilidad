"""Preparación: imagen destacada hiperrealista y caption obligatorio.

La imagen nunca detiene la publicación: si el modelo falla dos veces se usa la de respaldo
del país y el reporte lo marca para reemplazo. Lo que sí es obligatorio es el texto
alternativo y el pie de imagen generada con IA.
"""

from __future__ import annotations

from typing import Protocol

from orchestrator.assigner import Brief
from orchestrator.producer import Draft

IMAGE_CAPTION = "Imagen ilustrativa generada con IA"

COUNTRY_NAMES = {
    "CO": "Colombia",
    "MX": "México",
    "CR": "Costa Rica",
    "DO": "República Dominicana",
}

COUNTRY_SETTINGS = {
    "CO": "una oficina de una empresa pequeña en Bogotá, Colombia, con luz natural de mediodía",
    "MX": "un despacho contable en Ciudad de México, México, con luz natural de mañana",
    "CR": "una oficina administrativa pequeña en San José, Costa Rica, con luz natural de tarde",
    "DO": "una oficina de servicios en Santo Domingo, República Dominicana, con luz natural cálida",
}

FORMAT_SCENES = {
    "resena": "un contador revisando documentos y facturas en pantalla",
    "comparativa": "dos personas comparando reportes impresos sobre una mesa de trabajo",
    "mejores": "un equipo pequeño revisando opciones de software frente a una pantalla",
}


class ImageClient(Protocol):
    def generate(self, prompt: str) -> bytes: ...


def build_image_prompt(draft: Draft, brief: Brief) -> str:
    """Arma el prompt de la portada. El país manda la ambientación."""
    if not draft.alt_text.strip():
        raise ValueError("la imagen destacada necesita texto alternativo antes de generarse")

    name = COUNTRY_NAMES.get(brief.country)
    setting = COUNTRY_SETTINGS.get(brief.country)
    if name is None or setting is None:
        raise ValueError(f"mercado sin ambientación de imagen definida: {brief.country}")

    scene = FORMAT_SCENES.get(brief.format, FORMAT_SCENES["resena"])

    return (
        f"Fotografía hiperrealista de tipo editorial, formato 16:9, {setting}. "
        f"Plano medio de {scene}. "
        "Estilo documental, luz natural, profundidad de campo suave, colores realistas. "
        "Sin texto en la imagen, sin logos, sin marcas de agua, sin capturas de pantalla "
        "de software y sin personas identificables ni figuras públicas. "
        f"El tema es: {draft.alt_text}. "
        "La composición deja espacio limpio en el tercio izquierdo para el título."
    )


def generate_image(
    client: ImageClient,
    prompt: str,
    *,
    fallback: bytes,
    retries: int = 2,
) -> tuple[bytes, bool]:
    """Intenta generar la imagen; si falla todas las veces, devuelve la de respaldo."""
    for _ in range(max(1, retries)):
        try:
            return client.generate(prompt), False
        except Exception:  # noqa: BLE001 - cualquier fallo del modelo es un reintento
            continue

    return fallback, True


def comprimir_portada(datos: bytes, *, max_kb: int = 300) -> tuple[bytes, int]:
    """Recomprime el WebP del gateway hasta que entre en `max_kb`.

    Devuelve los bytes y la calidad usada (0 si no hubo que tocar nada o si Pillow no
    está instalado). Nunca engorda el archivo: si ya cabe, se devuelve tal cual.
    """
    if not datos or len(datos) <= max_kb * 1024:
        return datos, 0

    try:
        import io

        from PIL import Image
    except ModuleNotFoundError:
        return datos, 0

    try:
        with Image.open(io.BytesIO(datos)) as original:
            imagen = original.convert("RGB")
    except Exception:  # noqa: BLE001 - si no es una imagen válida, se sube como venga
        return datos, 0

    for calidad in (88, 82, 74, 66, 58, 50, 42, 34):
        buffer = io.BytesIO()
        imagen.save(buffer, format="WEBP", quality=calidad, method=6)
        if buffer.tell() <= max_kb * 1024:
            return buffer.getvalue(), calidad

    # Último recurso: reducir el lado mayor y volver a intentar.
    for lado in (1280, 1100, 900):
        copia = imagen.copy()
        copia.thumbnail((lado, lado))
        buffer = io.BytesIO()
        copia.save(buffer, format="WEBP", quality=70, method=6)
        if buffer.tell() <= max_kb * 1024:
            return buffer.getvalue(), 70

    return datos, 0
