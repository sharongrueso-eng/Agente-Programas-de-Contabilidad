"""Descarga lo que necesita el inventario: posts publicados, señales de país, redirecciones
y las páginas de precios de Alegra. Usa curl porque Cloudflare bloquea el agente de Python."""
import json, os, re, subprocess, time

BASE = "https://programascontabilidad.com/wp-json/wp/v2"
os.makedirs("raw", exist_ok=True)


def curl(url, out=None, extra=()):
    cmd = ["curl", "-sS", "-m", "90", *extra, url]
    if out:
        cmd[1:1] = ["-o", out]
    return subprocess.run(cmd, capture_output=True, text=True).stdout


# 1) posts publicados con contenido renderizado
posts = []
for page in range(1, 20):
    txt = curl(f"{BASE}/posts?per_page=100&page={page}&status=publish&_fields=id,slug,link,title,categories,date,modified,content,author,meta")
    try:
        lote = json.loads(txt)
    except json.JSONDecodeError:
        break
    if not isinstance(lote, list) or not lote:
        break
    posts += lote
json.dump(posts, open("raw/posts.json", "w"), ensure_ascii=False)
print("posts", len(posts))

# 2) recursos (tipo propio; su contenido no sale por la API)
rec = json.loads(curl(f"{BASE}/recursos?per_page=100&_fields=id,slug,link,title,modified"))
for r in rec:
    r["content"] = {"rendered": ""}
    r["categories"] = []
json.dump(rec, open("raw/recursos.json", "w"), ensure_ascii=False)

# 3) país por post (html lang que escribe pdc_target_country) y redirecciones
loc, red = {}, {}
for p in posts + rec:
    head = curl(p["link"])[:20000]
    m = re.search(r'<html[^>]*\slang="([^"]+)"', head)
    loc[p["id"]] = {"lang": m.group(1) if m else None}
    w = curl(p["link"], out="/dev/null", extra=("-w", "%{http_code} %{redirect_url}")).split(" ", 1)
    red[p["id"]] = {"code": w[0], "to": (w[1] if len(w) > 1 else "").strip()}
    time.sleep(0.2)
json.dump(loc, open("raw/locale.json", "w"))
json.dump(red, open("raw/redirects.json", "w"))

# 4) páginas de precios de Alegra (referencia para comparar)
for c in ("colombia", "mexico", "costarica", "rdominicana"):
    curl(f"https://www.alegra.com/{c}/precios/", out=f"raw/alegra-{c}-precios.html", extra=("-A", "curl/8.7.1"))
print("listo")
