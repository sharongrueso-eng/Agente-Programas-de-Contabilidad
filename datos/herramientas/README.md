# Registro de datos de herramientas

Cada archivo `.json` de esta carpeta es una marca en un país. Es la única fuente de cifras
que el agente puede citar: el validador bloquea cualquier importe con moneda que no exista
en una ficha del mercado de la pieza (`registry_amounts`).

## Campos

| Campo | Obligatorio | Qué es |
|---|---|---|
| `brand` | sí | Nombre de la marca tal como se publica |
| `country` | sí | `CO`, `MX`, `CR` o `DO` |
| `product` | sí | Producto o plan concreto |
| `plans` | sí | Lista de `{name, price, currency, period}` |
| `source_url` | sí | Página oficial de donde salió el dato |
| `captured_at` | sí | Fecha en que se leyó la página, `AAAA-MM-DD` |
| `evidence_level` | sí | Ver tabla de abajo |
| `features`, `integrations`, `advantages`, `known_limits` | no | Listas de texto |
| `electronic_invoicing`, `support` | no | Texto |
| `notes` | no | Advertencias para quien publique |

## Niveles de evidencia

| Nivel | Significa | ¿Sirve para publicar? |
|---|---|---|
| `documentacion_oficial` | Cifra leída en la página de la marca, con fecha | Sí |
| `revision_secundaria` | Cifra de una fuente reconocida que cita a la marca | Solo mencionando la fuente |
| `estimacion` | Rango deducido de planes o comunicados | No: se publica como «alrededor de» o no se publica |

## Reglas

1. Una ficha sin `source_url` o sin `captured_at` **no carga**: el programa falla en lugar de
   seguir con un dato sin respaldo.
2. Los precios se copian tal como aparecen, sin redondear ni convertir moneda.
3. Si la marca cambia de precio, se actualiza la ficha y se cambia `captured_at`; el histórico
   de precios lo lleva el vigía, no la ficha.
4. Una ficha de más de 30 días se marca como vencida y el agente no publica cifras de ella.

## Crear una ficha

```bash
python scripts/nueva_ficha.py --brand Siigo --country CO --url https://www.siigo.com/precios-siigo/
```

Deja el esqueleto con los campos vacíos. Mientras falten `plans`, `captured_at` o
`evidence_level`, la ficha no carga y el registro la rechaza al leer la carpeta.

## Qué hay hoy

| Ficha | Estado |
|---|---|
| `alegra-co.json` | Verificada contra la página oficial el 2026-11-06 |
| Resto de marcas y países | Pendiente: hay que leer cada página oficial y llenar la ficha |

Faltan, como mínimo, Siigo, World Office y Loggro en Colombia; Contalink y Aspel en México;
y las marcas locales de Costa Rica y República Dominicana.
