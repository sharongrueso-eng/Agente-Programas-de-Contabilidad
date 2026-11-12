# Precios oficiales de Alegra México (fuente: Golden Stack MX, leída 16-oct-2026)

Tomados de `alegra.com/mexico/precios/`. **Todo artículo de México cita estos números, con IVA aparte y
poniendo el pago anual primero.** El descuento anual es 25 % en Facturación, POS y ERP, y **10 % en Soy
Contador**.

| Producto | Plan | Mensual (MXN + IVA) | Equivalente anual / mes | Facturado al año | Límites |
|---|---|---|---|---|---|
| Facturación | Inicial | 249 | 186,75 | 2.241 | 1 usuario, CFDI ilimitados |
| Facturación | Pro | 449 | 336,75 | 4.041 | 2 usuarios, vendedores, multimoneda, reportes RESICO |
| Facturación | Plus | 699 | 524,25 | 6.291 | 3 usuarios, inventario con costo, listas de precios |
| POS | Inicial | 199 | 149,25 | 1.791 | 1 sucursal, CFDI ilimitados |
| POS | Pro | 399 | 299,25 | 3.591 | multisucursal, compras, remisiones |
| POS | Gastrobar | 599 | 449,25 | 5.391 | mesas, comandas, cocina, turnos, propinas |
| ERP | Inicial | 1.299 | 974,25 | 11.691 | 3 usuarios, 5.000 productos, 3 bancos, sin multibodega |
| ERP | Pro | 1.999 | 1.499,25 | 17.991 | 5 usuarios, multibodega, 10.000 productos, 6 bancos |
| ERP | Plus | 2.999 | 2.249,25 | 26.991 | 10 usuarios, 20.000 productos, 12 bancos |
| Soy Contador | Inicial | 490 | 441 | 5.292 | hasta 10 RFC activos |
| Soy Contador | Despacho | 990 | 891 | 10.692 | hasta 30 RFC activos |
| Soy Contador | Firma | 1.990 | 1.791 | 21.492 | hasta 75 RFC, soporte prioritario |

## Errores que ya están publicados en el portal (no repetirlos)

- **"RFC ilimitados" no existe.** Soy Contador topa en 10, 30 o 75 RFC según el plan.
- **"Contabilidad desde $499"** ya no existe: contabilidad con facturación = **ERP Inicial $974,25** (anual)
  o **Soy Contador desde $441** para despachos.
- **Facturación no tiene folios limitados**: son CFDI ilimitados; los planes viejos con "50/100/250
  facturas" desaparecieron.
- **El plan de entrada de Facturación no incluye contabilidad** ni multi-RFC.
- Los planes se llaman **Inicial / Pro / Plus** (y **Gastrobar** en POS). Ya no hay Emprendedor, Pyme,
  Lite ni Restobar.

## Backlog de correcciones (hoja "Ajuste de precios", superficie Programas de Contabilidad)

17 filas con URL exacta. Prioridad 1: PR-17, PR-20, PR-21, PR-22, PR-23, PR-24, PR-26, PR-27, PR-30.
Prioridad 2: PR-28, PR-29, PR-31, PR-32, PR-34. Prioridad 3: PR-25 (hecho: decimales en Bind), PR-33,
PR-35. Detalle completo en `prog-cont/backlog-precios-mx.md`.
