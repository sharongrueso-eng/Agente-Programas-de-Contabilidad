"""Arma los archivos del paso 1 para el repositorio: ubicaciones, fuentes y pendientes."""
import json, re, collections
from urllib.parse import urlparse
from marcas import MARCAS

X = json.load(open("salida/cifras_todas.json"))
ps = {p["id"]: p for p in json.load(open("raw/posts.json"))}
HOY = "2026-11-18"
RED = {int(k): v for k, v in json.load(open("raw/redirects.json")).items()}
EN = {"CO", "MX", "DO", "CR"}

# ---------- ubicaciones ----------
ubic = []
for x in X:
    if x["tipo_cifra"] not in ("precio", "limite") or not x["en_alcance"] or not x["marca"]:
        continue
    if x["marca_confianza"] == "baja":
        continue
    ubic.append({
        "post_id": x["post_id"], "url": x["url"], "pais": x["pais"],
        "marca": x["marca"], "producto": x["producto"], "plan": x["plan"], "concepto": x["concepto"],
        "periodo": x["periodo"], "tipo_cifra": x["tipo_cifra"],
        "texto_actual": x["texto_actual"], "valor": x["valor"], "moneda_leida": x["moneda_leida"],
        "clave_registro": x["clave_registro"], "confianza": x["marca_confianza"], "via": x["marca_via"],
        "estimado": x["estimado"], "alegra_hoy": x["alegra_hoy"],
        "pais_origen": x["pais_origen"], "pais_confianza": x["pais_confianza"], "pais_senales": x["pais_senales"],
        "conflicto_meta": x["conflicto_meta"],
        "contexto": x["contexto"], "seccion": x["h3"] or x["h2"],
        "estado_url": RED.get(x["post_id"], {}).get("code"),
        "redirige_a": RED.get(x["post_id"], {}).get("to") or None,
    })
import os
from pais import VIGIAS
NOTA = "Las cifras salen del HTML renderizado. El actualizador debe buscarlas en content.raw (Gutenberg) antes de reemplazar."
for p_, v_ in VIGIAS.items():
    if v_:
        os.makedirs(f"salida/paises/{v_}", exist_ok=True)


def guardar(pais_, nombre, clave, datos, extra=None):
    d = {"generado": HOY, "pais": pais_, "vigia": VIGIAS[pais_]}
    d.update(extra or {})
    d[clave] = datos
    json.dump(d, open(f"salida/paises/{VIGIAS[pais_]}/{nombre}.json", "w"), ensure_ascii=False, indent=1)


for p_ in [k for k, v in VIGIAS.items() if v]:
    guardar(p_, "ubicaciones", "ubicaciones", [u for u in ubic if u["pais"] == p_],
            {"fuente": "API pública de WordPress (content.rendered), 343 posts + 1 recurso", "nota": NOTA})

# ---------- pendientes ----------
pend = []
for x in X:
    motivo = None
    if x["tipo_cifra"] == "precio" and x["pais"] in EN:
        if not x["marca"]:
            motivo = "sin_marca"
        elif x["marca_confianza"] == "baja":
            motivo = "marca_baja_confianza"
    if x["tipo_cifra"] == "precio" and (x["pais"] is None):
        motivo = "sin_pais"
    if x["tipo_cifra"] == "dudoso" and x["pais"] in EN:
        motivo = "tipo_dudoso"
    if motivo:
        pend.append({"motivo": motivo, "post_id": x["post_id"], "url": x["url"], "pais": x["pais"],
                     "marca_propuesta": x["marca"], "texto_actual": x["texto_actual"],
                     "contexto": x["contexto"], "seccion": x["h3"] or x["h2"]})
rangos = [{"post_id": x["post_id"], "url": x["url"], "pais": x["pais"], "texto_actual": x["texto_actual"],
           "contexto": x["contexto"]} for x in X if x["tipo_cifra"] == "rango_generico" and x["pais"] in EN]
fuera = collections.Counter(x["pais"] for x in X if x["tipo_cifra"] == "precio" and x["pais"] in ("PE", "PA", "ES"))
for p_ in [k for k, v in VIGIAS.items() if v]:
    guardar(p_, "pendientes", "pendientes", [x for x in pend if x["pais"] == p_],
            {"rangos_de_mercado_sin_marca": [r for r in rangos if r["pais"] == p_]})
conflictos = {}
for x in X:
    if x.get("conflicto_meta") and x["tipo_cifra"] == "precio":
        c_ = conflictos.setdefault(x["post_id"], {"url": x["url"], "pais_meta": x["pais_meta"], "paises_por_senales": collections.Counter()})
        c_["paises_por_senales"][x["pais"]] += 1
