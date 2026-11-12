# Migración a Alegra — landings de Colombia (guardadas 22-oct-2026)

Las tres landings están **live y responden 200** (verificado 22-oct-2026). Son la base para las piezas
de intención «ya decidí cambiar de software, ¿cómo lo hago?», que es **distinta** de «alternativas a X»
y de «Alegra vs X».

## URLs

| Origen | Landing |
|---|---|
| Siigo | `https://www.alegra.com/colombia/contabilidad/migracion/siigo/` |
| Loggro | `https://www.alegra.com/colombia/contabilidad/migracion/loggro/` |
| World Office | `https://www.alegra.com/colombia/contabilidad/migracion/world-office/` |
| Hub (migración) | `https://www.alegra.com/colombia/contabilidad/migracion/` |

## UTM para el portal (no hace falta pedirlas)

Convención del portal, campaña `col_`:

```
?utm_source=blog_programascontabilidad&utm_medium=referral&utm_campaign=col_articulo_tmd_content&utm_term={keyword}
```

Listas para pegar:

- Siigo: `https://www.alegra.com/colombia/contabilidad/migracion/siigo/?utm_source=blog_programascontabilidad&utm_medium=referral&utm_campaign=col_articulo_tmd_content&utm_term=migrar-de-siigo-a-alegra`
- Loggro: `https://www.alegra.com/colombia/contabilidad/migracion/loggro/?utm_source=blog_programascontabilidad&utm_medium=referral&utm_campaign=col_articulo_tmd_content&utm_term=migrar-de-loggro-a-alegra`
- World Office: `https://www.alegra.com/colombia/contabilidad/migracion/world-office/?utm_source=blog_programascontabilidad&utm_medium=referral&utm_campaign=col_articulo_tmd_content&utm_term=migrar-de-world-office-a-alegra`

## Datos reutilizables (los tres servicios, texto oficial)

- **Plazo:** aproximadamente **6 días hábiles**, contados desde que se reciben los archivos completos y se
  confirma el alcance.
- **Qué se migra:** contactos (con NIT), clientes y proveedores, productos y servicios, inventario,
  catálogo de cuentas, facturas electrónicas **desde XML** y saldos iniciales.
- **Qué NO se migra por defecto:** movimientos contables, documentos históricos y periodos anteriores
  («sujeto a diagnóstico»). Hay que conservar acceso o respaldos del sistema de origen.
- **Saldos iniciales con IA:** se carga el **balance de prueba** exportado; la IA interpreta la estructura,
  identifica cuentas con saldo, propone el catálogo, relaciona terceros y deja los saldos listos. El contador
  revisa y confirma: la IA no reemplaza la validación contable.
- **Validación:** se compara lo cargado contra los reportes de cierre (catálogo, balance, bancos, cartera,
  cuentas por pagar, inventario y una muestra de contactos y facturas).
- **Multiempresa:** cada empresa se trata como un conjunto independiente; para firmas conviene empezar con
  una empresa piloto.
- **Continuidad:** se puede seguir operando en el sistema anterior hasta la **fecha de corte**, sin registros
  duplicados.
- **Límites del autoservicio (World Office):** hasta **1.000 contactos**, **3.000 productos** y **2.300
  cuentas** por archivo.
- **Loggro:** el alcance depende del producto de origen (Pymes, POS, Restobar, Alojamientos, Enterprise).
  Ventas, mesas, comandas, reservas o cierres de caja **no** equivalen automáticamente a datos contables
  migrables: se evalúan aparte.
- Guías de autoservicio: `ayuda.alegra.com/col/migra-tus-datos-de-siigo-a-alegra`,
  `ayuda.alegra.com/col/migra-tus-datos-a-alegra` (Loggro),
  `ayuda.alegra.com/col/migrar-de-world-office-a-alegra`.

## Qué hay ya en el portal (auditoría 22-oct-2026)

16 entradas mencionan estos softwares, pero **ninguna cubre la intención de migración**:

| id | Pieza | Intención |
|---|---|---|
| 4273 | Alternativas a Siigo en Colombia | alternativas |
| 34 | Alternativas a Loggro en Colombia | alternativas |
| 1438 | Alternativas a World Office en Colombia | alternativas |
| 139 | Alegra vs Siigo Colombia | duelo |
| 30 | Siigo Aspel vs Alegra | duelo |
| 24 | World Office vs Siigo Nube vs Alegra | duelo |
| 1492 | Certificado de retención en World Office | guía operativa |

**SERP (Colombia, 22-oct-2026):** «migrar de siigo a alegra» y «migrar de world office a alegra» devuelven
AI Overview y, en el top 10, solo propiedades de Alegra (blog, ayuda, novedades, redes). **Ningún medio
independiente compite** por estas consultas: hay hueco editorial.

## Decisión editorial (22-oct-2026): NO se crean piezas de migración

El portal no abre URLs nuevas de migración. **El enlace vive dentro de las comparativas que ya existen**, en la
sección donde ya se habla del cambio de software. Ya está aplicado:

| Pieza | Sección donde vive el enlace | Landing |
|---|---|---|
| 1438 Alternativas a World Office | «¿Cómo migrar de World Office sin perder información?» | `/migracion/world-office/` |
| 34 Alternativas a Loggro | «Migración desde Loggro: tiempos y fricción real» | `/migracion/loggro/` |
| 139 Alegra vs Siigo Colombia | cierre del veredicto («si ya decidiste el cambio») | `/migracion/siigo/` |

Reglas al insertarlo:

- Va como **callout de marca** (`#cce4f7`, borde `#159bd7`), no como bloque de CTA suelto.
- **Un solo enlace** por pieza, con el UTM de campaña `col_` y `utm_term=migrar-de-{software}-a-alegra`.
- Texto útil, no promocional: plazo (~6 días hábiles), qué se migra, saldos con IA desde balance de prueba y
  validación contra el cierre.
- No duplicar el enlace en la misma pieza ni añadirlo a las entradas de duelo que ya tienen su propio CTA.
- No crear «cómo migrar de X» como artículo independiente: esa intención se cubre desde la comparativa.
