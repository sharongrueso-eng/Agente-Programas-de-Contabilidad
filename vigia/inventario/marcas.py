"""Léxico de marcas: nombre canónico -> (patrones, dominios oficiales conocidos)."""
import re

MARCAS = {
    "Alegra": ([r"Alegra"], ["alegra.com"]),
    "Siigo": ([r"Siigo"], ["siigo.com"]),
    "World Office": ([r"World ?Office"], ["worldoffice.com.co"]),
    "CONTPAQi": ([r"CONTPAQ ?i", r"Contpaq ?i", r"CONTPAQ"], ["contpaqi.com"]),
    "Aspel": ([r"Aspel"], ["aspel.com.mx"]),
    "Facturama": ([r"Facturama"], ["facturama.mx"]),
    "Vendty": ([r"Vendty"], ["vendty.com"]),
    "Miskuentas": ([r"mis ?kuentas"], ["miskuentas.com"]),
    "Facturele": ([r"Facturele"], ["facturele.com"]),
    "Susii": ([r"Susii"], []),
    "GTI": ([r"GTI"], ["facturaelectronica.cr"]),
    "SAP Business One": ([r"SAP Business ?One", r"SAP B1", r"\bSAP\b"], ["sap.com"]),
    "Eleventa": ([r"Eleventa"], ["eleventa.com"]),
    "Loggro": ([r"Loggro"], ["loggro.com"]),
    "Softland": ([r"Softland"], ["softland.com", "softland.cr"]),
    "CloudYa": ([r"Cloud ?Ya"], ["cloudya.do"]),
    "Odoo": ([r"Odoo"], ["odoo.com"]),
    "GridPOS": ([r"Grid ?POS"], ["gridpos.co"]),
    "DGMax": ([r"DG ?Max"], ["dgmax.do"]),
    "Citrus": ([r"Citrus"], ["citrus.com.do"]),
    "Cashflow": ([r"Cash ?flow"], ["cashflow.do"]),
    "Adm Cloud": ([r"Adm ?Cloud"], ["admcloud.net"]),
    "Axentra": ([r"Axentra"], ["axentra.com.do"]),
    "Contadigital": ([r"Contadigital"], []),
    "FACTURATica": ([r"FACTURATica", r"Facturatica"], ["facturatica.com"]),
    "Bind ERP": ([r"Bind(?: ERP)?\b"], ["bind.com.mx"]),
    "Helisa": ([r"Helisa"], ["helisa.com"]),
    "Cuenti": ([r"Cuenti"], ["cuenti.com"]),
    "QuickBooks": ([r"Quick ?Books"], ["quickbooks.intuit.com"]),
    "Alanube": ([r"Alanube"], ["alanube.co"]),
    "Siesa": ([r"Siesa"], ["siesa.com"]),
    "Factura.com": ([r"Factura\.com"], ["factura.com"]),
    "Holded": ([r"Holded"], ["holded.com"]),
    "Sage": ([r"\bSage\b"], ["sage.com"]),
    "Aliaddo": ([r"Aliaddo"], ["aliaddo.com"]),
    "GuruSoft": ([r"Guru ?Soft"], ["guru-soft.com"]),
    "Factura Profesional": ([r"Factura Profesional"], ["facturaprofesional.com"]),
    "Bavel": ([r"Bavel"], ["bavel.com.do"]),
    "HolaBill": ([r"Hola ?Bill"], ["holabill.com"]),
    "Contalink": ([r"Contalink"], ["contalink.com"]),
    "Ticofactura": ([r"Tico ?factura"], ["ticofactura.cr"]),
    "Factoa": ([r"Factoa"], ["factoacr.com"]),
    "Facturabot": ([r"Facturabot"], ["facturabot.com"]),
    "DFacture": ([r"DFacture"], []),
    "Facturo por ti": ([r"Facturo por ti"], []),
    "Konta": ([r"\bKonta\b"], []),
    "Sistema Monica": ([r"M[oó]nica"], ["sistemamonica.com"]),
    "myGESTIÓN": ([r"my ?GESTI[OÓ]N"], []),
    "Marcel": ([r"Marcel"], ["marcelsolution.com"]),
    "Saint": ([r"\bSaint\b"], []),
    "Factura Simple": ([r"Factura Simple"], []),
    "Xero": ([r"\bXero\b"], ["xero.com"]),
    "Zoho": ([r"Zoho"], ["zoho.com"]),
    "Square": ([r"\bSquare\b"], ["squareup.com"]),
    "Poster": ([r"\bPoster\b"], ["joinposter.mx"]),
    "Treinta": ([r"\bTreinta\b"], ["treinta.co"]),
    "Soft Restaurant": ([r"Soft ?Restaurant"], ["softrestaurant.com.co"]),
    "Fudo": ([r"\bFudo\b"], ["fu.do"]),
    "Shopify": ([r"Shopify"], []),
    "STEL Order": ([r"STEL ?Order"], ["stelorder.com"]),
    "Quipu": ([r"Quipu"], ["getquipu.com"]),
    "Eleva POS": ([r"Eleva ?POS"], ["elevapos.com"]),
    "Digifact": ([r"Digifact"], ["digifact.com.do"]),
    "Edicom": ([r"Edicom"], ["edicomgroup.com"]),
    "Claro Cloud": ([r"Claro ?Cloud"], ["clarocloud.com.do"]),
    "Accounter": ([r"Accounter"], ["accounter.co"]),
    "Qenta": ([r"Qenta"], ["qenta.app"]),
    "Contai": ([r"Contai"], []),
    "Facturador DGII": ([r"Facturador (?:Gratuito )?(?:de la )?DGII"], []),
    "Defontana": ([r"Defontana"], []),
    "Nubox": ([r"Nubox"], []),
    "Bsale": ([r"Bsale"], []),
    "Loyverse": ([r"Loyverse"], []),
    "Clip": ([r"\bClip\b"], []),
    "Kyte": ([r"\bKyte\b"], []),
    "e-Factura": ([r"e-Factura"], []),
    "TNS": ([r"\bTNS\b"], []),
    "Wompi": ([r"Wompi"], []),
    "SoftDial": ([r"Soft ?Dial"], ["softdialcr.com"]),
    "Pymes.co": ([r"Pymesco"], ["pymesco.co"]),
    "Facturar.cr": ([r"Facturar\.cr"], ["facturar.cr"]),
    "BCPos": ([r"BC ?POS"], ["bcpos.com.do"]),
    "Voxel": ([r"Voxel"], ["voxelcaribe.com"]),
    "WebPOS": ([r"Web ?POS ?Online"], ["webposonline.com"]),
    "Microsoft Dynamics": ([r"Dynamics"], []),
    "NetSuite": ([r"NetSuite"], []),
    "Madison": ([r"Madison"], []),
    "TicoPay": ([r"Tico ?Pay"], []),
    "FactuSOL": ([r"FactuSOL"], []),
}

