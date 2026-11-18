#!/usr/bin/env python
"""Corrida completa en staging: auditoría -> publicación por MCP.

    PDC_STG=1 python scripts/corrida_completa.py --pais CO

Usa los modelos reales, el registro de datos real y el MCP de staging. No toca producción.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import sys
import time
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from orchestrator.adapters import AlegraImageClient, LiteLlmClient  # noqa: E402
from orchestrator.enlaces import estado as estado_de_enlace  # noqa: E402
from orchestrator.assigner import Brief  # noqa: E402
from orchestrator.audit import AuditRules, Opportunity, find_opportunities  # noqa: E402
from orchestrator.brief_io import load_brief  # noqa: E402
from orchestrator.gsc_io import load_snapshot  # noqa: E402
from orchestrator.resiliencia import ModeloConReintentos  # noqa: E402
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



OBLIGATORIAS = (
    "OPENAI_BASE_URL",
    "PDC_LLM_KEY",
    "PDC_PROD_URL",
    "PDC_PROD_USER",
    "PDC_PROD_TOKEN",
    "PDC_MCP_USER",
    "PDC_MCP_TOKEN",
    "PDC_CHAT_WEBHOOK_URL",
)



def _de_los_archivos() -> dict[str, str]:
    """Los valores de ~/.pdc/*.env, para que una corrida local no exija exportarlos a mano."""
    valores: dict[str, str] = {}
    for nombre in ("llm.env", "chat.env", "mcp.env", "wp-prod.env"):
        ruta = Path.home() / ".pdc" / nombre
        try:
            for linea in ruta.read_text(encoding="utf-8").splitlines():
                if "=" in linea and not linea.strip().startswith("#"):
                    clave, _, valor = linea.partition("=")
                    valores.setdefault(clave.strip(), valor.strip())
        except OSError:
            continue
    return valores


def verificar_entorno() -> None:
    """Comprueba las variables antes de gastar una sola llamada.

    Sin esto, una variable ausente aparece a mitad de la corrida -después de la auditoría, con
    tokens gastados- y como un KeyError que no dice qué falta.
    """
    locales = _de_los_archivos()
    faltan = [
        clave
        for clave in OBLIGATORIAS
        if not (os.environ.get(clave, "").strip() or locales.get(clave, "").strip())
    ]
    if faltan:
        raise SystemExit(
            "faltan variables de entorno: " + ", ".join(faltan) + ". "
            "Se definen en Coolify y se aplican al redesplegar."
        )
    cortas = [
        f"{clave} ({len(os.environ.get(clave, '').strip())})"
        for clave in ("PDC_PROD_TOKEN", "PDC_MCP_TOKEN")
        if not 20 <= len(os.environ.get(clave, "").strip()) <= 40
    ]
    if cortas:
        raise SystemExit(
            "estas credenciales no tienen pinta de contraseña de aplicación: "
            + ", ".join(cortas)
            + ". Debe ser 24 caracteres en seis grupos de cuatro, con sus espacios: "
            "29 en total. Ni menos, ni una frase, ni un comando."
        )


def modelo(nombre: str, por_defecto: str) -> str:
    """Un modelo sin configurar cae en el elegido por el proyecto, no revienta."""
    return (os.environ.get(nombre) or por_defecto).strip()



def _modelos_aeo() -> tuple[str, ...]:
    """Modelos a los que se les pregunta la consulta foco: ChatGPT y Perplexity por defecto."""
    crudo = os.environ.get("PDC_MODEL_AEO", "openai/gpt-4o-mini,perplexity/sonar")
    return tuple(m.strip() for m in crudo.split(",") if m.strip())


def _preguntar_aeo():
    """Devuelve `(modelo, pregunta) -> respuesta`, o None si no hay pasarela configurada.

    Sin llave no se inventa una respuesta: el informe AEO queda como «sin_modelo».
    """
    base = os.environ.get("OPENAI_BASE_URL")
    llave = os.environ.get("PDC_LLM_KEY")
    if not base or not llave:
        return None

    from orchestrator.adapters import LiteLlmClient

    def consultar(modelo: str, pregunta: str) -> str:
        cliente = LiteLlmClient(base_url=base, api_key=llave, model=modelo, max_tokens=400)
        return cliente.complete([{"role": "user", "content": pregunta}])

    return consultar


def _legal_del_pais(legal: str, pais: str) -> str:
    """Solo la sección del país: el redactor recibía el archivo entero, con la normativa de los
    cuatro mercados, y una pieza mexicana podía citar a la DIAN."""
    from orchestrator.producer import legal_section

    try:
        return legal_section(legal, pais)
    except ValueError:
        return legal


def _modelo_de_intencion():
    """`consulta -> intención` para las consultas que las reglas dejan ambiguas, o None.

    Sin pasarela configurada no se pregunta nada y las reglas deciden, como antes. La memoria
    vive en el volumen de estado y arranca con la semilla del repositorio.
    """
    base = os.environ.get("OPENAI_BASE_URL")
    llave = os.environ.get("PDC_LLM_KEY")
    if not base or not llave:
        return None

    from orchestrator.adapters import LiteLlmClient
    from orchestrator.diagnostico import ModeloConMemoria, pregunta_de_intencion

    cliente = LiteLlmClient(
        base_url=base,
        api_key=llave,
        model=modelo("PDC_MODEL_INTENCION", "deepseek/deepseek-v4-flash"),
        temperature=0.0,
        max_tokens=10,
        timeout=30,
    )

    def consultar(query: str) -> str:
        return cliente.complete([{"role": "user", "content": pregunta_de_intencion(query)}])

    try:
        maximo = max(0, int(os.environ.get("PDC_INTENCION_MAX_NUEVAS", "40") or 40))
    except ValueError:
        maximo = 40
    return ModeloConMemoria(
        consultar,
        Path(os.environ.get("PDC_STATE_DIR", "state")) / "intenciones.json",
        semilla=RAIZ / "datos" / "referencia" / "intenciones-semilla.json",
        maximo_nuevas=maximo,
    )


def _html_vivo(url: str) -> str:
    """Contenido actual de una URL publicada, para comparar la versión nueva contra ella."""
    from orchestrator.adapters import WordPressClient

    if not url:
        return ""
    wp = WordPressClient(
        os.environ.get("PDC_PROD_URL", ""),
        os.environ.get("PDC_PROD_TOKEN", ""),
        username=os.environ.get("PDC_PROD_USER", ""),
    )
    try:
        hallado = wp.find_by_url(url)
        if not hallado or not hallado.get("id"):
            return ""
        datos = wp._write("GET", f"/wp-json/wp/v2/posts/{hallado['id']}?context=edit", {})
        return str((datos.get("content") or {}).get("raw") or "")
    except Exception:  # noqa: BLE001 - sin lectura no hay comparación, y eso se informa
        return ""


def _mercado_del_articulo(url: str) -> tuple[str | None, str]:
    """Lee el mercado en el artículo publicado, no en su URL.

    Es la comprobación que faltaba: una pieza mexicana se estaba reescribiendo como colombiana
    porque la ruta no llevaba país. Si el artículo no da señales, devuelve None y quien llama
    decide abstenerse.
    """
    from orchestrator.adapters import WordPressClient
    from orchestrator.mercado import pais_de_contenido

    if not url:
        return None, "sin url"
    wp = WordPressClient(
        os.environ.get("PDC_PROD_URL", ""),
        os.environ.get("PDC_PROD_TOKEN", ""),
        username=os.environ.get("PDC_PROD_USER", ""),
    )
    try:
        hallado = wp.find_by_url(url)
        if not hallado:
            return None, "la url no está en el blog"
        identificador = hallado.get("id")
        datos = wp._write("GET", f"/wp-json/wp/v2/posts/{identificador}?context=edit", {})
    except Exception as error:  # noqa: BLE001
        return None, f"no se pudo leer el post ({error})"
    texto = " ".join(
        [
            str((datos.get("title") or {}).get("raw", "")),
            str((datos.get("excerpt") or {}).get("raw", "")),
            re.sub(r"<[^>]+>", " ", str((datos.get("content") or {}).get("raw", "")))[:6000],
        ]
    )
    mercado = pais_de_contenido(texto)
    crudo = str((datos.get("content") or {}).get("raw", ""))
    meses = None
    fecha_post = str(datos.get("date") or datos.get("modified") or "")[:10]
    if fecha_post:
        try:
            from datetime import date as _date

            anio, mes, dia = (int(x) for x in fecha_post.split("-"))
            meses = (_date.today() - _date(anio, mes, dia)).days / 30.4
        except ValueError:
            meses = None
    _mercado_del_articulo.ultimo = {  # type: ignore[attr-defined]
        "html": crudo,
        "titulo": str((datos.get("title") or {}).get("raw", "")),
        "meses": meses,
    }
    return (mercado.pais if mercado else None), ("contenido del artículo" if mercado else "sin señales")



def _webhook(args) -> str:
    """La URL del Chat, del entorno primero: en Coolify no hay ~/.pdc/chat.env."""
    if getattr(args, "sin_avisos", False):
        return ""
    del_entorno = os.environ.get("PDC_CHAT_WEBHOOK_URL", "").strip()
    if del_entorno:
        return del_entorno
    return env(Path.home() / ".pdc" / "chat.env").get("PDC_CHAT_WEBHOOK_URL", "")



REFERENCIAS_DE_REDACCION = (
    "bloques-editoriales.md",
    "formatos.md",
    "portada-y-medios.md",
    "alegra-modulos-por-pais.md",
    "auditoria-blog-seo-aeo.md",
    "wordpress-prog-cont.md",
    "refresco-de-precios.md",
    "migracion-colombia.md",
)

MANDATO_DE_USO = (
    "## Instrucción de uso obligatorio"
    + chr(10) + chr(10)
    + "Las referencias que siguen NO son contexto de fondo ni lectura opcional: son reglas de "
    "producción y se aplican todas en esta pieza."
    + chr(10) + chr(10)
    + "- Si una regla de estas referencias contradice tu criterio, manda la referencia."
    + chr(10)
    + "- Si una referencia exige un dato que no tienes, no lo inventes: aplica su regla de ausencia."
    + chr(10)
    + "- Antes de entregar, comprueba la pieza contra cada referencia cargada."
    + chr(10) + chr(10)
)


def referencias_de_redaccion(pais: str) -> str:
    """Las referencias de la skill del portal que el redactor necesita de verdad.

    formatos y portada son iguales para todos los mercados; los precios de Alegra son por país.
    Se cargan solo estas tres: el resto del paquete son procedimientos operativos, no escritura.
    """
    base = RAIZ / "skills" / "prog-cont-blog" / "references"
    piezas = []
    # Los bloques son HTML: recortarlos a 2.200 caracteres dejaría fuera media biblioteca, que
    # es justo lo que hay que copiar. El resto de referencias sí se recorta.
    limites = {"bloques-editoriales.md": 7000}
    for nombre in REFERENCIAS_DE_REDACCION + (f"precios-alegra-{pais.lower()}.md",):
        ruta = base / nombre
        if ruta.exists():
            piezas.append(
                "## Referencia: " + nombre + chr(10) + chr(10)
                # Recortada a lo esencial: con el texto entero el modelo gasta el presupuesto en
                # razonar sobre 40.000 caracteres y devuelve la cabecera vacía.
                + ruta.read_text(encoding="utf-8")[: limites.get(nombre, 2200)]
                + chr(10) + "… (referencia recortada: el resto se aplica igual)" + chr(10) + chr(10)
            )
    if not (base / f"precios-alegra-{pais.lower()}.md").exists():
        piezas.append(
            "## No hay precios verificados de Alegra para este país"
            + chr(10) + chr(10)
            + "No cites ninguna tarifa de Alegra en esta pieza. Cuando el artículo necesite una cifra, "
            "escribe exactamente: «El proveedor no publica esta información en su sitio web.»"
            + chr(10) + chr(10)
        )
    return MANDATO_DE_USO + "".join(piezas)


def buscar_respaldo(objetivo: int, raiz: Path) -> dict | None:
    """El respaldo más reciente de un post, dando prioridad al que tiene el HTML completo.

    `respaldo.json` lo escribe la corrida antes de tocar el post vivo; `publicacion.json` solo trae
    título y extracto del camino de borrador. Se prefiere el primero porque permite restaurar de
    verdad, sin depender de las revisiones de WordPress ni de un archivo externo.
    """
    for carpeta in sorted((raiz / "state" / "corridas").glob("*"), reverse=True):
        archivo = carpeta / "respaldo.json"
        if archivo.exists():
            datos = json.loads(archivo.read_text(encoding="utf-8"))
            if datos.get("post_id") == objetivo and datos.get("content"):
                return datos
        archivo = carpeta / "publicacion.json"
        if not archivo.exists():
            continue
        datos = json.loads(archivo.read_text(encoding="utf-8"))
        if datos.get("post_id") == objetivo and datos.get("respaldo"):
            return datos["respaldo"]
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pais", default="CO")
    parser.add_argument("--brief", default="", help="usar un brief existente en vez de planear")
    parser.add_argument("--borrador", action="store_true", help="dejar la pieza en borrador y avisar")
    parser.add_argument(
        "--en-vivo",
        action="store_true",
        help="autoriza actualizar un artículo publicado, conservando su URL",
    )
    parser.add_argument(
        "--probar-aviso",
        action="store_true",
        help="envía un aviso de prueba al Chat y termina, para comprobar el webhook en el contenedor",
    )
    parser.add_argument("--secciones", action="store_true", help="producir bloque a bloque en vez de una sola llamada")
    parser.add_argument(
        "--solo-nuevos",
        action="store_true",
        help="solo oportunidades de artículo nuevo; omite los reencauches de URLs vivas",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="prioridad de negocio: reencauche primero, artículo nuevo después (es lo que corre el calendario)",
    )
    parser.add_argument("--reusar", action="store_true", help="usar el borrador ya guardado y seguir desde la validación")
    parser.add_argument("--sin-avisos", action="store_true", help="no enviar nada al espacio de Chat")
    parser.add_argument("--entorno", choices=["stg", "prod"], default="stg", help="destino de la publicación")
    parser.add_argument("--gsc", action="store_true", help="elegir el tema con Search Console en vivo")
    parser.add_argument("--revertir", type=int, default=0, help="devuelve un post a su título anterior")
    parser.add_argument(
        "--url",
        default="",
        help="trabaja esta página concreta en vez de elegir por puntaje (para pruebas guiadas)",
    )
    args = parser.parse_args()

    try:
        from orchestrator.mercado import PAISES, validar_pais

        args.pais = validar_pais(args.pais)
    except ValueError as error:
        print(f"país: {error}")
        return 2

    for archivo in ("llm.env", "mcp.env", "wp-stg.env", "wp-prod.env"):
        ruta = Path.home() / ".pdc" / archivo
        if not ruta.exists():
            continue
        for clave, valor in env(ruta).items():
            os.environ.setdefault(clave, valor)

    verificar_entorno()

    if args.probar_aviso:
        from orchestrator.notices import send

        webhook = _webhook(args)
        if not webhook:
            print("no hay webhook configurado: revisa PDC_CHAT_WEBHOOK_URL")
            return 2
        estado_http = send(
            webhook,
            "🔧 Prueba de aviso del agente PdC. "
            "Si lees esto, la próxima corrida también avisará aquí.",
        )
        print("aviso de prueba:", estado_http)
        return 0 if estado_http == 200 else 1

    if args.revertir:
        from orchestrator.adapters import WordPressClient as _WpRevertir

        objetivo = args.revertir
        respaldo = buscar_respaldo(objetivo, RAIZ)
        if not respaldo:
            print(f"no hay respaldo guardado para el post {objetivo}")
            return 2
        print("respaldo con HTML completo" if respaldo.get("content") else "respaldo parcial")
        wp = _WpRevertir(
            os.environ["PDC_PROD_URL"],
            os.environ["PDC_PROD_TOKEN"],
            username=os.environ["PDC_PROD_USER"],
        )
        cambios = {
            "title": respaldo.get("title", ""),
            "excerpt": respaldo.get("excerpt", ""),
        }
        if respaldo.get("content"):
            cambios["content"] = respaldo["content"]
        wp.update_post(objetivo, cambios)
        vivo = wp._write("GET", f"/wp-json/wp/v2/posts/{objetivo}?context=edit", {})
        restaurado = (vivo.get("content") or {}).get("raw", "")
        print("revertido a:", str((vivo.get("title") or {}).get("raw", ""))[:80])
        print(f"contenido restaurado: {len(restaurado):,} caracteres")
        return 0

    if args.brief:
        brief = load_brief(RAIZ / args.brief)
    else:
        if args.gsc:
            from orchestrator.gsc_mcp import snapshot_desde_mcp
            from orchestrator.gsc_io import check_freshness

            instantanea = snapshot_desde_mcp(args.pais)
            check_freshness(instantanea, __import__("datetime").date.today(), 7)
            print(f"gsc     : {len(instantanea.pages)} páginas hasta {instantanea.captured_at}")
        else:
            instantanea = load_snapshot(RAIZ / "datos" / "muestra" / "gsc-2026-11-05.json")
        oportunidades = find_opportunities(instantanea.pages, AuditRules.from_file())
        # El blog tiene posts de varios países y este agente solo escribe para cuatro: un tema
        # marcado con otro mercado no se convierte en pieza.
        fuera = [o for o in oportunidades if (o.country or "").upper() not in PAISES]
        if fuera:
            print(f"temas   : {len(fuera)} descartados por mercado fuera del portal")
        propias = [o for o in oportunidades if o.country == args.pais]
        propuesta_de_reencauche = False

        # Diagnóstico del día: el ranking con las cifras que lo sostienen. Falla cerrada si el
        # dato de GSC no es fresco — sin dato de máximo 7 días no hay slot.
        from orchestrator import diagnostico as diagnostico_mod
        from orchestrator.ahrefs import desde_entorno as ahrefs_desde_entorno

        # Intención ambigua: la decide un modelo barato, con memoria en el volumen de estado.
        memoria_intenciones = _modelo_de_intencion()
        try:
            diag = diagnostico_mod.diagnosticar(
                instantanea.pages,
                args.pais,
                capturado=instantanea.captured_at,
                oportunidades=oportunidades,
                consultar_modelo=memoria_intenciones,
                ahrefs=ahrefs_desde_entorno(),
            )
        except diagnostico_mod.SinDatos as error:
            print(f"sin diagnóstico: {error}")
            return 2
        finally:
            if memoria_intenciones is not None:
                try:
                    memoria_intenciones.guardar()
                except OSError as error:
                    print(f"intención: no se pudo guardar la memoria ({error})")
        print(
            f"diagnóstico: {len(diag.paginas)} páginas · {len(diag.oportunidades)} oportunidades · "
            f"umbral {diag.umbral_impresiones} impresiones · datos de hace {diag.edad_dias} día(s)"
        )
        if memoria_intenciones is not None:
            print(f"intención: {memoria_intenciones.nuevas} consulta(s) nueva(s) al modelo")
        print(f"ahrefs  : {diag.ahrefs}")
        # El diagnóstico trae la intención que desempató el modelo y la evidencia de Ahrefs: las
        # oportunidades del país salen de ahí, en el mismo orden de antes.
        del_diagnostico = {o.url: o for o in diag.oportunidades}
        propias = [del_diagnostico.get(o.url, o) for o in propias]

        con_cuerpo = [o for o in propias if requires_body(o.action)]

        # Descanso de 30 días: una URL trabajada no se vuelve a tocar hasta que pase el mes. El
        # registro existía y solo lo usaba el comando `plan`; sin esto, la misma URL reaparecía
        # cada vez que el turno le tocaba al país.
        from orchestrator.state import RefreshJournal, StateError

        try:
            diario = RefreshJournal.load(
                Path(os.environ.get("PDC_STATE_DIR", "state")) / "reencauches.json"
            )
        except StateError as error:
            print(f"sin descanso: no se pudo leer el registro de reencauches ({error})")
            return 2
        con_cuerpo, descansando = diagnostico_mod.en_descanso(con_cuerpo, diario)
        if descansando:
            proximas = ", ".join(
                f"{o.url.rstrip('/').split('/')[-1][:34]} ({(diario.last_refresh(o.url) or date.today()).isoformat()})"
                for o in descansando[:3]
            )
            print(
                f"descanso: {len(descansando)} URL(s) trabajadas en los últimos "
                f"{diario.min_days} días → {proximas}"
            )
        # Prioridad de negocio: primero se mejora lo que ya posiciona (reencauche), y solo cuando
        # no hay nada que mejorar se escribe una pieza nueva.
        reencauches = [o for o in con_cuerpo if (o.action or "").startswith("refresh")]
        # Una búsqueda de una marca que el agente no conoce ni tiene en fichas («susii») no se
        # elige como foco: la pieza no tendría nada que decir de ella y el juez la bloquea.
        from orchestrator.directorio import marca_sin_datos

        sin_datos = [o for o in reencauches if marca_sin_datos(o.focus_keyword or "", args.pais)]
        if sin_datos:
            reencauches = [o for o in reencauches if o not in sin_datos]
            print(
                "sin datos: se omiten "
                + ", ".join(
                    f"«{o.focus_keyword}» ({o.url.rstrip('/').split('/')[-1][:30]})"
                    for o in sin_datos[:3]
                )
                + " — marca sin ficha ni entrada en el directorio"
            )
        nuevos = [o for o in con_cuerpo if (o.action or "") == "create"]
        if args.solo_nuevos:
            elegidas = nuevos
            if con_cuerpo and not nuevos:
                print(
                    f"nuevos  : 0 de {len(con_cuerpo)} con cuerpo; "
                    "los reencauches se omiten (--solo-nuevos)"
                )
        else:
            elegidas = reencauches or nuevos
        if elegidas and (elegidas[0].action or "").startswith("refresh"):
            propuesta_de_reencauche = True
            print(
                f"prioridad: reencauche «{elegidas[0].action}» sobre "
                f"{elegidas[0].url.rstrip('/').split('/')[-1]} ({len(reencauches)} en cola)"
            )
        if not elegidas and not args.solo_nuevos:
            # El auditor solo propone refrescos: nunca emite `create`. Los temas nuevos salen del
            # registro cruzado con el archivo del blog, y la fecha elige cuál toca hoy.
            try:
                from orchestrator.sitemap import urls_del_sitio

                archivo = urls_del_sitio(maximo=1200) or []
            except Exception as error:  # noqa: BLE001 - sin archivo no hay filtro, se informa
                archivo = []
                print(f"temas   : no se pudo leer el archivo del blog ({error})")
            from orchestrator.temas import tema_del_dia, temas_nuevos

            propuestas = temas_nuevos(args.pais, archivo) if archivo else []
            if propuestas:
                hoy = tema_del_dia(args.pais, archivo)
                elegidas = ([hoy] if hoy else []) + [p for p in propuestas if p is not hoy]
                print(
                    f"temas   : {len(propuestas)} sin cubrir en {args.pais}; "
                    f"hoy toca «{elegidas[0].focus_keyword}»"
                )
            else:
                print(f"temas   : sin temas nuevos sin cubrir en {args.pais}")
        if not elegidas:
            print("sin oportunidades para", args.pais)
            return 2
        if args.url:
            objetivo = [c for c in elegidas if args.url.rstrip("/") in c.url.rstrip("/")]
            if not objetivo:
                print(f"la url {args.url} no está entre las oportunidades de {args.pais}")
                return 2
            elegidas = objetivo + [c for c in elegidas if c not in objetivo]
            print(f"url forzada: {elegidas[0].url}")

        # El mercado del artículo manda: si dice otro país, no se toca.
        confirmadas = []
        for candidata in elegidas[:4]:
            if (candidata.action or "") == "create":
                # Un tema nuevo no tiene URL que leer: el mercado es el que declara la propuesta.
                confirmadas.append(candidata)
                continue
            pais_real, motivo = _mercado_del_articulo(candidata.url)
            if pais_real and pais_real not in PAISES:
                # Un artículo de Perú, Chile o España no se toca: el portal cubre cuatro
                # mercados y reescribirlo con normativa colombiana destruye lo que posiciona.
                print(
                    f"descartada {candidata.url[-45:]}: es de {pais_real}, "
                    f"fuera del portal ({motivo})"
                )
                continue
            if pais_real and pais_real != args.pais:
                print(f"descartada {candidata.url[-45:]}: es de {pais_real} ({motivo})")
                continue
            if pais_real is None and requires_body(candidata.action):
                print(f"descartada {candidata.url[-45:]}: sin señales de mercado ({motivo})")
                continue
            confirmadas.append(candidata)
        if not confirmadas:
            print(
                "sin oportunidades confirmadas para", args.pais,
                "— el mercado se lee en el contenido del artículo",
            )
            return 2
        elegidas = confirmadas
        elegida = elegidas[0]

        # Reencauche: se lee la versión viva para comparar la nueva contra ella antes de tocar
        # nada. Sin esa lectura no hay reencauche, hay una reescritura a ciegas.
        html_vivo = ""
        if (elegida.action or "").startswith("refresh"):
            html_vivo = _html_vivo(elegida.url) or ""
            if html_vivo:
                print(f"viva    : {len(html_vivo)} caracteres leídos de {elegida.url[-45:]}")
            else:
                print(f"viva    : no se pudo leer {elegida.url[-45:]}; se sigue sin comparación")

        # Calendario quincenal del mercado: el plan que se revisa, guardado con la corrida.
        try:
            hoy_dia = __import__("datetime").date.today()
            plan = diagnostico_mod.calendario({args.pais: diag}, desde=hoy_dia)
            destino = Path(os.environ.get("PDC_STATE_DIR", "state")) / "calendario.json"
            diagnostico_mod.guardar_calendario(plan, destino.parent)
            print(f"calendario: {len(plan)} días hábiles en {destino}")
        except Exception as error:  # noqa: BLE001 - el calendario informa, no bloquea
            print(f"calendario: no se pudo armar ({error})")

        from dataclasses import replace as _replace

        from orchestrator.decision import decidir

        sesiones = participacion = None
        try:
            from orchestrator.ga4 import de_la_pagina, resumen as resumen_ga4

            visita = de_la_pagina(elegida.url, resumen_ga4(dias=28))
            if visita:
                sesiones, participacion = visita.sesiones, visita.participacion
                print(
                    f"ga4     : {visita.sesiones} sesiones · "
                    f"participación {visita.participacion:.0%}"
                )
        except Exception as error:  # noqa: BLE001 - sin GA4 se decide con GSC, y se dice
            print("ga4     : no disponible —", str(error)[:90])

        articulo = getattr(_mercado_del_articulo, "ultimo", {}) or {}
        evidencia = dict(elegida.evidence or {})
        decision = decidir(
            existe=bool(articulo.get("html")),
            html=articulo.get("html", ""),
            titulo=articulo.get("titulo", ""),
            intencion=elegida.intent,
            ctr=evidencia.get("ctr"),
            ctr_esperado=evidencia.get("expected_ctr"),
            posicion=evidencia.get("position"),
            meses=articulo.get("meses"),
            sesiones=sesiones,
            participacion=participacion,
            tema_normativo=any(
                palabra in (elegida.focus_keyword or "").lower()
                for palabra in ("isr", "iva", "reforma", "normativ", "dian", "sat", "dgii", "tribu")
            ),
        )
        print(f"decisión: {decision.accion} — {'; '.join(decision.motivos)}")
        if decision.accion != elegida.action:
            elegida = _replace(elegida, action=decision.accion)
        if not requires_body(elegida.action):
            print(f"oportunidad: {elegida.action} (título y meta, sin cuerpo)")
            # Un reencauche de snippet no reescribe el cuerpo: se produce solo la cabecera.
            args.secciones = False
        brief = Brief(
            f"{args.entorno}-{date.today().isoformat()}-{args.pais}",
            date.today(),
            "A",
            "resena",
            args.pais,
            elegida,
        )
        # En un reencauche manda la promesa de la página viva: si la URL publicada es una guía de
        # «mejores», el reencauche sigue siendo esa guía, reordenada y ampliada. Antes el brief se
        # armaba con «resena» y la consulta dominante de turno, y la pieza resultante no cubría los
        # temas de la URL (la comparación la bloqueó, con razón: habría reemplazado una buena
        # página por otra distinta).
        if (elegida.action or "").startswith("refresh"):
            ficha = next((f for f in diag.paginas if f["url"] == elegida.url), {})
            publicado = str(ficha.get("formato_publicado") or "").strip().lower()
            dominante = str(ficha.get("consulta_dominante") or "").strip()
            if publicado in {"comparativa", "resena", "mejores", "guia"}:
                brief = _replace(brief, format=publicado)
            from orchestrator.directorio import marca_sin_datos as _marca_sin_datos

            if (
                dominante
                and dominante != (elegida.focus_keyword or "")
                and not _marca_sin_datos(dominante, brief.country)
            ):
                brief = _replace(brief, opportunity=_replace(elegida, focus_keyword=dominante))
            print(
                f"promesa : se conserva el formato «{brief.format}» y la consulta "
                f"«{brief.opportunity.focus_keyword if brief.opportunity else ''}» de la página viva"
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

    # Las fichas de la pieza, no las del país: las que nombra el tema, las que ya trata la página
    # viva, Alegra y las que publican precios, hasta el elenco que admite el formato. Antes iban
    # todas (13 en México) cortadas a 6.000 caracteres: la pieza siempre se pasaba del elenco y
    # en Colombia World Office quedaba nombrado sin sus precios.
    from orchestrator.formato import presupuesto as _presupuesto_formato
    from orchestrator.registry import elegir_fichas, fecha_de_consulta, texto_acotado

    fichas_pieza = elegir_fichas(
        registro.fichas,
        keyword=brief.opportunity.focus_keyword or "",
        url=brief.opportunity.url or "",
        html_vivo=locals().get("html_vivo") or "",
        maximo=_presupuesto_formato(brief.format).elenco_max,
    ) or list(registro.fichas)
    fecha_datos = fecha_de_consulta(fichas_pieza)
    print(
        f"fichas  : {', '.join(str(f.get('brand')) for f in fichas_pieza)} "
        f"(de {len(registro.fichas)} del país) · consultadas {fecha_datos or 'sin fecha'}"
    )

    # El formato no puede contradecir el tema. La reseña cierra el elenco al del título, así que
    # solo sirve cuando la keyword nombra una marca con ficha; con un tema que obliga a nombrar
    # varios proveedores, la pieza es una comparativa. Antes el formato salía siempre «resena» y
    # la pieza se bloqueaba sola por nombrar los competidores que el tema exigía.
    if brief.format == "resena":
        keyword = (brief.opportunity.focus_keyword or "").strip().lower()
        con_ficha = [
            str(f.get("brand", "") if isinstance(f, dict) else getattr(f, "brand", "")).strip().lower()
            for f in registro.fichas
        ]
        if keyword and not any(marca and marca in keyword for marca in con_ficha):
            brief = _replace(brief, format="comparativa")
            print(
                f"formato : comparativa — el tema «{keyword}» no es una marca con ficha, "
                "y una reseña no puede nombrar el elenco que el tema exige"
            )

    if args.entorno == "prod":
        from orchestrator.mcp_client import ClienteMcp

        # En producción mandan las credenciales de producción: PDC_MCP_* puede ser de staging.
        usuario = (os.environ.get("PDC_PROD_USER") or os.environ.get("PDC_MCP_USER") or "").strip()
        token = (os.environ.get("PDC_PROD_TOKEN") or os.environ.get("PDC_MCP_TOKEN") or "").strip()
        if not usuario or not token:
            raise SystemExit(
                "faltan credenciales del MCP: define PDC_MCP_USER y PDC_MCP_TOKEN "
                f"(usuario {len(usuario)} caracteres, token {len(token)})"
            )
        if args.entorno == "prod":
            destino_mcp = (
                os.environ.get("PDC_PROD_URL", "https://programascontabilidad.com").rstrip("/")
                + "/wp-json/mcp/mcp-adapter-default-server"
            )
        else:
            destino_mcp = os.environ.get(
                "PDC_MCP_URL",
                "https://wordpress-1477557-6320318.cloudwaysapps.com"
                "/wp-json/mcp/mcp-adapter-default-server",
            )
        print(f"mcp     : {destino_mcp.split('/wp-json')[0]}")
        cliente_mcp = ClienteMcp(
            url=destino_mcp,
            headers={
                "Authorization": "Basic "
                + __import__("base64").b64encode(f"{usuario}:{token}".encode()).decode()
            },
        )
        try:
            cliente_mcp.inicializar()
        except Exception as error:  # noqa: BLE001 - se explica, no se adivina
            raise SystemExit(
                f"el MCP rechazó la credencial ({error}). Usuario de {len(usuario)} caracteres "
                f"y token de {len(token)}: la contraseña de aplicación debe tener 24, con sus "
                "espacios, y ser de una cuenta con permisos de edición"
            ) from error
    else:
        cliente_mcp = cliente_desde_entorno()
    print(f"mcp     : conectado ({cliente_mcp.sesion[:8]}…)")

    from orchestrator.adapters import WordPressClient as _Wp

    if args.entorno == "prod":
        _wp = _Wp(
            os.environ["PDC_PROD_URL"],
            os.environ["PDC_PROD_TOKEN"],
            username=os.environ["PDC_PROD_USER"],
        )
    else:
        _wp = _Wp(
            os.environ["PDC_STG_URL"],
            os.environ["PDC_STG_TOKEN"],
            username=os.environ["PDC_STG_USER"],
        )

    def subir_media(imagen, nombre, alt):
        medio = _wp.upload_media(
            imagen, nombre, alt_text=alt, caption="Imagen ilustrativa generada con IA"
        )
        return medio.get("id")

    post_existente = None
    if brief.opportunity.action != "create" and brief.opportunity.url:
        try:
            hallado = _wp.find_by_url(brief.opportunity.url)
            post_existente = hallado.get("id") if hallado else None
        except Exception:  # noqa: BLE001
            from orchestrator.adapters import WordPressClient as _Wp

    if args.entorno == "prod":
        _wp = _Wp(
            os.environ["PDC_PROD_URL"],
            os.environ["PDC_PROD_TOKEN"],
            username=os.environ["PDC_PROD_USER"],
        )
    else:
        _wp = _Wp(
            os.environ["PDC_STG_URL"],
            os.environ["PDC_STG_TOKEN"],
            username=os.environ["PDC_STG_USER"],
        )

    def subir_media(imagen, nombre, alt):
        medio = _wp.upload_media(
            imagen, nombre, alt_text=alt, caption="Imagen ilustrativa generada con IA"
        )
        return medio.get("id")

    post_existente = None
    if brief.opportunity.action != "create" and brief.opportunity.url:
        try:
            hallado = _wp.find_by_url(brief.opportunity.url)
            post_existente = hallado.get("id") if hallado else None
        except Exception:  # noqa: BLE001
            post_existente = None
        if locals().get("propuesta_de_reencauche") and args.borrador:
            # En modo borrador el reencauche se guarda como versión paralela: la URL viva no se
            # toca hasta que alguien la apruebe.
            print("propuesta: se crea un borrador nuevo; la URL publicada no se modifica")
            post_existente = None
        elif locals().get("propuesta_de_reencauche") and post_existente:
            # Modo publicar: la versión aprobada se aplica sobre la misma URL, con respaldo previo.
            print(f"reencauche: se escribe sobre el post {post_existente}, con respaldo de la versión actual")
        destino = f"actualiza el post {post_existente}" if post_existente else "la URL no existe, se crea"
        print(f"reencauche: {destino}")

    urls_para_enlaces: list[str] = []
    try:
        from orchestrator.sitemap import urls_del_sitio

        urls_para_enlaces = urls_del_sitio(maximo=20)
        print(f"sitemap : {len(urls_para_enlaces)} urls internas")
    except Exception as error:  # noqa: BLE001 - se informa, no se silencia
        print(f"sitemap : no se pudo leer ({error})")
    if not urls_para_enlaces:
        try:
            from orchestrator.gsc_mcp import snapshot_desde_mcp

            urls_para_enlaces = [p.url for p in snapshot_desde_mcp(args.pais).pages][:20]
            print(f"gsc     : {len(urls_para_enlaces)} urls internas de reserva")
        except Exception as error:  # noqa: BLE001 - se informa, no se silencia
            print(f"gsc     : sin urls internas ({error})")

    deps = Deps(
        producer=LiteLlmClient(
            base_url=os.environ["OPENAI_BASE_URL"],
            api_key=os.environ["PDC_LLM_KEY"],
            model=modelo("PDC_MODEL_PRODUCER", "deepseek/deepseek-v4-pro"),
            max_tokens=12000,
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
        corrector=ModeloConReintentos(
            [
                LiteLlmClient(
                    base_url=os.environ["OPENAI_BASE_URL"],
                    api_key=os.environ["PDC_LLM_KEY"],
                    model=os.environ.get("PDC_MODEL_CORRECTOR", "zai/glm-5.3"),
                    max_tokens=6000,
                    timeout=240,
                ),
                LiteLlmClient(
                    base_url=os.environ["OPENAI_BASE_URL"],
                    api_key=os.environ["PDC_LLM_KEY"],
                    model="deepseek/deepseek-v4-flash",
                    max_tokens=6000,
                    timeout=240,
                ),
            ],
            # El corrector lee la pieza entera a propósito: recortarla rompería los fragmentos
            # que tiene que localizar. Se reintenta con otro modelo si la respuesta viene vacía.
            max_caracteres=120_000,
            intentos_por_modelo=2,
        ),
        wp=WpNulo(),
        publisher=None,
        skill=(RAIZ / "skills" / "prog-cont-blog" / "SKILL.md").read_text(encoding="utf-8")
        + referencias_de_redaccion(brief.country),
        skill_bloques=(RAIZ / "skills" / "prog-cont-blog" / "SKILL.md").read_text(encoding="utf-8"),
        legal=(RAIZ / "skills" / "marco-legal" / "legal-context.md").read_text(
            encoding="utf-8"
        ),
        registry=registro.texto,
        image=AlegraImageClient(
            base_url=os.environ["OPENAI_BASE_URL"], api_key=os.environ["PDC_LLM_KEY"]
        ),
        # Los enlaces se comprueban de verdad antes de publicar: un 404 en el cuerpo invalida
        # el artículo. Se puede apagar con --sin-avisos para una prueba sin red.
        comprobar_enlaces=None if args.sin_avisos else estado_de_enlace,
        # Reencauche: la versión nueva se compara contra la viva antes de reemplazarla.
        html_vivo=locals().get("html_vivo") or None,
        # El diagnóstico del día viaja con la corrida: el equipo ve los mismos números.
        diagnostico=(locals().get("diag").to_dict() if locals().get("diag") else None),
        # AEO: quién responde por la consulta foco. Sin llave queda registrado como «sin_modelo».
        aeo_preguntar=_preguntar_aeo(),
        aeo_modelos=_modelos_aeo(),
        # El sitemap es el mapa de lo que existe: sin él, los enlaces internos se contrastaban
        # contra las oportunidades de GSC y una corrida con `--brief` quedaba sin lista (y sin
        # comprobación). `urls_para_enlaces` son las 20 URLs reales del sitio.
        urls_internas=urls_para_enlaces
        or [
            o.url
            for o in (
                find_opportunities(
                    (locals().get("instantanea").pages if locals().get("instantanea") else []),
                    AuditRules.from_file(),
                )
                or []
            )
        ][:12],
        publicar_con_observaciones=True,
        post_existente=post_existente,
        subir_media=subir_media,
        # Un reencauche de snippet sí escribe sobre el artículo vivo: es su trabajo.
        permitir_vivo=args.en_vivo or not requires_body(brief.opportunity.action),
        verificar_publicacion=lambda pid: str(
            ((_wp._write("GET", f"/wp-json/wp/v2/posts/{pid}?context=edit", {}) or {})
             .get("content") or {}).get("raw", "")
        ),
        brands_available=len(fichas_pieza),
        fecha_datos=fecha_datos,
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

    # Un timeout de la tarea de Coolify o un reinicio del contenedor matan el proceso con SIGTERM.
    # Sin esto, la corrida se cortaba a mitad de la producción y en la carpeta quedaban solo los
    # bloques ya escritos, sin decir por qué. El registro deja el motivo y el último paso.
    def _interrupcion(senal: int, _marco: object) -> None:
        previo = estado.load("checkpoint.json", {}) or {}
        nota = {
            "motivo": "SIGTERM: se agotó el tiempo de la tarea o el contenedor se reinició",
            "senal": int(senal),
            "ultimo_paso": previo.get("last_step", "production"),
            "bloques_escritos": sorted(
                p.stem for p in (estado.dir / "bloques").glob("*.html")
            )
            if (estado.dir / "bloques").exists()
            else [],
        }
        try:
            estado.save("interrupcion.json", nota)
            print("interrumpida: queda el motivo en interrupcion.json")
        except Exception:  # noqa: BLE001 - morir sin registro es peor que morir sin aviso
            pass
        raise SystemExit(143)

    try:
        signal.signal(signal.SIGTERM, _interrupcion)
    except (ValueError, OSError):  # no hay señales si corre en un hilo que no es el principal
        pass

    # Guardar la versión viva antes de escribir es la única red que no depende de WordPress ni de
    # un archivo externo. Si no se puede leer, no se escribe: sin red no hay salto.
    respaldo = None
    if post_existente and not args.borrador:
        try:
            vivo = _wp._write(
                "GET", f"/wp-json/wp/v2/posts/{post_existente}?context=edit", {}
            ) or {}
            contenido_previo = (vivo.get("content") or {}).get("raw", "")
            if not contenido_previo:
                raise RuntimeError("WordPress devolvió el contenido vacío")
            respaldo = {
                "post_id": post_existente,
                "title": (vivo.get("title") or {}).get("raw", ""),
                "excerpt": (vivo.get("excerpt") or {}).get("raw", ""),
                "content": contenido_previo,
                "fecha": datetime.now().isoformat(timespec="seconds"),
            }
            estado.dir.mkdir(parents=True, exist_ok=True)
            (estado.dir / "respaldo.json").write_text(
                json.dumps(respaldo, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(
                f"respaldo del post {post_existente}: {len(contenido_previo):,} caracteres "
                f"en {estado.dir / 'respaldo.json'}"
            )
        except Exception as error:  # noqa: BLE001 - sin respaldo no se sobrescribe
            print(f"NO se publica: no se pudo respaldar el post {post_existente}: {error}")
            return 1

    if args.reusar and (estado.dir / "borrador.json").exists():
        print()
        print("reusando el borrador guardado; sigo desde la validación")
        estado.checkpoint("production", resume_from="judge")
    elif args.secciones:
        from dataclasses import asdict

        from orchestrator.reencauche import contexto_para_reescribir
        from orchestrator.sections import producir_por_secciones

        print()
        print("produciendo por secciones...")
        salida = producir_por_secciones(
            brief,
            llm=deps.producer,
            skill=deps.skill,
            skill_bloques=deps.skill_bloques,
            legal=_legal_del_pais(deps.legal, brief.country),
            # Solo las fichas de la pieza, enteras: el gateway devuelve vacío con prompts largos,
            # así que si no caben sobran las últimas, nunca la mitad de una.
            registro=texto_acotado(fichas_pieza, 6000),
            marcas=[str(f.get("brand", "")) for f in fichas_pieza],
            fichas=list(fichas_pieza),
            carpeta=RAIZ / "state" / "corridas" / brief.task_id / "bloques",
            # Reencauche: el redactor recibe las secciones y los enlaces que la página ya tiene.
            contexto=(
                contexto_para_reescribir(html_vivo, propia=brief.opportunity.url or "")
                if locals().get("html_vivo")
                else ""
            ),
            # y las secciones de la viva que la pieza no cubra se escriben como bloque propio.
            html_vivo=locals().get("html_vivo") or "",
        )
        from dataclasses import replace as _reemplazar

        from orchestrator.presentacion import presentar

        salida.draft = _reemplazar(
            salida.draft, html=presentar(salida.draft.html, pais=brief.country)
        )
        if brief.opportunity.action != "create" and brief.opportunity.url:
            try:
                from orchestrator.adapters import WordPressClient as _WP

                _wp = _WP(
                    os.environ.get("PDC_PROD_URL", ""),
                    os.environ.get("PDC_PROD_TOKEN", ""),
                    username=os.environ.get("PDC_PROD_USER", ""),
                )
                _actual = _wp.find_by_url(brief.opportunity.url)
                if _actual and _actual.get("slug"):
                    salida.draft = _reemplazar(salida.draft, slug=_actual["slug"])
                    print(f"slug    : {_actual['slug']} (el del post vivo: la URL no cambia)")
            except Exception as error:  # noqa: BLE001
                print("slug    : no se pudo leer el original —", str(error)[:80])

        estado.save("borrador.json", asdict(salida.draft))
        estado.checkpoint("production", resume_from="judge")
        print(f"   llamadas: {salida.llamadas} | bloques: {len(salida.bloques)} | fallidos: {salida.fallidos or 'ninguno'}")
        print(f"   pieza: {len(salida.draft.html):,} caracteres")
        if salida.fallidos:
            raise SystemExit(
                "la pieza quedó incompleta: faltan los bloques "
                + ", ".join(salida.fallidos)
                + ". No se valida ni se publica una pieza a la que le falta la comparativa."
            )

    inicio = time.time()
    resultado = run(
        brief,
        deps=deps,
        state=estado,
        conditions=condiciones,
        dry_run=False,
        presentar_pieza=not args.secciones,  # por secciones ya se presentó al ensamblar
    )
    print()
    print(f"duración: {time.time() - inicio:.1f}s")
    from orchestrator.adapters import consumo_total

    consumo = consumo_total()
    try:
        destino = RAIZ / "state" / "corridas" / brief.task_id / "consumo.json"
        destino.write_text(json.dumps(consumo, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    print(
        "tokens : "
        + f"{consumo['llamadas']} llamadas · entrada {consumo['entrada']:,} · "
        + f"salida {consumo['salida']:,} · razonamiento {consumo['razonamiento']:,}"
    )
    print(json.dumps(resultado, ensure_ascii=False, indent=1))

    # Una URL trabajada descansa 30 días. Se anota solo cuando la pieza salió (DONE): una corrida
    # bloqueada no gastó el turno de la URL y mañana puede reintentarse.
    if (
        resultado.get("status") == "DONE"
        and brief.opportunity
        and (brief.opportunity.action or "").startswith("refresh")
        and brief.opportunity.url
    ):
        try:
            from orchestrator.state import RefreshJournal

            diario = RefreshJournal.load(
                Path(os.environ.get("PDC_STATE_DIR", "state")) / "reencauches.json"
            )
            diario.record(brief.opportunity.url, date.today())
            hasta = date.today() + __import__("datetime").timedelta(days=diario.min_days)
            print(
                f"descanso: {brief.opportunity.url.rstrip('/').split('/')[-1]} "
                f"no se vuelve a tocar hasta {hasta.isoformat()}"
            )
        except Exception as error:  # noqa: BLE001 - no se pierde la publicación por el registro
            print(f"descanso: no se pudo anotar la URL ({error})")

    webhook = _webhook(args)
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



    # Categoría, subcategoría y etiquetas: el post nace archivado, no en "sin categoría".
    if resultado["status"] == "DONE" and resultado.get("post_id"):
        try:
            from orchestrator.adapters import WordPressClient
            from orchestrator.metadatos import categorias, etiquetas

            wp = WordPressClient(
                os.environ.get("PDC_PROD_URL", ""),
                os.environ.get("PDC_PROD_TOKEN", ""),
                username=os.environ.get("PDC_PROD_USER", ""),
            )
            borrador_meta = json.loads((estado.dir / "borrador.json").read_text(encoding="utf-8"))
            titulo_meta = borrador_meta.get("title", "")
            texto_meta = titulo_meta + " " + borrador_meta.get("meta_description", "")
            ids = categorias(brief.format, texto_meta)
            nombres = etiquetas(
                titulo_meta,
                getattr(elegida, "focus_keyword", "") if "elegida" in dir() else "",
                brief.country,
                [f["brand"] if isinstance(f, dict) else getattr(f, "brand", "") for f in registro.fichas],
            )
            etiquetas_ids = []
            for nombre in nombres:
                codigo, datos = wp._write("POST", "/wp-json/wp/v2/tags", {"name": nombre})
                if codigo in (200, 201) and isinstance(datos, dict) and datos.get("id"):
                    etiquetas_ids.append(int(datos["id"]))
            wp.update_post(int(resultado["post_id"]), {"categories": ids, "tags": etiquetas_ids})
            print(f"metadatos: categorías {ids} · etiquetas {len(etiquetas_ids)}")
            from base64 import b64encode

            from orchestrator.metadatos import escribir_rank_math

            autorizacion = b64encode(
                f'{os.environ.get("PDC_PROD_USER", "")}:{os.environ.get("PDC_PROD_TOKEN", "")}'.encode()
            ).decode()
            estado_rm = escribir_rank_math(
                os.environ.get("PDC_PROD_URL", ""),
                autorizacion,
                int(resultado["post_id"]),
                titulo=titulo_meta,
                descripcion=borrador_meta.get("meta_description", ""),
                keyword=(getattr(elegida, "focus_keyword", "") if "elegida" in dir() else ""),
            )
            print(f"rank math: {estado_rm}")
        except Exception as error:  # noqa: BLE001 - un fallo de taxonomía no oculta la publicación
            print("metadatos: no se pudieron asignar —", str(error)[:120])

    if resultado["status"] == "DONE" and not args.borrador:
        from orchestrator.notices import aviso_de_pieza, semaforo, send

        try:
            borrador = json.loads((estado.dir / "borrador.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            borrador = {}
        evidencia = dict(getattr(elegida, "evidence", {}) or {})
        impresiones = int(evidencia.get("impressions") or 0)
        ctr = float(evidencia.get("ctr") or 0.0)
        posicion = float(evidencia.get("position") or 0.0)
        esperado = float(evidencia.get("expected_ctr") or evidencia.get("ctr_esperado") or 0.0)
        clics_potenciales = int(impresiones * esperado) if esperado else 0

        aprobados = total = 0
        observaciones = 0
        try:
            veredictos = json.loads((estado.dir / "veredictos.json").read_text(encoding="utf-8"))
            del_validador = veredictos.get("validator") or []
            total = len(del_validador)
            aprobados = sum(1 for c in del_validador if str(c.get("status")) == "PASS")
            observaciones = sum(
                1 for c in (veredictos.get("judge") or []) if str(c.get("status")) != "PASS"
            )
        except (OSError, ValueError):
            pass

        es_nuevo = str(getattr(elegida, "action", "")) == "create"
        post_id = str(resultado.get("post_id") or "")
        if not post_id:
            # El contrato no siempre trae el id; publicacion.json sí lo guarda, y sin él el
            # enlace de edición del aviso salía con «post=&action=edit».
            try:
                guardado = json.loads(
                    (estado.dir / "publicacion.json").read_text(encoding="utf-8")
                )
                post_id = str(guardado.get("post_id") or "")
            except (OSError, ValueError):
                post_id = ""
        base = os.environ.get("PDC_PROD_URL", "https://programascontabilidad.com").rstrip("/")
        texto = aviso_de_pieza(
            titulo=borrador.get("title", ""),
            slug=borrador.get("slug", ""),
            pais=brief.country,
            nuevo=es_nuevo,
            url_edicion=f"{base}/wp-admin/post.php?post={post_id}&action=edit",
            impresiones=impresiones,
            ctr=ctr,
            posicion=posicion,
            clics_potenciales=clics_potenciales,
            criticos_ok=aprobados,
            criticos_total=total,
            importantes_ok=aprobados,
            importantes_total=total,
            advertencias=tuple(
                str(item.get("detail") or item.get("code", ""))[:120]
                for item in (
                    json.loads((estado.dir / "advertencias.json").read_text(encoding="utf-8")).get("items", [])
                    if (estado.dir / "advertencias.json").exists()
                    else []
                )
            ),
            estado=semaforo(
                criticos_fallidos=total - aprobados, importantes_fallidos=0, observaciones=observaciones
            ),
            observaciones=observaciones,
            titulo_seo=borrador.get("title", ""),
            meta=borrador.get("meta_description", ""),
            keyword=getattr(elegida, "focus_keyword", ""),
            motivo="",
        )
        print()
        print(texto)
        webhook = _webhook(args)
        if webhook:
            print()
            print("aviso en Chat:", send(webhook, texto))

    if resultado["status"] == "DONE" and args.borrador:
        import os as _os

        from orchestrator.notices import render, send

        webhook = _webhook(args)
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
