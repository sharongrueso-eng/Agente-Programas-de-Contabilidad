# Precios oficiales de Alegra — Colombia

Tabla leída del sitio oficial el **22 de octubre de 2026** (COP, descuento de 25 % por pago anual).
**Vuelve a verificarla antes de usarla**: cambia sin aviso y el artículo no puede contradecir a su fuente.

## Facturación electrónica (no incluye contabilidad)

| Plan | Mensual | Equivalente con pago anual | Facturado al año | Ingresos hasta | Usuarios |
|---|---|---|---|---|---|
| Emprendedor | $17.900 | $13.425 | $161.100 | $10.000.000 | 1 |
| Pyme | $49.900 | $37.425 | $449.100 | $40.000.000 | 2 |
| Pro | $99.900 | $74.925 | $899.100 | $180.000.000 | 3 |
| Plus | $179.900 | $134.925 | $1.619.100 | $500.000.000 | 5 |

Los cuatro planes incluyen un usuario gratis para el contador, soporte 24/7 y Alegra IA.

## Contabilidad

| Plan | Mensual | Equivalente con pago anual | Facturado al año |
|---|---|---|---|
| Emprendedor | $74.900 | $56.175 | $674.100 |
| Pyme | $163.900 | $122.925 | $1.475.100 |
| Pro | $250.900 | $188.175 | $2.258.100 |
| Plus | $319.900 | $239.925 | $2.879.100 |

## POS

| Plan | Mensual | Equivalente con pago anual | Facturado al año |
|---|---|---|---|
| Emprendedor | $25.900 | $19.425 | $233.100 |
| Pyme | $79.900 | $59.925 | $719.100 |
| Pro | $139.900 | $104.925 | $1.259.100 |
| Plus | $199.900 | $149.925 | $1.799.100 |

POS: documento POS electrónico ilimitado, versión online y offline, soporte 24/7, balanza, integración con
Bold, Wompi y Nequi, cierres de caja y terminales/bodegas según plan. **No publica funciones de
restaurante** (comandas, propinas, cuentas divididas) para Colombia.

## Nómina electrónica

| Plan | Mensual | Equivalente con pago anual | Facturado al año |
|---|---|---|---|
| Emprendedor | $29.900 | $22.425 | $269.100 |
| Pyme | $69.000 | $51.750 | $621.000 |
| Pro | $139.000 | $104.250 | $1.251.000 |
| Plus | $259.000 | $194.250 | $2.331.000 |

## Cómo se extrae la tabla del HTML

La página `https://www.alegra.com/colombia/precios/` renderiza las cuatro pestañas en el mismo HTML,
ocultas. Cada producto está en un contenedor con id propio:

```python
h = open("cache-alegra-co-precios.html", encoding="utf-8", errors="replace").read()
i = h.find('id="pricing-cards-pos"')
seg = h[i:i+60000]
anuales = re.findall(r'Facturado \$([\d\.,]+) anualmente', seg)   # facturado al año
# el equivalente mensual con descuento = anual / 12; la tarifa de lista = esa cifra / 0,75
```

Contenedores: `pricing-cards-facturacion`, `pricing-cards-contabilidad`, `pricing-cards-pos`,
`pricing-cards-nomina`. La tabla comparativa de cada pestaña trae además los límites por plan (bodegas,
usuarios, ingresos), útil para la ficha rápida.

Descarga con `curl -A "curl/8.7.1"` a un archivo local: son ~500 KB y Cloudflare bloquea el UA de Python.
