"""HTTP adapters for LiteLLM and the WordPress REST API.

Both take an injectable transport so the payloads can be asserted without network or
credentials. The default transport is stdlib urllib: no extra dependency to install on
the Coolify image.

**Verification status:** unit tested against a fake transport only. Neither adapter has
been run against the live services. Run `scripts/smoke_adapters.py` once IT provides the
credentials, before the first real production run.

Credentials are read by the caller from the environment; nothing here logs or stores a
token.
"""

from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence
from urllib.parse import urlparse


class HttpTransport(Protocol):
    def request(
        self, method: str, url: str, *, headers: Mapping[str, str], body: bytes | None
    ) -> tuple[int, bytes]: ...


class UrllibTransport:
    """Minimal JSON-over-HTTP transport with a hard timeout."""

    def __init__(self, timeout: float = 180.0) -> None:
        self.timeout = timeout

    def request(
        self, method: str, url: str, *, headers: Mapping[str, str], body: bytes | None
    ) -> tuple[int, bytes]:
        request = urllib.request.Request(url, data=body, method=method, headers=dict(headers))
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()


class LiteLlmClient:
    """OpenAI-compatible chat completions, as exposed by the Alegra LiteLLM gateway."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        *,
        transport: HttpTransport | None = None,
        temperature: float = 0.4,
        max_tokens: int | None = None,
        timeout: float = 180.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.transport = transport or UrllibTransport(timeout=timeout)
        self.temperature = temperature
        self.max_tokens = max_tokens

    def complete(self, messages: Sequence[dict[str, str]]) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "temperature": self.temperature,
        }
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens

        status, raw = self.transport.request(
            "POST",
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        )

        text = raw.decode("utf-8", "replace")
        if status >= 400:
            raise RuntimeError(f"el modelo respondió {status}: {text[:300]}")

        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"respuesta ilegible del modelo: {error}") from error

        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("el modelo devolvió una respuesta sin contenido")

        content = (choices[0].get("message") or {}).get("content")
        if not content or not str(content).strip():
            raise RuntimeError("el modelo devolvió contenido vacío")
        return str(content)


class WordPressClient:
    """WordPress REST API with an application token bound to Leandro's user."""

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        username: str = "leandro",
        scheme: str = "basic",
        transport: HttpTransport | None = None,
        timeout: float = 60.0,
    ) -> None:
        if scheme not in {"basic", "bearer"}:
            raise ValueError("scheme debe ser 'basic' o 'bearer'")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.username = username
        self.scheme = scheme
        self.transport = transport or UrllibTransport(timeout=timeout)

    def _auth_header(self) -> str:
        if self.scheme == "bearer":
            return f"Bearer {self.token}"
        pair = f"{self.username}:{self.token}".encode()
        return "Basic " + base64.b64encode(pair).decode()

    def find_by_run_id(self, run_id: str) -> dict[str, Any] | None:
        query = urllib.parse.urlencode(
            {"meta[pdc_run_id]": run_id, "status": "any", "per_page": 1}
        )
        status, raw = self.transport.request(
            "GET",
            f"{self.base_url}/wp-json/wp/v2/posts?{query}",
            headers={"Authorization": self._auth_header(), "Accept": "application/json"},
            body=None,
        )
        text = raw.decode("utf-8", "replace")
        if status >= 400:
            raise RuntimeError(f"WordPress respondió {status} al buscar la corrida: {text[:300]}")

        try:
            found = json.loads(text)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"respuesta ilegible de WordPress: {error}") from error

        if isinstance(found, list) and found:
            return found[0]
        return None

    def create_draft(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._write("POST", "/wp-json/wp/v2/posts", payload)

    # --- superficie del publicador -------------------------------------------------

    def create_post(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._write("POST", "/wp-json/wp/v2/posts", payload)

    def update_post(self, post_id: int, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._write("POST", f"/wp-json/wp/v2/posts/{post_id}", payload)

    def restore(self, post_id: int, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._write("POST", f"/wp-json/wp/v2/posts/{post_id}", payload)

    def find_by_url(self, url: str) -> dict[str, Any] | None:
        slug = urlparse(url).path.strip("/").split("/")[-1]
        if not slug:
            return None
        query = urllib.parse.urlencode({"slug": slug, "status": "any", "per_page": 1})
        status, raw = self.transport.request(
            "GET",
            f"{self.base_url}/wp-json/wp/v2/posts?{query}",
            headers={"Authorization": self._auth_header(), "Accept": "application/json"},
            body=None,
        )
        text = raw.decode("utf-8", "replace")
        if status >= 400:
            raise RuntimeError(f"WordPress respondió {status} al buscar por URL: {text[:300]}")
        try:
            found = json.loads(text)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"respuesta ilegible de WordPress: {error}") from error
        if isinstance(found, list) and found:
            post = found[0]
            rendered = post.get("content")
            if isinstance(rendered, dict):
                post = {**post, "content": rendered.get("rendered", "")}
            return post
        return None

    def read_live(self, url: str) -> dict[str, Any]:
        """Lee la página pública y extrae lo que el readback necesita comparar."""
        status, raw = self.transport.request(
            "GET", url, headers={"Accept": "text/html"}, body=None
        )
        html = raw.decode("utf-8", "replace")

        def grab(pattern: str) -> str:
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""

        return {
            "status_code": status,
            "title": grab(r"<title[^>]*>(.*?)</title>"),
            "h1": grab(r"<h1[^>]*>(.*?)</h1>"),
            "meta_description": grab(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)'),
            "robots": grab(r'<meta[^>]+name=["\']robots["\'][^>]+content=["\']([^"\']*)'),
            "featured_image": grab(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']*)'),
        }

    def _write(self, method: str, path: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        status, raw = self.transport.request(
            method,
            f"{self.base_url}{path}",
            headers={
                "Authorization": self._auth_header(),
                "Content-Type": "application/json",
            },
            body=json.dumps(dict(payload), ensure_ascii=False).encode("utf-8"),
        )
        text = raw.decode("utf-8", "replace")
        if status >= 400:
            raise RuntimeError(f"WordPress respondió {status} al escribir: {text[:300]}")
        try:
            return json.loads(text)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"respuesta ilegible de WordPress: {error}") from error


@dataclass
class AlegraImageClient:
    """Genera la portada con `alegra-image` del gateway, por el endpoint de imágenes.

    No es un modelo de chat: se llama con `/images/generations` y devuelve la imagen en
    base64. Si el gateway devolviera una URL en lugar del contenido, se descarga.
    """

    base_url: str
    api_key: str
    model: str = "alegra-image"
    size: str = "1536x1024"
    output_format: str = "webp"
    quality: str = "high"
    timeout: float = 240.0
    transport: HttpTransport | None = None

    def __post_init__(self) -> None:
        self.transport = self.transport or UrllibTransport(timeout=self.timeout)

    def generate(self, prompt: str) -> bytes:
        payload = {"model": self.model, "prompt": prompt, "size": self.size, "n": 1}
        if self.output_format:
            payload["output_format"] = self.output_format
        if self.quality:
            payload["quality"] = self.quality
        status, raw = self.transport.request(
            "POST",
            f"{self.base_url.rstrip('/')}/images/generations",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        )

        text = raw.decode("utf-8", "replace")
        if status >= 400:
            raise RuntimeError(f"el generador de imágenes respondió {status}: {text[:300]}")

        try:
            data = json.loads(text).get("data") or []
        except json.JSONDecodeError as error:
            raise RuntimeError(f"respuesta ilegible del generador: {error}") from error

        if not data:
            raise RuntimeError("el generador no devolvió ninguna imagen")

        primero = data[0]
        if primero.get("b64_json"):
            return base64.b64decode(primero["b64_json"])

        if primero.get("url"):
            return self._descargar(primero["url"])

        raise RuntimeError("la respuesta no trae b64_json ni url")

    def _descargar(self, url: str) -> bytes:
        status, raw = self.transport.request("GET", url, headers={}, body=None)
        if status >= 400:
            raise RuntimeError(f"no se pudo descargar la imagen: {status}")
        return raw
