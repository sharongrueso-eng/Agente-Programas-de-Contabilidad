"""Registra en las fichas las tarifas que las páginas oficiales publican y faltaban.

Las cifras se leyeron del HTML de siigo.com/precios-siigo y alegra.com/colombia/precios el
13-nov-2026. Se añaden como planes con su periodicidad; no se estima ni se convierte nada que
la página no imprima.
"""

import json
from pathlib import Path

FICHAS = Path("datos/herramientas")
HOY = "2026-11-13"

SIIGO_NUEVOS = [
    ("Sistema POS Inicio", "527.310", "año"),
    ("Sistema POS Avanzado", "764.915", "año"),
    ("Sistema POS Avanzado + Emprendedor", "2.827.350", "año"),
    ("Sistema POS Avanzado + Premium", "2.958.060", "año"),
    ("Sistema POS GastroBar PRO", "1.049.930", "año"),
    ("Sistema POS GastroBar PRO + Premium", "2.895.480", "año"),
    ("Nómina Electrónica Lite 120", "239.920", "año"),
    ("Nómina Electrónica Lite 300", "449.925", "año"),
    ("Nómina PLUS", "749.925", "año"),
    ("Nómina PRO", "1.402.425", "año"),
    ("Profesional independiente (Siigo Nube)", "1.751.920", "año"),
    ("Emprendedor (Siigo Nube)", "2.295.920", "año"),
    ("Premium (Siigo Nube)", "2.494.425", "año"),
    ("Nube independiente + Nómina Electrónica 120", "2.489.800", "año"),
    ("Siigo contador ilimitado", "535.900", "año"),
]

ALEGRA_NUEVOS = [
    ("Facturación electrónica Pro", "74.925", "mes", "anual", "Equivalente mensual del plan anual"),
    ("Facturación electrónica Plus", "134.925", "mes", "anual", "Equivalente mensual del plan anual"),
    ("Facturación electrónica Emprendedor", "161.100", "año", "anual", "Total facturado al año"),
    ("Facturación electrónica Pyme", "449.100", "año", "anual", "Total facturado al año"),
    ("Facturación electrónica Pro", "899.100", "año", "anual", "Total facturado al año"),
    ("Facturación electrónica Plus", "1.619.100", "año", "anual", "Total facturado al año"),
    ("POS Emprendedor", "233.100", "año", "anual", "Total facturado al año"),
    ("POS Pyme", "719.100", "año", "anual", "Total facturado al año"),
    ("Contabilidad Emprendedor", "674.100", "año", "anual", "Total facturado al año"),
    ("Contabilidad Pyme", "1.475.100", "año", "anual", "Total facturado al año"),
    ("Nómina Emprendedor", "29.900", "mes", "mensual", "Línea Nómina, de 1 a 10 empleados"),
    ("Nómina Emprendedor", "22.425", "mes", "anual", "Equivalente mensual del plan anual"),
    ("Nómina Emprendedor", "269.100", "año", "anual", "Total facturado al año (1 a 10 empleados)"),
    ("Nómina Pyme", "69.000", "mes", "mensual", "Línea Nómina, de 11 a 20 empleados"),
    ("Nómina Pyme", "51.750", "mes", "anual", "Equivalente mensual del plan anual"),
    ("Nómina Pyme", "621.000", "año", "anual", "Total facturado al año (11 a 20 empleados)"),
]


def cargar(nombre):
    return json.loads((FICHAS / nombre).read_text(encoding="utf-8"))


def guardar(nombre, datos):
    (FICHAS / nombre).write_text(
        json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def existe(planes, nombre, precio):
    return any(
        p.get("name") == nombre and str(p.get("price")) == precio for p in planes
    )


ADMCLOUD_NUEVOS = [
    ("Billing", "18.00", "15.00"),
    ("Start", "24.00", "20.00"),
    ("Basic", "36.00", "30.00"),
    ("Standard", "60.00", "50.00"),
    ("Premium", "84.00", "70.00"),
    ("Premium Plus", "108.00", "90.00"),
    ("Premium Plus Nómina", "144.00", "120.00"),
    ("Premium Plus Manufactura", "144.00", "120.00"),
]


def main() -> int:
    siigo = cargar("siigo-co.json")
    antes = len(siigo["plans"])
    for nombre, precio, periodo in SIIGO_NUEVOS:
        if existe(siigo["plans"], nombre, precio):
            continue
        siigo["plans"].append(
            {
                "name": nombre,
                "price": precio,
                "currency": "COP",
                "period": periodo,
                "billing": "anual" if periodo == "año" else "mensual",
                "note": "Publicado en la tabla de planes; el pago es anual y el descuento aplica a clientes nuevos",
            }
        )
    siigo["captured_at"] = HOY
    siigo["notes"] = (
        "Precios de lista con pago anual (el mensual es el anual dividido entre 12) para "
        "clientes nuevos. Incluye las líneas de Siigo Nube, POS y Nómina que la página publica "
        "en tablas separadas de la facturación electrónica. Registrado el 13-nov-2026 leyendo "
        "el HTML de la página."
    )
    guardar("siigo-co.json", siigo)
    print(f"siigo-co: {antes} -> {len(siigo['plans'])} planes")

    alegra = cargar("alegra-co.json")
    antes = len(alegra["plans"])
    for nombre, precio, periodo, cobro, nota in ALEGRA_NUEVOS:
        if existe(alegra["plans"], nombre, precio):
            continue
        alegra["plans"].append(
            {
                "name": nombre,
                "price": precio,
                "currency": "COP",
                "period": periodo,
                "billing": cobro,
                "note": nota,
            }
        )
    alegra["captured_at"] = HOY
    guardar("alegra-co.json", alegra)
    print(f"alegra-co: {antes} -> {len(alegra['plans'])} planes")

    adm = cargar("adm-cloud-do.json")
    antes = len(adm["plans"])
    for nombre, mensual, anual in ADMCLOUD_NUEVOS:
        for precio, cobro in ((mensual, "mensual"), (anual, "anual")):
            if existe(adm["plans"], nombre, precio):
                continue
            adm["plans"].append(
                {
                    "name": nombre,
                    "price": precio,
                    "currency": "USD",
                    "period": "mes",
                    "billing": cobro,
                    "note": "Precio con facturación electrónica incluida"
                    if cobro == "mensual"
                    else "Precio mensual pagando anualmente",
                }
            )
    adm["captured_at"] = HOY
    adm["source_url"] = "https://www.admcloud.net/planes"
    adm["notes"] = (
        "Ocho planes con facturación electrónica incluida, en dólares. La página publica el "
        "precio de pago mensual y el equivalente mensual pagando al año. Registrado el "
        "13-nov-2026 leyendo el HTML de la página de planes."
    )
    guardar("adm-cloud-do.json", adm)
    print(f"adm-cloud-do: {antes} -> {len(adm['plans'])} planes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
