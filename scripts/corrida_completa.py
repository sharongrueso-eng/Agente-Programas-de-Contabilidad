#!/usr/bin/env python
"""Corrida completa en staging: auditoría -> publicación por MCP.

    PDC_STG=1 python scripts/corrida_completa.py --pais CO

Usa los modelos reales, el registro de datos real y el MCP de staging. No toca producción.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from orchestrator.adapters import AlegraImageClient, LiteLlmClient  # noqa: E402
from orchestrator.assigner import Brief  # noqa: E402
from orchestrator.audit import AuditRules, Opportunity, find_opportunities  # noqa: E402
from orchestrator.brief_io import load_brief  # noqa: E402
from orchestrator.gsc_io import load_snapshot  # noqa: E402
from orchestrator.mcp_client import cliente_desde_entorno  # noqa: E402
from orchestrator.mcp_publish import MapaPublicaciones  # noqa: E402
from orchestrator.producer import requires_body  # noqa: E402
from orchestrator.publisher import PublishConditions  # noqa: E402
from orchestrator.registry import cargar_registro  # noqa: E402
from orchestrator.runner import Deps, RunState, run  # noqa: E402



class JuezConReintentos:
    """El gateway falla de forma intermitente con el juez: vacío, 504 o JSON raro.

    Se intenta hasta tres veces alternando modelos, siempre con el texto recortado. Si una
    respuesta vuelve con llaves duplicadas ({{ en vez de {) se corrige antes de devolverla.
    """

    def __init__(self, clientes, max_caracteres: int = 12000) -> None:
        self.clientes = list(clientes)
        self.max_caracteres = max_caracteres
        self.intentos = 0

    def _recortar(self, mensajes):
        ajustados = []
        for mensaje in mensajes:
            contenido = mensaje["content"]
            if len(contenido) > self.max_caracteres:
                corte = contenido[: self.max_caracteres]
                for marca in ("</p>", "</h2>", "</li>"):
                    posicion = corte.rfind(marca)
                    if posicion > self.max_caracteres * 0.6:
                        corte = corte[: posicion + len(marca)]
                        break
                contenido = corte + chr(10) + chr(10) + "[FIN DEL TEXTO EVALUADO]"
            ajustados.append({"role": mensaje["role"], "content": contenido})
        return ajustados

    def complete(self, mensajes):
        ajustados = self._recortar(mensajes)
        ultimo = "sin respuesta"
        for cliente in self.clientes:
            for _ in range(2):
                self.intentos += 1
                try:
                    crudo = cliente.complete(ajustados).strip()
                except Exception as error:  # noqa: BLE001
                    ultimo = str(error)[:120]
                    continue
                if not crudo:
                    ultimo = "respuesta vacía"
                    continue
                crudo = crudo.replace("{{", "{").replace("}}", "}")
                if crudo.startswith("```"):
                    crudo = crudo.split("```")[1]
                    crudo = crudo.split(chr(10), 1)[1] if chr(10) in crudo else crudo
                return crudo
        raise RuntimeError(f"el juez no respondió tras varios intentos: {ultimo}")


class WpNulo:
    """El borrador lo crea el MCP, no la API: el productor no escribe en el sitio."""

    def find_by_run_id(self, run_id):
        return None

    def create_draft(self, payload):
        return {"id": 0, "link": ""}


def env(ruta: Path) -> dict[str, str]:
    valores: dict[str, str] = {}
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if "=" in linea and not linea.strip().startswith("#"):
            clave, _, valor = linea.partition("=")
            valores[clave.strip()] = valor.strip()
    return valores


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pais", default="CO")
    parser.add_argument("--brief", default="", help="usar un brief existente en vez de planear")
    parser.add_argument("--borrador", action="store_true", help="dejar la pieza en borrador y avisar")
    parser.add_argument("--secciones", action="store_true", help="producir bloque a bloque en vez de una sola llamada")
    parser.add_argument("--reusar", action="store_true", help="usar el borrador ya guardado y seguir desde la validación")
    parser.add_argument("--sin-avisos", action="store_true", help="no enviar nada al espacio de Chat")
    args = parser.parse_args()

    for archivo in ("llm.env", "mcp.env", "wp-stg.env"):
        ruta = Path.home() / ".pdc" / archivo
        if not ruta.exists():
            continue
        for clave, valor in env(ruta).items():
            import os

            os.environ.setdefault(clave, valor)

    if args.brief:
        brief = load_brief(RAIZ / args.brief)
    else:
        instantanea = load_snapshot(RAIZ / "datos" / "muestra" / "gsc-2026-11-05.json")
        oportunidades = find_opportunities(instantanea.pages, AuditRules.from_file())
        elegidas = [
            o
            for o in oportunidades
            if o.country == args.pais and requires_body(o.action)
        ]
        if not elegidas:
            print("sin oportunidades que necesiten cuerpo para", args.pais)
            return 2
        elegida = elegidas[0]
        brief = Brief(
            f"stg-{date.today().isoformat()}-{args.pais}",
            date.today(),
            "A",
            "resena",
            args.pais,
            elegida,
        )

    if brief.opportunity is None:
        print("el brief no tiene oportunidad asignada:", brief.skipped_reason)
        return 2

    print(f"brief   : {brief.task_id} · {brief.format} · {brief.country} · {brief.opportunity.action}")
    print(f"keyword : {brief.opportunity.focus_keyword}")

    registro = cargar_registro(brief.country)
    if not registro.utilizable:
        print("registro no utilizable:", registro.error or "sin fichas del mercado")
        return 2
    print(f"registro: {len(registro.fichas)} ficha(s) de {brief.country}")

    cliente_mcp = cliente_desde_entorno()
    print(f"mcp     : conectado ({cliente_mcp.sesion[:8]}…)")

    deps = Deps(
        producer=LiteLlmClient(
            base_url=os.environ["OPENAI_BASE_URL"],
            api_key=os.environ["PDC_LLM_KEY"],
            model=os.environ["PDC_MODEL_PRODUCER"],
            max_tokens=8000,
            timeout=300,
        ),
        judge=JuezConReintentos([
            LiteLlmClient(
                base_url=os.environ["OPENAI_BASE_URL"],
                api_key=os.environ["PDC_LLM_KEY"],
                model=os.environ.get("PDC_MODEL_JUEZ_RAPIDO", "zai/glm-5.3"),
                max_tokens=8000,
                timeout=240,
            ),
            LiteLlmClient(
                base_url=os.environ["OPENAI_BASE_URL"],
                api_key=os.environ["PDC_LLM_KEY"],
                model="deepseek/deepseek-v4-flash",
                max_tokens=6000,
                timeout=240,
            ),
        ]),
        corrector=LiteLlmClient(
            base_url=os.environ["OPENAI_BASE_URL"],
            api_key=os.environ["PDC_LLM_KEY"],
            model=os.environ.get("PDC_MODEL_CORRECTOR", "zai/glm-5.3"),
            max_tokens=20000,
            timeout=300,
        ),
        wp=WpNulo(),
        publisher=None,
        skill=(RAIZ / "skills" / "leandro" / "SKILL.md").read_text(encoding="utf-8"),
        legal=(RAIZ / "skills" / "leandro" / "references" / "legal-context.md").read_text(
            encoding="utf-8"
        ),
        registry=registro.texto,
        image=AlegraImageClient(
            base_url=os.environ["OPENAI_BASE_URL"], api_key=os.environ["PDC_LLM_KEY"]
        ),
        urls_internas=[
            o.url for o in (find_opportunities(
                load_snapshot(RAIZ / "datos" / "muestra" / "gsc-2026-11-05.json").pages,
                AuditRules.from_file(),
            ) or [])
        ][:12],
        publicar_con_observaciones=True,
        mcp=cliente_mcp,
        mapa=MapaPublicaciones(RAIZ / "state" / "publicados.json"),
        solo_borrador=args.borrador,
    )

    condiciones = PublishConditions(
        approved_fingerprint="",
        current_fingerprint="",
        now=datetime.now(),
        window_start=__import__("datetime").time(0, 0),
        window_end=__import__("datetime").time(23, 59),
        publications_today=0,
        daily_cap=2,
        health_check_ok=True,
    )

    estado = RunState(RAIZ / "state" / "corridas", brief.task_id)

    if args.reusar and (estado.dir / "borrador.json").exists():
        print()
        print("reusando el borrador guardado; sigo desde la validación")
        estado.checkpoint("production", resume_from="judge")
    elif args.secciones:
        from dataclasses import asdict

        from orchestrator.sections import producir_por_secciones

        print()
        print("produciendo por secciones...")
        salida = producir_por_secciones(
            brief, llm=deps.producer, skill=deps.skill, legal=deps.legal, registro=registro.texto
        )
        estado.save("borrador.json", asdict(salida.draft))
        estado.checkpoint("production", resume_from="judge")
        print(f"   llamadas: {salida.llamadas} | bloques: {len(salida.bloques)} | fallidos: {salida.fallidos or 'ninguno'}")
        print(f"   pieza: {len(salida.draft.html):,} caracteres")

    inicio = time.time()
    resultado = run(
        brief, deps=deps, state=estado, conditions=condiciones, dry_run=False
    )
    print()
    print(f"duración: {time.time() - inicio:.1f}s")
    print(json.dumps(resultado, ensure_ascii=False, indent=1))

    webhook = "" if args.sin_avisos else env(Path.home() / ".pdc" / "chat.env").get("PDC_CHAT_WEBHOOK_URL", "")
    if webhook and resultado["status"] != "DONE":
        from orchestrator.notices import render, send

        pasos = resultado.get("steps") or []
        ultimo = pasos[-1] if pasos else {}
        texto = render(
            "corrida_fallida",
            task_id=brief.task_id,
            estado=resultado["status"],
            motivo=resultado.get("block_reason", "sin motivo declarado")[:300],
            paso=ultimo.get("step", "desconocido"),
            carpeta=resultado.get("evidence_url", ""),
        )
        print()
        print("aviso de fallo en Chat:", send(webhook, texto))

    if resultado["status"] == "DONE" and args.borrador:
        import os as _os

        from orchestrator.notices import render, send

        webhook = "" if args.sin_avisos else env(Path.home() / ".pdc" / "chat.env").get("PDC_CHAT_WEBHOOK_URL", "")
        if webhook:
            texto = render(
                "borrador_listo",
                pais=brief.country,
                formato=brief.format.capitalize(),
                keyword=brief.opportunity.focus_keyword,
                post_id=str(resultado.get("post_id", "")),
            )
            codigo = send(webhook, texto)
            print()
            print("aviso Chat:", codigo)

    portada = estado.load("portada.json", {}) or {}
    if portada:
        print()
        print("portada :", json.dumps({k: portada.get(k) for k in ("bytes", "bytes_original", "calidad_webp", "used_fallback")}, ensure_ascii=False))

    return 0 if resultado["status"] == "DONE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
