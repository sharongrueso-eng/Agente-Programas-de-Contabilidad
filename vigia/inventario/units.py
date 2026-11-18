"""Convierte el HTML de cada post en unidades (párrafos, ítems, filas de tabla)
con el encabezado vigente y, para tablas, la fila de encabezados."""
import json, re, html
from bs4 import BeautifulSoup, NavigableString

BLOCK_TAGS = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "figcaption", "blockquote", "dt", "dd"}


def clean(t):
    t = html.unescape(t)
    t = t.replace("\xa0", " ").replace(" ", " ")
    return re.sub(r"\s+", " ", t).strip()


def units_from_html(raw):
    soup = BeautifulSoup(raw, "lxml")
    for s in soup(["script", "style", "noscript"]):
        s.decompose()
    out = []
    heading = {"h2": None, "h3": None}
    seen = set()

    def walk(node):
        for el in node.find_all(True, recursive=False):
            name = el.name
            if name in ("h1", "h2", "h3", "h4"):
                txt = clean(el.get_text(" "))
                if name in ("h1", "h2"):
                    heading["h2"], heading["h3"] = txt, None
                else:
                    heading["h3"] = txt
                out.append({"tipo": "titulo", "texto": txt, "h2": heading["h2"], "h3": heading["h3"]})
                continue
            if name == "table":
                rows = el.find_all("tr")
                head = None
                for i, tr in enumerate(rows):
                    cells = [clean(c.get_text(" ")) for c in tr.find_all(["th", "td"])]
                    if not any(cells):
                        continue
                    is_head = (i == 0) or all(c.name == "th" for c in tr.find_all(["th", "td"]))
                    if head is None and is_head:
                        head = cells
                        continue
                    out.append({"tipo": "fila", "celdas": cells, "cabecera": head,
                                "texto": " | ".join(cells), "h2": heading["h2"], "h3": heading["h3"]})
                continue
            if name in ("p", "li", "figcaption", "blockquote", "dt", "dd"):
                # li con listas anidadas: tomar solo su texto directo + recursión
                nested = el.find(["ul", "ol", "table"])
                if nested is not None and name == "li":
                    direct = clean(" ".join(t for t in el.find_all(string=True, recursive=False)))
                    for ch in el.find_all(["strong", "b", "span", "a", "em"], recursive=False):
                        direct += " " + clean(ch.get_text(" "))
                    if direct.strip():
                        out.append({"tipo": name, "texto": clean(direct), "h2": heading["h2"], "h3": heading["h3"]})
                    walk(el)
                    continue
                txt = clean(el.get_text(" "))
                if txt:
                    out.append({"tipo": name, "texto": txt, "h2": heading["h2"], "h3": heading["h3"]})
                continue
            walk(el)

    body = soup.body or soup
    walk(body)
    return out


if __name__ == "__main__":
    ps = json.load(open("raw/posts.json")) + json.load(open("raw/recursos.json"))
    allu = {}
    for p in ps:
        allu[p["id"]] = units_from_html(p["content"]["rendered"])
    json.dump(allu, open("raw/units.json", "w"), ensure_ascii=False)
    print(sum(len(v) for v in allu.values()), "unidades en", len(allu), "posts")
