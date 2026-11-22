"""Paso 1 del vigía: extrae cada cifra de dinero publicada en PdC y la atribuye a
país, marca, producto, plan y periodo, con un nivel de confianza."""
import json, re, html, collections, os
os.makedirs("salida", exist_ok=True)
from marcas import marcas_en, producto_de
from numeros import valor, moneda_de

posts = json.load(open("raw/posts.json")) + json.load(open("raw/recursos.json"))
U = json.load(open("raw/units.json"))
LOC = {str(k): v for k, v in json.load(open("raw/locale.json")).items()}

# ---------------- dinero ----------------
CUR = r"(?:US\$|USD\s?\$?|RD\$|DOP\s?\$?|MX\$|Mex\$|MXN\s?\$?|COP\s?\$?|CRC\s?|₡|\$|€|S/\.?\s?|B/\.\s?)"
NUM = r"\d{1,3}(?:[.,\s]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?"
SUF = r"(?:USD|MXN|COP|CRC|DOP|EUR|PEN|d[oó]lares|pesos(?: mexicanos| colombianos| dominicanos)?|colones|euros|soles)\b"
MONEY = re.compile(rf"(?P<pre>{CUR})\s?(?P<n1>{NUM})(?:\s?(?P<suf1>{SUF}))?|(?P<n2>{NUM})\s?(?P<suf2>{SUF})")

# ---------------- país ----------------
# El país se reconoce por las señales propias de cada uno (senales-pais.json), de lo más cercano a lo
# más amplio: moneda de la cifra -> frase o fila -> sección -> post -> metadato pdc_target_country.
from pais import puntajes, decidir, senales, EN_ALCANCE as PAISES_VIGIA

MONEDA_PAIS = {"COP": "CO", "MXN": "MX", "CRC": "CR", "DOP": "DO", "EUR": "ES", "PEN": "PE", "PAB": "PA"}
RX_ORACION = re.compile(r"(?<=[.!?;•])\s+")


def oracion(texto, pos):
    ini = 0
    for m in RX_ORACION.finditer(texto):
        if m.end() > pos:
            return texto[ini:m.start()]
        ini = m.end()
    return texto[ini:]


# ---------------- tipo de cifra ----------------
RX_PRECIO = re.compile(r"/\s?mes|al mes|mensual|mes\b|meses|al a[ñn]o|/\s?a[ñn]o|anual|plan\b|planes|licencia|suscripci|precio|cuesta|costo|tarifa|"
                       r"desde|pago|por usuario|usuario adicional|por documento|por factura|timbre|folio|paquete|\+ ?IVA|IVA incluido|"
                       r"m[aá]s IVA|lifetime|perpetua|implementaci|instalaci|mensualidad|cobro|cobra|inversi[oó]n", re.I)
RX_LIMITE = re.compile(r"ingresos|ventas (?:anuales|hasta|de hasta)|facturaci[oó]n (?:anual|hasta)|factures hasta|tope|l[ií]mite de", re.I)
RX_OTRO = re.compile(r"multa|sanci[oó]n|salario|sueldo|\bUVT\b|patrimonio|capital|ahorr|deduc|retenci[oó]n|base gravable|liquidaci|prima|cesant|"
                     r"vacaciones|pr[eé]stamo|cr[eé]dito|vendes|venta de|factura de \$|ticket|impuesto a pagar|ISR de|ITBIS de|IVA de|"
                     r"recargo|inter[eé]s|aportes?|pensi[oó]n|salud|ARL|bono|subsidio|indemniz|utilidad|ganancia|p[eé]rdida|presupuesto|"
                     r"monto|valor de la|costo de oportunidad|horas? de|ejemplo|supongamos|si tu empresa|pierdes|gastando|/hora|por hora|hardware", re.I)

RX_FISCAL = re.compile(r"\bUVT\b|base m[ií]nima|umbral|Resoluci[oó]n|base gravable|retenci[oó]n|ReteFuente|\bISR\b|tarifa marginal|salario|sueldo|multa|sanci[oó]n|pago neto|impuesto|ITBIS|cesant|liquidaci", re.I)
RX_PRECIO_SW = re.compile(r"plan|licencia|suscripci|software|sistema|/\s?mes|mensual|al mes|usuario|precio", re.I)
RX_RANGO = re.compile(r"rango|oscila|entre \$|entre US|entre RD|promedio|pueden? ir|van? de|desde alrededor|aproximad|orientativ|t[ií]picamente|en el mercado|suelen|var[ií]a", re.I)

