"""Lectura de cifras de dinero: moneda y valor numérico según la convención de cada país."""
import re

CUR_PAIS = {"COP": "CO", "MXN": "MX", "MX$": "MX", "MEX$": "MX", "CRC": "CR", "₡": "CR", "COLONES": "CR",
            "RD$": "DO", "DOP": "DO", "PESOS DOMINICANOS": "DO", "PESOS MEXICANOS": "MX", "PESOS COLOMBIANOS": "CO",
            "€": "ES", "EUR": "ES", "EUROS": "ES", "S/": "PE", "S/.": "PE", "PEN": "PE", "SOLES": "PE", "B/.": "PA"}


def moneda_de(pre, suf):
    for s in (suf, pre):
        if not s:
            continue
        k = s.strip().upper().replace(" ", "")
        k2 = s.strip().upper()
        if k in ("US$", "USD", "USD$", "DÓLARES", "DOLARES"):
            return "USD"
        if k2 in CUR_PAIS or k in CUR_PAIS:
            code = CUR_PAIS.get(k2) or CUR_PAIS.get(k)
            return {"CO": "COP", "MX": "MXN", "CR": "CRC", "DO": "DOP", "ES": "EUR", "PE": "PEN", "PA": "PAB"}[code]
        if k.startswith("COP"):
            return "COP"
        if k.startswith("MXN"):
            return "MXN"
        if k.startswith("DOP"):
            return "DOP"
        if k == "PESOS":
            return "$"
    return "$"


def valor(n, pais=None):
    """Convierte '49.900', '1,299', '974,25', '2.249,25', '13.50' en número."""
    s = n.replace(" ", "")
    if re.fullmatch(r"\d+", s):
        return float(s)
    if "." in s and "," in s:
        dec = "." if s.rfind(".") > s.rfind(",") else ","
        if re.search(rf"\{dec}\d{{1,2}}$", s):
            mil = "," if dec == "." else "."
            return float(s.replace(mil, "").replace(dec, "."))
        return float(s.replace(".", "").replace(",", ""))
    sep = "." if "." in s else ","
    if re.fullmatch(rf"\d{{1,3}}(?:\{sep}\d{{3}})+", s):
        return float(s.replace(sep, ""))
    if re.fullmatch(rf"\d+\{sep}\d{{1,2}}", s):
        return float(s.replace(sep, "."))
    try:
        return float(s.replace(sep, ""))
    except ValueError:
        return None