# Productos que distinguimos dentro de una marca
PRODUCTOS = {
    "Alegra": [("POS", r"\bPOS\b|punto de venta"),
               ("ERP", r"\bERP\b|Software administrativo"),
               ("Nómina", r"N[oó]mina"),
               ("Facturación", r"Facturaci[oó]n|Facturador|factura electr[oó]nica"),
               ("Contabilidad", r"Contabilidad|Soy Contador|software contable|\bContador")],
    "Siigo": [("Nube", r"Nube"), ("POS", r"\bPOS\b"), ("Pyme", r"Pyme"), ("Contador", r"Contador")],
    "Aspel": [("COI", r"\bCOI\b"), ("SAE", r"\bSAE\b"), ("NOI", r"\bNOI\b"), ("Facture", r"Facture"),
              ("Nube Gestión", r"Nube Gesti[oó]n")],
    "CONTPAQi": [("Contabilidad", r"Contabilidad"), ("Comercial", r"Comercial"), ("Factura electrónica", r"Factura electr[oó]nica"),
                 ("Nóminas", r"N[oó]minas?"), ("Bancos", r"Bancos")],
}

COMPILADAS = [(m, re.compile("|".join(f"(?:{p})" for p in pats), re.I if m not in ("GTI", "SAP Business One", "TNS", "Clip", "Square", "Saint") else 0))
              for m, (pats, _) in MARCAS.items()]


def marcas_en(texto):
    """Devuelve [(marca, posición)] ordenadas por posición."""
    res = []
    for m, rx in COMPILADAS:
        for mt in rx.finditer(texto or ""):
            res.append((m, mt.start()))
    res.sort(key=lambda x: x[1])
    return res


def producto_de(marca, texto):
    for nombre, rx in PRODUCTOS.get(marca, []):
        if re.search(rx, texto or "", re.I):
            return nombre
    return None