PLANES = r"Emprendedor|Emprendimiento|Pyme|PYME|Pro|PRO|Plus|PLUS|Inicial|Avanzad[oa]|B[aá]sic[oa]|Premium|Esencial|Starter|Profesional|Empresarial|" \
         r"Ilimitad[oa]|Corporativ[oa]|Est[aá]ndar|Standard|Elite|Gratuito|Gratis|Free|Lite|Micro|Peque[ñn]a|Mediana|Grande|Business|Enterprise|" \
         r"Esencial|Crecimiento|Avance|Full|Total|Online|Nube|Escritorio|Despacho|Contador|Independiente|Facturaci[oó]n|Contabilidad|POS|ERP|N[oó]mina"
RX_PLAN = re.compile(rf"\bplan(?:es)?\s+[«\"“]?([A-ZÁÉÍÓÚ][\wÁÉÍÓÚáéíóúñ+\-]*(?:\s[A-Z0-9][\w+\-]*)?)|\b({PLANES})\b")


def periodo_de(t):
    t = t or ""
    if re.search(r"por (?:documento|factura|comprobante|CFDI|timbre|folio)|timbres|folios|por e-CF", t, re.I):
        return "por_documento"
    if re.search(r"pago [uú]nico|una sola vez|[uú]nica vez|perpetua|de por vida|lifetime", t, re.I):
        return "unico"
    if re.search(r"/\s?mes|al mes|mensual|mes\b|mensualidad", t, re.I):
        return "mensual"
    if re.search(r"al a[ñn]o|/\s?a[ñn]o|anual|anualmente", t, re.I):
        return "anual"
    return None


def slug(s):
    s = (s or "").lower()
    for a, b in zip("áéíóúñ", "aeioun"):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


EN_ALCANCE = PAISES_VIGIA
out = []
resumen_post = {}

