"""Publicación por el MCP de WordPress.

El MCP no permite buscar un post por meta ni escribir meta al crearlo, así que la
publicación tiene que ser una secuencia con memoria propia. Este módulo la ordena:

    borrador -> meta -> verificación -> publicación

y guarda un mapa `run_id -> post_id` en disco **antes** de crear nada. Si el proceso muere a
mitad de camino, al reanudar encuentra la reserva, busca el borrador por slug y lo adopta en
lugar de duplicarlo.

El transporte no vive aquí: `ejecutar(ability, parametros)` lo inyecta quien tenga acceso a
las herramientas MCP. Así la secuencia y las comprobaciones son deterministas y probables sin
red, y el agente solo aporta la llamada.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from orchestrator.assigner import Brief
from orchestrator.preparacion import IMAGE_CAPTION
from orchestrator.producer import Draft

ROL_AUTOR = 17  # Leandro
ABILITIES = {
    "crear": "ewpa/create-post",
    "actualizar": "ewpa/update-post",
    "meta_escribir": "ewpa/update-post-meta",
    "meta_leer": "ewpa/get-post-meta",
    "obtener": "ewpa/get-post",
    "listar": "ewpa/get-posts",
    "subir_imagen": "ewpa/upload-image",
}

Ejecutor = Callable[[str, dict[str, Any]], Any]


class MapaError(RuntimeError):
    """El mapa de publicaciones no se pudo leer."""


@dataclass
class MapaPublicaciones:
    """Libro propio de `run_id -> post_id`. El MCP no puede hacer esta búsqueda."""

    path: Path

    def _leer(self) -> dict[str, Any]:
        ruta = Path(self.path)
        if not ruta.exists():
            return {}
        try:
            return json.loads(ruta.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise MapaError(f"el mapa de publicaciones está corrupto: {error}") from error

    def _escribir(self, datos: dict[str, Any]) -> None:
        ruta = Path(self.path)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = ruta.with_suffix(".tmp")
        temporal.write_text(
            json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temporal.replace(ruta)

    def obtener(self, run_id: str) -> dict[str, Any]:
        return self._leer().get(run_id, {})

    def reservar(self, run_id: str, slug: str, pais: str) -> None:
        """Deja constancia antes de crear: si algo falla, la reserva queda huérfana."""
        datos = self._leer()
        datos[run_id] = {"post_id": None, "slug": slug, "pais": pais, "estado": "creando"}
        self._escribir(datos)

    def confirmar(self, run_id: str, post_id: int, estado: str) -> None:
        datos = self._leer()
        entrada = datos.setdefault(run_id, {})
        entrada.update({"post_id": post_id, "estado": estado})
        self._escribir(datos)


def _desempaquetar(respuesta: Any) -> Any:
    """El MCP envuelve el resultado en `data`: {"success": true, "data": {...}}."""
    if isinstance(respuesta, dict):
        interior = respuesta.get("data")
        if isinstance(interior, (dict, list)):
            return interior
    return respuesta


def _post_id(respuesta: Any) -> int | None:
    datos = _desempaquetar(respuesta)
    for clave in ("post_id", "id", "ID"):
        valor = datos.get(clave)
        if valor:
            try:
                return int(valor)
            except (TypeError, ValueError):
                continue
    return None


def _resultado(status: str, brief: Brief, **extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "status": status,
        "task_id": brief.task_id,
        "post_id": None,
        "output_url": "",
        "block_reason": "",
    }
    base.update(extra)
    return base


def _buscar_borrador(ejecutar: Ejecutor, slug: str) -> int | None:
    """Busca un borrador con ese slug, para adoptar una reserva huérfana."""
    try:
        encontrados = ejecutar(ABILITIES["listar"], {"status": "draft", "search": slug})
    except Exception:  # noqa: BLE001 - si la consulta falla, se crea igual
        return None

    encontrados = _desempaquetar(encontrados)
    if isinstance(encontrados, dict):
        encontrados = encontrados.get("posts") or encontrados.get("items") or []
    for post in encontrados or []:
        if not isinstance(post, dict):
            continue
        if str(post.get("slug", "")).strip() == slug:
            identificador = _post_id(post)
            if identificador:
                return identificador
    return None


def _leer_meta(ejecutar: Ejecutor, post_id: int, clave: str) -> Any:
    """`get-post-meta` lee una clave por llamada: pide `meta_key` obligatoriamente."""
    respuesta = _desempaquetar(
        ejecutar(ABILITIES["meta_leer"], {"post_id": post_id, "meta_key": clave})
    )
    if isinstance(respuesta, dict):
        meta = respuesta.get("meta")
        if isinstance(meta, dict) and clave in meta:
            return meta[clave]
        for candidata in (clave, "meta_value", "value"):
            if candidata in respuesta:
                return respuesta[candidata]
    return respuesta


def publicar(
    draft: Draft,
    brief: Brief,
    *,
    ejecutar: Ejecutor,
    mapa: MapaPublicaciones,
    portada: bytes | None = None,
    portada_nombre: str = "portada.webp",
    solo_borrador: bool = False,
    post_id: int | None = None,
) -> dict[str, Any]:
    """Publica una pieza por MCP. Nunca deja un post publicado sin `pdc_run_id`."""
    run_id = brief.task_id
    previo = mapa.obtener(run_id)

    if previo.get("post_id") and previo.get("estado") in {"publicado", "borrador_verificado"}:
        return _resultado(
            "DONE",
            brief,
            post_id=previo["post_id"],
            reutilizado=True,
            block_reason="",
        )

    if previo.get("estado") == "creando" and not previo.get("post_id"):
        # Corrida anterior murió antes de guardar el id: puede haber un borrador suelto.
        pass

    # Un reencauche actualiza la pieza que ya existe; no crea una URL nueva.
    post_id = post_id or _buscar_borrador(ejecutar, draft.slug)
    mapa.reservar(run_id, draft.slug, brief.country)

    if post_id is None:
        imagen_id = None
        if portada:
            try:
                subida = ejecutar(
                    ABILITIES["subir_imagen"],
                    {"filename": portada_nombre, "content": portada},
                )
                if isinstance(subida, dict):
                    imagen_id = subida.get("id") or subida.get("attachment_id")
            except Exception:  # noqa: BLE001 - sin portada se puede publicar igual
                imagen_id = None

        argumentos: dict[str, Any] = {
            "title": draft.title,
            "content": draft.html,
            "excerpt": draft.meta_description,
            "status": "draft",
            "slug": draft.slug,
            "author_id": ROL_AUTOR,
        }
        if imagen_id:
            argumentos["featured_image_id"] = imagen_id

        creado = ejecutar(ABILITIES["crear"], argumentos)
        post_id = _post_id(creado)
        if post_id is None:
            return _resultado(
                "FAILED",
                brief,
                block_reason=f"el MCP no devolvió el id del post creado: {creado}",
            )

    mapa.confirmar(run_id, post_id, "borrador_creado")

    metas = {
        "pdc_run_id": run_id,
        "pdc_target_country": brief.country,
        "pdc_estado": "borrador",
        "pdc_focus_keyword": (
            brief.opportunity.focus_keyword if brief.opportunity else ""
        ),
        "pdc_alt_text": draft.alt_text,
    }
    for clave, valor in metas.items():
        try:
            ejecutar(
                ABILITIES["meta_escribir"],
                {"post_id": post_id, "meta_key": clave, "meta_value": valor},
            )
        except Exception as error:  # noqa: BLE001
            return _resultado(
                "FAILED",
                brief,
                post_id=post_id,
                block_reason=f"no se pudo escribir {clave}: {error}. El post quedó en borrador.",
            )

    leido = _leer_meta(ejecutar, post_id, "pdc_run_id")
    if str(leido or "").strip() != run_id:
        return _resultado(
            "FAILED",
            brief,
            post_id=post_id,
            block_reason="la meta no se pudo releer: el post queda en borrador",
        )

    autor = None
    try:
        post = ejecutar(ABILITIES["obtener"], {"post_id": post_id})
        if isinstance(post, dict):
            autor = post.get("author_id") or post.get("post_author") or post.get("author")
    except Exception:  # noqa: BLE001
        post = {}

    if autor is not None and str(autor).strip() not in {str(ROL_AUTOR), "Leandro", ""}:
        return _resultado(
            "FAILED",
            brief,
            post_id=post_id,
            block_reason=f"la firma no es la de Leandro: el post tiene el autor {autor}",
        )

    mapa.confirmar(run_id, post_id, "borrador_verificado")

    if solo_borrador:
        return _resultado(
            "DONE",
            brief,
            post_id=post_id,
            output_url=f"post:{post_id}",
            borrador=True,
        )

    publicado = _desempaquetar(
        ejecutar(ABILITIES["actualizar"], {"post_id": post_id, "status": "publish"})
    )
    enlace = ""
    if isinstance(publicado, dict):
        enlace = str(
            publicado.get("link") or publicado.get("permalink") or publicado.get("url") or ""
        )

    mapa.confirmar(run_id, post_id, "publicado")

    return _resultado("DONE", brief, post_id=post_id, output_url=enlace)
