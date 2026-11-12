# Alegra: módulos por país (matriz verificada 21-oct-2026)

Fuente: cada URL comprobada con `curl -L` contra `alegra.com`. ✅ = 200 con contenido propio del
módulo · ❌ = no existe. **Antes de escribir el nombre de un módulo, mira esta tabla.**

| Módulo | MX | CO | CR | RD | PE | PA |
|---|---|---|---|---|---|---|
| Contabilidad | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Facturación electrónica | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| POS | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| ERP / gestión administrativa | ✅ | ✅ (`/colombia/software-administrativo/`) | ✅ | ✅ | ❌ | ❌ |
| Nómina | ⚠️ **timbrado de nómina** (CFDI nómina) | ✅ | ❌ | ✅ | ❌ | ❌ |
| Inventarios | ✅ (`/mexico/administracion-inventarios/`) | ✅ | ✅ | ✅ | ❌ | ❌ |
| CRM | ❌ | ✅ (producto `/alegra-crm/`) | integrado en ERP | integrado en ERP | ❌ | ❌ |
| IA / Agente Alegra | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| App móvil | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Contadores | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

Rutas canónicas:

| País | Contabilidad | Facturación | POS | Otros | Precios |
|---|---|---|---|---|---|
| MX | `/mexico/contabilidad/` | `/mexico/facturacion-electronica/` | `/mexico/pos/` y `/mexico/punto-de-venta/` | `/mexico/erp/`, `/mexico/administracion-inventarios/`, `/mexico/ia/`, `/mexico/calcula/`, `/mexico/sistema-multi-rfc/` | `/mexico/precios/` |
| CO | `/colombia/contabilidad/` | `/colombia/facturacion-electronica/` | `/colombia/pos/` | **`/colombia/software-administrativo/`** (ERP), `/colombia/inventarios/`, `/colombia/gestion-de-cobranzas/`, `/colombia/nomina-electronica/`, `/colombia/alegra-crm/`, `/colombia/ia/` | `/colombia/precios/` |
| CR | `/costarica/contabilidad/` | `/costarica/facturacion-electronica/` | `/costarica/pos/` | `/costarica/erp/`, `/costarica/ia/`, `/costarica/sistema-de-inventarios/` | `/costarica/precios/` |
| RD | `/rdominicana/contabilidad/` | **`/rdominicana/factura-electronica/`** | `/rdominicana/pos/` | `/rdominicana/erp/`, `/rdominicana/nomina/` (TSS), `/rdominicana/ia/` | `/rdominicana/precios/` |
| PE | `/peru/contabilidad/` | `/peru/factura-electronica/` + `/peru/boleta-electronica/` | **`/peru/punto-venta/`** | — | `/peru/contabilidad/precios/` |
| PA | `/panama/contabilidad/` | `/panama/facturacion-electronica/` | `/panama/pos/` | `/panama/contadores/` | `/panama/contabilidad/precios/` |

Monedas: MX=Mex$, CO=COP, CR=CRC, RD=USD, PE=S/ (PEN), PA=USD.

## Reglas duras

1. **México — timbrado de nómina: SÍ existe.** Se ofrece y se menciona **timbrado de nómina** (CFDI de
   nómina) con total naturalidad; aparece como "Timbrado de nómina" en los planes de contadores de
   `/mexico/precios/`. **Nunca** escribir ni insinuar que el módulo de nómina "todavía no está", "no
   existe" o "está incompleto": esa aclaración no le sirve al lector y desgasta la venta. CTA de nómina
   en MX: `/mexico/contabilidad/` o `/mexico/precios/` (no hay `/mexico/nomina/`).
2. **Colombia — ERP: SÍ existe.** Se publica como *software administrativo* `/colombia/software-administrativo/`
   y reúne inventarios, cobranzas, bancos, nómina, CRM y POS. Se habla de ERP sin reservas y el CTA va a
   esa URL. **Nunca** decir que Alegra no tiene ERP en Colombia. Ojo: `/colombia/erp/` **responde 404**,
   nunca enlazar ahí.
3. **ERP sí, pero no en Perú ni Panamá**, y en Costa Rica y RD solo como `/erp/`.
4. **Nómina en Costa Rica, Perú y Panamá:** no se menciona. Si el artículo es de planilla en esos
   países, el producto es **Alegra Contabilidad** (registrar y pagar la planilla como operación
   contable), sin prometer cálculo automático ni emisión.
5. **CRM:** producto propio solo en Colombia; en CR y RD va integrado en el ERP; en MX, PE y PA no se
   nombra.
6. **Vocabulario del país, no traducción:** MX CFDI/SAT + "timbrado de nómina" · CO DIAN + "nómina
   electrónica" + "software administrativo" · CR TRIBU-CR (FE 4.4) · RD **"factura electrónica"**/e-CF/
   DGII/TSS · PE SUNAT **"factura electrónica", "boleta electrónica", "punto de venta"** (nunca POS) ·
   PA DGI/ITBMS.
7. **Precios del país de la pieza**, leídos el día de la publicación, con fecha de consulta. Nunca
   copiar el precio de otro país.
8. Un solo CTA de Alegra, a la URL del módulo que de verdad cubre lo que promete el párrafo, más el UTM.

## Higiene de enlaces (deuda del archivo)

42 enlaces publicados usan rutas que hoy hacen 301: `/costarica/facturacion/` (14),
`/rdominicana/contabilidad/gestion-negocios/` (6), `/mexico/tpv/` (4), `/mexico/tienda/` (3 → home, la
Tienda Online ya no existe en MX), `/panama/facturacion/` (3), `*/pos/precios/` y
`*/facturacion/precios/` (6), `/peru/pos/` (1), `/peru/precios/` (2), `/colombia/contador` (1).
Al refrescar un post, se reescriben a la canónica.

**Un solo enlace roto de verdad:** `/rdomincana/contacto/` (typo, falta la "i") responde **404**. Debe
ser `/rdominicana/contacto/`.
