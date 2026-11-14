"""Respalda un post antes de tocarlo: duplicado en borrador + archivo local.

Dos copias, y en este orden, porque cada una cubre un fallo distinto:

1. **Duplicado en WordPress** (`ewpa/duplicate-post`, borrador, con meta y taxonomías):
   si la escritura sobre el vivo sale mal, la versión anterior sigue dentro del CMS y se
   puede copiar de vuelta desde el editor, sin depender de este equipo.
2. **Archivo local** con contenido y SEO (Rank Math completo): sirve para restaurar por API
   y para comparar después qué cambió, sin volver a leer el sitio.

El duplicado se crea **antes** de escribir el archivo: si el proceso muere entre los dos
pasos, existe la copia que de verdad importa (la que vive junto al original).

Uso:
    python scripts/respaldar_post.py --post 5309 --entorno prod
    python scripts/respaldar_post.py --post 5309 --entorno prod --sin-duplicado
    python scripts/respaldar_post.py --post 5309 --entorno prod --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from orchestrator.mcp_client import McpError, cliente_desde_entorno  # noqa: E402

ENTORNOS = {
    "prod": ("PDC_PROD", Path.home() / ".pdc" / "wp-prod.env"),
    "stg": ("PDC_MCP", Path.home() / ".pdc" / "mcp.env"),
}

RUTA_MCP = "/wp-json/mcp/mcp-adapter-default-server"
DESTINO = RAIZ / "state" / "respaldos"


def cargar_entorno(archivo: Path) -> None:
    """Vuelca el `.env` en el proceso. No imprime nada: el archivo tiene el token."""
    if not archivo.exists():
        raise SystemExit(f"no existe {archivo}")
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        limpia = linea.strip()
        if not limpia or limpia.startswith("#") or "=" not in limpia:
            continue
        clave, _, valor = limpia.partition("=")
        os.environ.setdefault(clave.strip(), valor.strip())


def endpoint(prefijo: str) -> str:
    base = os.environ.get(f"{prefijo}_URL", "").strip().rstrip("/")
    if not base:
        raise SystemExit(f"falta {prefijo}_URL")
    return base if "wp-json" in base else base + RUTA_MCP


def _desenvolver(respuesta):
    """El adaptador envuelve todo en `{"success": true, "data": {...}}`."""
    if isinstance(respuesta, dict) and isinstance(respuesta.get("data"), (dict, list)):
        return respuesta["data"]
    return respuesta


def leer_post(cliente, post_id: int) -> dict:
    respuesta = _desenvolver(cliente.ejecutar("ewpa/get-post", {"post_id": post_id}))
    if isinstance(respuesta, dict) and isinstance(respuesta.get("post"), dict):
        return respuesta["post"]
    return respuesta if isinstance(respuesta, dict) else {}


def leer_seo(cliente, post_id: int) -> dict:
    try:
        respuesta = _desenvolver(cliente.ejecutar("ewpa/get-rankmath", {"post_id": post_id}))
    except McpError as error:
        return {"error": str(error)}
    return respuesta if isinstance(respuesta, dict) else {}


def duplicar(cliente, post_id: int, titulo: str, fecha: str) -> dict:
    """Copia exacta en borrador, con meta y taxonomías. Devuelve id y enlace de edición."""
    respuesta = cliente.ejecutar(
        "ewpa/duplicate-post",
        {
            "post_id": post_id,
            "title": f"{titulo} — respaldo {fecha}",
            "status": "draft",
            "copy_meta": True,
            "copy_terms": True,
        },
    )
    datos = respuesta.get("data") if isinstance(respuesta, dict) else None
    if isinstance(datos, dict):
        respuesta = datos
    if not isinstance(respuesta, dict):
        return {"error": f"respuesta inesperada: {str(respuesta)[:200]}"}

    nuevo = respuesta.get("new_post_id") or respuesta.get("post_id") or respuesta.get("id")
    enlace = respuesta.get("edit_url") or respuesta.get("edit_link") or ""
    if not nuevo:
        return {"error": f"sin id nuevo en la respuesta: {list(respuesta)[:8]}"}
    if not enlace:
        base = os.environ.get("PDC_PROD_URL", "").rstrip("/")
        enlace = f"{base}/wp-admin/post.php?post={nuevo}&action=edit"
    return {"id": int(nuevo), "edit_url": str(enlace), "status": "draft"}


def respaldo_previo(post_id: int) -> dict | None:
    """Un respaldo ya hecho para ese post se reutiliza: no se apilan copias en el CMS."""
    for archivo in sorted(DESTINO.glob(f"post-{post_id}-*.json"), reverse=True):
        try:
            datos = json.loads(archivo.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if (datos.get("duplicado") or {}).get("id"):
            return datos
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Respalda un post antes de tocarlo.")
    parser.add_argument("--post", type=int, required=True)
    parser.add_argument("--entorno", choices=sorted(ENTORNOS), default="prod")
    parser.add_argument("--sin-duplicado", action="store_true", help="solo el archivo local")
    parser.add_argument("--dry-run", action="store_true", help="lee y no escribe nada")
    args = parser.parse_args(argv)

    prefijo, archivo_env = ENTORNOS[args.entorno]
    cargar_entorno(archivo_env)
    os.environ[f"{prefijo}_URL"] = endpoint(prefijo)

    cliente = cliente_desde_entorno(prefijo)

    post = leer_post(cliente, args.post)
    if not post.get("post_content"):
        print(json.dumps({"status": "FAILED", "motivo": "el post llegó vacío"}, ensure_ascii=False))
        return 2

    seo = leer_seo(cliente, args.post)
    titulo = str(post.get("post_title") or "")
    contenido = str(post.get("post_content") or "")
    fecha = datetime.now().strftime("%Y%m%d-%H%M")
    huella = hashlib.sha256(contenido.encode("utf-8")).hexdigest()

    datos = {
        "post_id": args.post,
        "entorno": args.entorno,
        "respaldo_de": datetime.now().isoformat(timespec="seconds"),
        "url_publica": post.get("permalink") or "",
        "estado": post.get("post_status") or "",
        "slug": post.get("post_slug") or "",
        "titulo": titulo,
        "autor": post.get("post_author") or "",
        "fecha_publicacion": post.get("post_date") or "",
        "modificado": post.get("post_modified") or "",
        "excerpt": post.get("post_excerpt") or "",
        "categorias": post.get("categories") or [],
        "etiquetas": post.get("tags") or [],
        "imagen_destacada": post.get("featured_image") or "",
        "contenido_chars": len(contenido),
        "contenido_sha256": huella,
        "contenido": contenido,
        "seo": seo,
    }

    resumen = {
        "post_id": args.post,
        "estado": datos["estado"],
        "titulo": titulo,
        "url": datos["url_publica"],
        "contenido_chars": len(contenido),
        "sha256": huella[:16],
        "seo_titulo": seo.get("titulo_seo") or "",
        "seo_descripcion_chars": len(str(seo.get("descripcion_seo") or "")),
        "keyword": seo.get("keywords") or "",
        "robots": seo.get("robots") or [],
    }

    if args.dry_run:
        print(json.dumps({"status": "DRY_RUN", **resumen}, ensure_ascii=False, indent=2))
        return 0

    # 1. La copia que vive junto al original, primero.
    previo = respaldo_previo(args.post)
    if previo and not args.sin_duplicado:
        datos["duplicado"] = previo["duplicado"]
        resumen["duplicado"] = previo["duplicado"]
        resumen["duplicado_nota"] = "ya existía; no se crea otra copia"
    elif not args.sin_duplicado:
        duplicado = duplicar(cliente, args.post, titulo, fecha)
        datos["duplicado"] = duplicado
        resumen["duplicado"] = duplicado

    # 2. El archivo con contenido y SEO.
    DESTINO.mkdir(parents=True, exist_ok=True)
    ruta = DESTINO / f"post-{args.post}-{fecha}.json"
    temporal = ruta.with_suffix(".tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporal.replace(ruta)
    resumen["archivo"] = str(ruta)
    resumen["archivo_chars"] = ruta.stat().st_size

    if (datos.get("duplicado") or {}).get("error"):
        resumen["status"] = "PARCIAL"
    else:
        resumen["status"] = "DONE"
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    return 0 if resumen["status"] == "DONE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