for p in posts:
    pid = str(p["id"])
    us = U.get(pid) or U.get(int(pid)) or []
    titulo = html.unescape(p["title"]["rendered"])
    lang = (LOC.get(str(p["id"])) or {}).get("lang") or ""
    pais_meta = lang.split("-")[1] if "-" in lang else None
    texto_post = titulo + " " + " ".join(u["texto"] for u in us)
    sc_post = puntajes(texto_post)
    pais_titulo = decidir(puntajes(titulo), minimo=2)
    pais_p = pais_titulo or decidir(sc_post)
    origen_p = "senales" if pais_p else ("meta" if pais_meta else "sin_senal")
    if pais_p is None and pais_meta:
        pais_p = pais_meta
    secciones = collections.defaultdict(list)
    for u0 in us:
        secciones[u0.get("h2") or ""].append(u0["texto"])
    sc_sec = {k: puntajes(k + " " + " ".join(v)) for k, v in secciones.items()}
    marcas_titulo = list(dict.fromkeys(m for m, _ in marcas_en(titulo)))
    n_post = 0
    for idx, u in enumerate(us):
        texto = u["texto"]
        if not MONEY.search(texto):
            continue
        h = " ".join(x for x in (u.get("h2"), u.get("h3")) if x)
        cab = u.get("cabecera") or []
        ctx_tipo = texto + " " + h + " " + " ".join(cab)
        # sumamos la unidad previa (a veces la cifra viene tras un párrafo que dice de qué marca habla)
        prev = us[idx - 1]["texto"] if idx > 0 else ""
        for mt in MONEY.finditer(texto):
            raw_tok = mt.group(0).strip()
            pre, suf = mt.group("pre"), mt.group("suf1") or mt.group("suf2")
            num = mt.group("n1") or mt.group("n2")
            # descartar falsos positivos: porcentajes, años, números sin moneda real
            if pre is None and suf is None:
                continue
            if re.fullmatch(r"\d{1,2}", num) and (pre or "").strip() == "$" and "%" in texto[mt.end():mt.end() + 2]:
                continue
            moneda = moneda_de(pre, suf)
            # tipo
            a, b = max(0, mt.start() - 90), mt.end() + 70
            ventana = texto[a:b]
            col_head = ""
            celda = None
            if u["tipo"] == "fila":
                # ubicar la celda de la cifra
                pos = 0
                for ci, cel in enumerate(u["celdas"]):
                    if pos <= mt.start() < pos + len(cel) + 3:
                        celda = ci
                        break
                    pos += len(cel) + 3
                if celda is not None and cab and celda < len(cab):
                    col_head = cab[celda]
            ctx_v = ventana + " " + col_head + " " + h
            despues = texto[mt.end():mt.end() + 16].lower()
            pre_w = texto[max(0, mt.start() - 60):mt.start()]
            post_w = texto[mt.end():mt.end() + 40]
            celda_txt = (u["celdas"][celda] if (u["tipo"] == "fila" and celda is not None) else "")
            if re.match(r"\s*(?:millones|mill[oó]n|mil millones|mm\b|m\b)", despues):
                tipo = "limite" if re.search(r"ingres|factur|vent|patrimonio", pre_w + col_head, re.I) else "otro"
            elif RX_FISCAL.search(pre_w[-35:]):
                tipo = "otro"
            elif RX_FISCAL.search(col_head + " " + (u["celdas"][0] if u["tipo"] == "fila" else "") + " " + h) and not RX_PRECIO_SW.search(col_head + " " + pre_w + post_w):
                tipo = "otro"
            elif RX_LIMITE.search(pre_w[-45:] + " " + col_head):
                tipo = "limite"
            elif RX_OTRO.search(pre_w + " " + post_w) and not RX_PRECIO.search(pre_w + " " + post_w + " " + col_head):
                tipo = "otro"
            elif RX_PRECIO.search(ctx_v) or u["tipo"] == "fila":
                tipo = "precio"
            elif RX_OTRO.search(ctx_v):
                tipo = "otro"
            else:
                tipo = "dudoso"
            # país de la cifra
            pais, origen, conf_pais, por = None, None, None, []
            if moneda in MONEDA_PAIS:
                pais, origen, conf_pais, por = MONEDA_PAIS[moneda], "moneda", "alta", [moneda]
            else:
                frase = (texto if u["tipo"] == "fila" else oracion(texto, mt.start()))
                frase = " ".join(x for x in (frase, col_head, u.get("h3") or "") if x)
                p1 = decidir(puntajes(frase), minimo=2)
                p2 = decidir(sc_sec.get(u.get("h2") or "", collections.Counter()))
                p3 = decidir(sc_post)
                if p1:
                    pais, origen, conf_pais, por = p1, "frase", "alta", senales(frase, p1)
                elif p2:
                    pais, origen, conf_pais = p2, "seccion", "media"
                    por = senales((u.get("h2") or "") + " " + " ".join(secciones.get(u.get("h2") or "", [])), p2)
                elif pais_titulo:
                    pais, origen, conf_pais, por = pais_titulo, "titulo", "media", senales(titulo, pais_titulo)
                elif p3:
                    pais, origen, conf_pais, por = p3, "post", "baja", senales(texto_post, p3)
                elif pais_meta:
                    pais, origen, conf_pais, por = pais_meta, "meta", "baja", ["pdc_target_country"]
            conflicto_meta = bool(pais_meta and pais and pais != pais_meta)
            # marca
            marca, conf, via = None, None, None
            if u["tipo"] == "fila":
                cel_txt = u["celdas"][celda] if celda is not None else ""
                m_cel = list(dict.fromkeys(m for m, _ in marcas_en(cel_txt)))
                m_col = list(dict.fromkeys(m for m, _ in marcas_en(col_head)))
                m_fila = list(dict.fromkeys(m for m, _ in marcas_en(texto)))
                m_fila0 = list(dict.fromkeys(m for m, _ in marcas_en(u["celdas"][0])))
                if len(m_col) == 1:
                    marca, conf, via = m_col[0], "alta", "columna"
                elif len(m_cel) == 1:
                    marca, conf, via = m_cel[0], "alta", "celda"
                elif len(m_fila0) == 1:
                    marca, conf, via = m_fila0[0], "alta", "fila"
                elif len(m_fila) == 1:
                    marca, conf, via = m_fila[0], "alta", "fila"
            if marca is None:
                antes = marcas_en(texto[:mt.start()])
                en_texto = list(dict.fromkeys(m for m, _ in marcas_en(texto)))
                if len(en_texto) == 1:
                    marca, conf, via = en_texto[0], "alta", "texto"
                elif antes:
                    marca, conf, via = antes[-1][0], "media", "texto_cercano"
                elif en_texto:
                    marca, conf, via = en_texto[0], "baja", "texto_despues"
            if marca is None:
                for nivel, src in (("h3", u.get("h3")), ("h2", u.get("h2"))):
                    mm = list(dict.fromkeys(m for m, _ in marcas_en(src or "")))
                    if len(mm) == 1:
                        marca, conf, via = mm[0], "media", "encabezado_" + nivel
                        break
            if marca is None:
                mm = list(dict.fromkeys(m for m, _ in marcas_en(prev)))
                if len(mm) == 1:
                    marca, conf, via = mm[0], "media", "parrafo_anterior"
            if marca is None:
                for j in range(idx - 1, max(-1, idx - 7), -1):
                    uj = us[j]
                    if uj.get("h2") != u.get("h2"):
                        break
                    if uj["tipo"] == "fila":
                        continue
                    mm = list(dict.fromkeys(m for m, _ in marcas_en(uj["texto"])))
                    if len(mm) == 1:
                        marca, conf, via = mm[0], "media", "seccion"
                        break
                    if len(mm) > 1:
                        break
            if marca is None and len(marcas_titulo) == 1:
                marca, conf, via = marcas_titulo[0], "baja", "titulo"
            # producto, plan, periodo
            producto = None
            if marca:
                for src_prod in (texto[max(0, mt.start() - 120): mt.end() + 40], col_head, u["celdas"][0] if u["tipo"] == "fila" else "", u.get("h3") or "", u.get("h2") or "", texto):
                    producto = producto_de(marca, src_prod)
                    if producto:
                        break
            plan = None
            if u["tipo"] == "fila":
                c0 = u["celdas"][0]
                if c0 and not MONEY.search(c0) and (celda is None or celda != 0):
                    plan = c0 if len(c0) <= 60 else None
            if plan is None:
                pm = RX_PLAN.search(ventana)
                if pm:
                    plan = (pm.group(1) or pm.group(2))
            periodo = periodo_de(ventana + " " + col_head)
            estimado = bool(RX_RANGO.search(texto[max(0, mt.start() - 120): mt.end() + 60] + " " + col_head))
            if tipo == "precio" and marca is None and estimado:
                tipo = "rango_generico"
            # plan vs concepto
            concepto = None
            if plan and via == "columna":
                concepto, plan = plan, None
                pm = RX_PLAN.search(concepto)
                if pm and re.search(r"\bplan", concepto, re.I):
                    plan = pm.group(1) or pm.group(2)
            pais_ok = pais in EN_ALCANCE
            pendiente = []
            if tipo == "precio":
                if marca is None:
                    pendiente.append("sin_marca")
                if pais is None:
                    pendiente.append("sin_pais")
                if conf == "baja":
                    pendiente.append("marca_baja_confianza")
            v = valor(num, pais)
            out.append({
                "post_id": int(pid), "url": p["link"], "titulo": titulo,
                "post_modificado": (p.get("modified") or "")[:10], "pais_post": pais_p,
                "unidad": idx, "tipo_unidad": u["tipo"], "h2": u.get("h2"), "h3": u.get("h3"),
                "texto_actual": raw_tok, "valor": v, "moneda_leida": moneda,
                "pais": pais, "pais_origen": origen, "pais_confianza": conf_pais, "pais_senales": por[:6],
                "pais_meta": pais_meta, "conflicto_meta": conflicto_meta, "en_alcance": pais_ok,
                "tipo_cifra": tipo, "marca": marca, "marca_confianza": conf, "marca_via": via,
                "producto": producto, "plan": plan, "concepto": concepto, "periodo": periodo, "estimado": estimado,
                "clave_registro": "|".join(slug(x) or "?" for x in (marca, producto or "general", pais, plan)) if marca else None,
                "contexto": texto[max(0, mt.start() - 140): mt.end() + 100],
                "columna": col_head or None,
                "pendiente": pendiente,
            })
            n_post += 1
    resumen_post[pid] = {"titulo": titulo, "url": p["link"], "pais_post": pais_p, "origen": origen_p,
                         "pais_meta": pais_meta, "puntajes": dict(sc_post),
                         "modificado": (p.get("modified") or "")[:10], "cifras": n_post,
                         "categorias": p.get("categories")}

json.dump(out, open("salida/cifras_todas.json", "w"), ensure_ascii=False, indent=1)
json.dump(resumen_post, open("salida/posts_resumen.json", "w"), ensure_ascii=False, indent=1)
c = collections.Counter
print("cifras", len(out))
print("tipo", c(x["tipo_cifra"] for x in out))
pr = [x for x in out if x["tipo_cifra"] == "precio"]
print("precio por pais", c(x["pais"] for x in pr))
print("precio conf", c(x["marca_confianza"] for x in pr))
print("pendientes", c(tuple(x["pendiente"]) for x in pr).most_common(8))
print("pais_post", c(v["pais_post"] for v in resumen_post.values()))