json.dump({"generado": HOY,
           "nota": "Cifras de precio a las que no se les pudo reconocer el país. Asignarlas a mano o agregar la señal que falte en senales-pais.json.",
           "sin_pais": [p for p in pend if p["motivo"] == "sin_pais"],
           "fuera_de_alcance_por_pais": dict(fuera),
           "metadato_pais_en_conflicto": {str(k): {**v, "paises_por_senales": dict(v["paises_por_senales"])} for k, v in conflictos.items()}},
          open("salida/sin-pais.json", "w"), ensure_ascii=False, indent=1)

# ---------- fuentes ----------
links = collections.defaultdict(list)
for pid, p in ps.items():
    for h in re.findall(r'href="(https?://[^"]+)"', p["content"]["rendered"]):
        links[pid].append(h.split("#")[0])
ALEGRA = {"CO": "https://www.alegra.com/colombia/precios/", "MX": "https://www.alegra.com/mexico/precios/",
          "CR": "https://www.alegra.com/costarica/precios/", "DO": "https://www.alegra.com/rdominicana/precios/"}
PAISW = {"CO": ["colombia", "/co/", "es-co", ".com.co"], "MX": ["mexico", "/mx", ".mx", "es-mx"],
         "CR": ["costa", "/cr", ".cr", "es-cr"], "DO": ["dominicana", "/do", ".do", "/rd"]}
pares = collections.defaultdict(list)
for u in ubic:
    pares[(u["marca"], u["pais"])].append(u)


def score(u, pais):
    s = 0
    if re.search(r"precio|planes|plan\b|pricing|tarifa|costo|tienda|comprar|price", u, re.I):
        s += 3
    if any(w in u.lower() for w in PAISW[pais]):
        s += 2
    return s


fuentes = []
for (m, pais), xs in sorted(pares.items(), key=lambda kv: -len(kv[1])):
    doms = MARCAS[m][1]
    cand = collections.Counter()
    for pid in {x["post_id"] for x in xs}:
        for h in links.get(pid, []):
            d = urlparse(h).netloc.lower().replace("www.", "")
            if any(d == dd or d.endswith("." + dd) for dd in doms):
                cand[h.split("?")[0]] += 1
    urls = sorted(cand, key=lambda u: (-score(u, pais), -cand[u]))[:4]
    url = ALEGRA[pais] if m == "Alegra" else (urls[0] if urls and score(urls[0], pais) >= 3 else None)
    n_prec = sum(1 for x in xs if x["tipo_cifra"] == "precio")
    n_posts = len({x["post_id"] for x in xs})
    fuentes.append({
        "id": f"{re.sub(r'[^a-z0-9]+', '-', m.lower()).strip('-')}-{pais.lower()}",
        "marca": m, "pais": pais,
        "prioridad": 1 if (n_prec >= 20 or n_posts >= 4) else (2 if n_prec >= 6 else 3),
        "cifras_publicadas": n_prec, "limites_publicados": len(xs) - n_prec,
        "posts": sorted({x["post_id"] for x in xs}),
        "productos_citados": sorted({x["producto"] for x in xs if x["producto"]}),
        "monedas_en_posts": dict(collections.Counter(x["moneda_leida"] for x in xs)),
        "url": url, "url_candidatas": urls if m != "Alegra" else [ALEGRA[pais]],
        "url_verificada": m == "Alegra",
        "moneda_esperada": {"CO": "COP", "MX": "MXN", "CR": "USD", "DO": "USD"}[pais] if m == "Alegra" else None,
        "senales_pais": [], "modo_lectura": "ruta_pais" if m == "Alegra" else "por_definir",
        "receta": {"contenedor": "[id^='pricing-cards-']"} if (m == "Alegra" and pais == "CO") else None,
        "estado": "borrador",
    })
for p_ in [k for k, v in VIGIAS.items() if v]:
    guardar(p_, "fuentes", "fuentes", [f for f in fuentes if f["pais"] == p_])

print("ubicaciones", len(ubic), "| pendientes", len(pend), collections.Counter(p["motivo"] for p in pend),
      "| rangos", len(rangos), "| fuera", dict(fuera))
print("fuentes", len(fuentes), "| con url", sum(1 for f in fuentes if f["url"]),
      "| prioridad", collections.Counter(f["prioridad"] for f in fuentes))
print("por pais", collections.Counter(f["pais"] for f in fuentes))
print("ubic por pais", collections.Counter(u["pais"] for u in ubic), "conf", collections.Counter(u["confianza"] for u in ubic))
print("posts con ubicaciones", len({u["post_id"] for u in ubic}))
