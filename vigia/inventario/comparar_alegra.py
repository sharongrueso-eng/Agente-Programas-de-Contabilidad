"""Compara las cifras de Alegra publicadas en PdC con las páginas de precios de Alegra leídas hoy."""
import json, re
from numeros import valor

PAG = {"CO": "colombia", "MX": "mexico", "CR": "costarica", "DO": "rdominicana"}
ref = {}
for pais, c in PAG.items():
    h = open(f"raw/alegra-{c}-precios.html", encoding="utf-8", errors="replace").read()
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"\s+", " ", t)
    vals = set()
    for m in re.finditer(r"(?:USD|US\$|\$)\s?(\d[\d.,]*\d|\d)", t):
        v = valor(m.group(1))
        if v is not None:
            vals.add(round(v, 2))
    ref[pais] = vals

X = json.load(open("salida/cifras_todas.json"))
n = {"coincide": 0, "no_coincide": 0}
for x in X:
    x["alegra_hoy"] = None
    if x["marca"] == "Alegra" and x["tipo_cifra"] in ("precio", "limite") and x["pais"] in ref and x["valor"] is not None:
        moneda_ok = not (x["pais"] in ("CR", "DO") and x["moneda_leida"] in ("DOP", "CRC"))
        ok = moneda_ok and round(x["valor"], 2) in ref[x["pais"]]
        x["alegra_hoy"] = "coincide" if ok else ("moneda_distinta" if not moneda_ok else "no_coincide")
        n["coincide" if ok else "no_coincide"] += 1
json.dump(X, open("salida/cifras_todas.json", "w"), ensure_ascii=False, indent=1)
print(n, {k: len(v) for k, v in ref.items()})
