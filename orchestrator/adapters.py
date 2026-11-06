"""HTTP adapters for LiteLLM and the WordPress REST API.

Both take an injectable transport so the payloads can be asserted without network or
credentials. The default transport is stdlib urllib: no extra dependency to install on
the Coolify image.

Credentials are read by the caller from the environment; nothing here logs or stores a
token.
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Mapping, Protocol, Sequence


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
        status, raw = self.transport.request(
            "POST",
            f"{self.base_url}/wp-json/wp/v2/posts",
            headers={
                "Authorization": self._auth_header(),
                "Content-Type": "application/json",
            },
            body=json.dumps(dict(payload), ensure_ascii=False).encode("utf-8"),
        )
        text = raw.decode("utf-8", "replace")
        if status >= 400:
            raise RuntimeError(f"WordPress respondió {status} al crear el borrador: {text[:300]}")

        try:
            return json.loads(text)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"respuesta ilegible de WordPress: {error}") from error
