# Contexto legal por país — mercados activos de PdC

> Mercados cubiertos: **Colombia, México, Costa Rica y República Dominicana**.
> Panamá no se trabaja en este blog y no debe citarse como mercado.
>
> **Última verificación: 6 de noviembre de 2026.** Toda norma citada en un artículo
> lleva su número exacto y su enlace oficial. Si la norma cambió después de esta fecha,
> la ficha se actualiza antes de publicar; no se cita de memoria.

---

## 🇲🇽 México — SAT / CFDI

### Marco regulatorio vigente
- **Ente:** Servicio de Administración Tributaria (SAT)
- **Comprobante:** CFDI (Comprobante Fiscal Digital por Internet)
- **Versión vigente:** CFDI 4.0. En vigor desde el 1 de enero de 2022 y **única versión
  válida desde el 1 de abril de 2023**, cuando se inhabilitó la 3.3.
- **PAC:** Proveedor Autorizado de Certificación — intermediario obligatorio para el timbrado
- **Complementos relevantes:** Complemento de Pago (REP) 2.0, Carta Porte 3.1 (versión de
  referencia en 2026: confirmar la vigente en el portal del SAT antes de publicar),
  Nómina 1.2, Retenciones e Ingresos 2.0
- **Fuente oficial:** https://wwwmat.sat.gob.mx/ (Anexo 20 y matriz de errores)

### CFDI 4.0 — cambios críticos que el software debe reflejar
1. **RFC del receptor obligatorio y validado:** el sistema debe verificar que el RFC existe
   en el listado del SAT. Sin esa validación aparecen errores de timbrado.
2. **Régimen fiscal del receptor:** campo obligatorio; requiere catálogo actualizado y
   autocompletado por cliente.
3. **Uso del CFDI:** catálogo actualizado y coherente con el régimen del receptor.
4. **Nombre y domicilio fiscal del receptor obligatorios:** impacta la base de datos de
   clientes y la facturación de mostrador.
5. **Nómina 1.2:** complemento con campos de IMSS, INFONAVIT e ISR.

### Errores comunes de implementación
- **Error SAT 301:** RFC del receptor no encontrado — el sistema no validó contra la lista
  del SAT o el RFC está mal capturado.
- **Error SAT 305:** régimen fiscal del receptor incompatible con el uso del CFDI —
  catálogos desactualizados.
- **Complemento de pago:** sin REP automático al registrar el cobro, el receptor pierde
  deducibilidad.
- **Cancelación:** el receptor debe aceptar la cancelación; los sistemas sin ese flujo
  generan fricción operativa.
- **Lista 69-B (EFOS):** operar con proveedores señalados invalida deducciones.

### Impuestos y retenciones que el sistema debe calcular
- IVA 16% general / 0% exportación / exento
- IVA fronterizo 8% (región fronteriza norte)
- IEPS cuando aplique por giro
- ISR retención (honorarios, arrendamiento)
- IVA retención (personas morales pagando a personas físicas)

### Declaraciones que el software debe facilitar
- **DIOT:** mensual; los sistemas avanzados generan el archivo `.txt`.
- Declaración mensual de IVA/ISR y declaración anual.

### Integración bancaria relevante
- SPEI en tiempo real y CLABE interbancaria obligatoria en pagos.

### Señales de que un software no está al día en México
- No maneja CFDI 4.0 completo
- No genera DIOT automáticamente
- No valida el RFC en tiempo real
- No emite complemento de pago automático
- No maneja retenciones de IVA/ISR

---

## 🇨🇴 Colombia — DIAN / Sistema de Facturación Electrónica

### Marco regulatorio vigente
- **Ente:** Dirección de Impuestos y Aduanas Nacionales (DIAN)
- **Comprobante:** Factura Electrónica de Venta
- **Estándar técnico:** UBL 2.1
- **Norma base:** **Resolución DIAN 000165 del 1 de noviembre de 2023**, que reemplazó la
  Resolución 000042 de 2020 y adoptó el Anexo Técnico de Factura Electrónica de Venta
  **versión 1.9** y el Anexo Técnico 1.0 del documento equivalente electrónico.
- **Modificaciones posteriores:** Resolución 000188 de 2024 (documentos equivalentes
  electrónicos), **Resolución 000202 del 31 de marzo de 2025** (consulta y autocompletado
  de datos del adquirente) y **Resolución 000227 de 2025**, que compila y reubica las
  disposiciones del sistema de facturación dentro de la Resolución Única en Materia
  Tributaria, Aduanera y Cambiaria.
- **Identificadores:** CUFE (factura) y CUDE (documento electrónico)
- **RADIAN:** Resolución 000015 de 2021 y actualizaciones — registro de la factura como título valor
- **Nómina electrónica:** Resolución 000013 de 2021
- **Documento soporte con no obligados a facturar:** Resolución 000167 de 2021
- **Fuente oficial:** https://normograma.dian.gov.co/ y https://www.dian.gov.co/

> Citar la resolución con número y año. Escribir «Resolución 000042» en 2026 solo tiene
> sentido si el artículo habla de historia normativa.

### Documentos electrónicos que el sistema debe soportar
1. Factura de venta electrónica
2. Nota débito y nota crédito
3. Documento equivalente electrónico (incluye el tiquete POS, con anexo técnico propio)
4. Nómina electrónica con CUFE
5. Documento soporte en operaciones con no obligados a facturar

### Proceso técnico de emisión
1. Generación del XML en UBL 2.1
2. Firma digital con certificado habilitado
3. Transmisión y validación previa en la DIAN
4. Entrega al adquirente
5. Acuse de recibo del adquirente (relevante para deducción)
6. Conservación del XML

### Errores comunes de implementación
- **CUFE mal calculado:** anula el documento.
- **Nómina electrónica incompleta:** muchos sistemas facturan bien pero no liquidan nómina.
- **Retención en la fuente:** tablas que deben actualizarse cada año.
- **ICA:** parametrización por municipio; sin ella las declaraciones salen mal.
- **Documento equivalente:** sistemas que siguen emitiendo tiquete POS en papel después de
  la entrada del anexo electrónico.

### Impuestos y obligaciones que el software debe facilitar
- IVA general 19% (con bienes y servicios excluidos o exentos)
- Retención en la fuente mensual
- ICA municipal
- Renta anual
- Información exógena
- IVA bimestral o cuatrimestral según el caso

### Señales de que un software no está al día en Colombia
- No genera nómina electrónica con CUFE
- No transmite y valida en línea con la DIAN
- No calcula retenciones automáticamente
- No soporta el documento equivalente electrónico
- No tiene módulo de información exógena

---

## 🇨🇷 Costa Rica — Ministerio de Hacienda / TRIBU-CR

### Marco regulatorio vigente
- **Ente:** Ministerio de Hacienda, Dirección General de Tributación
- **Plataforma:** **TRIBU-CR**. El término «ATV» está descontinuado; usarlo invalida la
  credibilidad técnica del artículo.
- **Comprobantes:** Factura Electrónica, Tiquete Electrónico, Nota de Débito, Nota de
  Crédito, Comprobante de Retención y recibo electrónico de pago
- **Normativa:**
  - **Ley 9416** — medidas de control fiscal y lucha contra el fraude
  - **Decreto Ejecutivo 44739-H** — Reglamento de Comprobantes Electrónicos para Efectos Tributarios
  - **MH-DGT-RES-0027-2024** — disposiciones técnicas de los comprobantes electrónicos y **versión 4.4**
  - **MH-DGT-RES-0001-2025** — modificación del plazo de implementación general de la versión 4.4
- **Versión vigente:** **4.4**, operativa desde el **1 de septiembre de 2025**
- **Noviembre de 2026:** entran nuevos códigos de referencia (13 a 17, y 19 y 20) que cambian
  cómo se identifican anulaciones, correcciones, sustituciones y pagos
- **Declaración de IVA:** **formulario D-150**. Mencionar el D-101 en contexto de IVA es un
  error de contenido, no un detalle.

### Características técnicas
- XML firmado digitalmente, validado en TRIBU-CR con respuesta de aceptación, rechazo o
  aceptación parcial
- **Modo contingencia obligatorio:** si Hacienda no responde, el comprobante se almacena y
  se reenvía. Los sistemas sin contingencia robusta emiten documentos sin validez
- El D-150 se alimenta de los comprobantes aceptados; un sistema que clasifica mal los tipos
  de documento arrastra el error a la declaración

### Impuestos que el sistema debe manejar
- **IVA general 13%**, con tasas reducidas de 1%, 2% y 4% según el bien o servicio
- Impuesto de renta, personas físicas y jurídicas
- Retenciones en pagos a no domiciliados

### Errores comunes
- Configurar solo 13% e ignorar las tasas reducidas
- Contingencia débil o inexistente
- No distinguir tiquete, factura, nota y comprobante de retención
- XML que no pasa la validación por campos mal formateados
- Seguir hablando de ATV o del D-101

### Contexto de mercado
- Mercado más pequeño que México y Colombia, con obligatoriedad estricta
- Alta penetración de software en la nube
- El contador público juega un rol central en la validación
- **Tratamiento formal: «usted»**, en todo el contenido dirigido a Costa Rica

---

## 🇩🇴 República Dominicana — DGII / e-CF

### Marco regulatorio vigente
- **Ente:** Dirección General de Impuestos Internos (DGII)
- **Comprobante:** e-CF (Comprobante Fiscal Electrónico), secuencias tipo «E»
- **Normativa:**
  - **Ley 32-23 de Facturación Electrónica**, publicada el 16 de mayo de 2023
  - **Decreto 587-24**, del 10 de octubre de 2024, que reglamenta la Ley 32-23
- **Fuente oficial:** https://dgii.gov.do/

> Nombrar el país como «República Dominicana». La sigla suelta «RD» no se usa como nombre
> del país en el cuerpo del artículo.

### Estado del e-CF (no es «en transición»)
La facturación electrónica es obligatoria por grupos y el calendario está en su etapa final:
- **Grandes contribuyentes nacionales:** implementados entre enero y mayo de 2024
- **Grandes contribuyentes locales y medianos:** obligados desde 2025; desde el
  **1 de noviembre de 2026** emiten **exclusivamente e-CF tipo «E»**, y las secuencias
  tipo «B» solo son válidas hasta el **31 de octubre de 2026**, salvo contingencia
  (artículo 55 del Reglamento 587-24)
- **Pequeños, micro y no clasificados:** plazo del **15 de noviembre de 2026**
- **Prórroga:** individual, a solicitud, por única vez y hasta seis meses (artículo 8 del
  Decreto 587-24)
- **Nuevos inscritos en el RNC:** 120 días para incorporarse

### Estados del e-CF
Aceptado, Rechazado, Aceptado condicional, En proceso y Anulado. El estado «anulado» lo
incorporó el Decreto 587-24.

### Figuras que el sistema debe conocer
- **PSFE** — Proveedor de Servicios de Facturación Electrónica homologado por la DGII
- **Envío diferido** y mecanismos de contingencia del capítulo IX del Reglamento
- Certificados de firma digital emitidos por la DGII

### Impuestos clave
- **ITBIS 18%** general; 16% para algunos bienes
- ISR personas físicas y jurídicas
- Retenciones de ITBIS en pagos entre contribuyentes designados

### Errores comunes
- Sistemas que siguen emitiendo comprobantes tipo «B» fuera de contingencia
- Catálogos de tipos de comprobante desactualizados
- No manejar los cinco estados del e-CF
- No soportar el envío diferido cuando el contribuyente lo usa

---

## Regla de oro sobre contexto legal

> Nunca cruzar normas entre países. El CFDI es México. El CUFE es Colombia. TRIBU-CR es
> Costa Rica. El e-CF es República Dominicana.
>
> Si una función fiscal no está documentada públicamente para el país en cuestión, escribir:
> *«[Función] no está documentado públicamente para [País] en la versión actual. Verificar
> directamente con el proveedor antes de tomar decisiones de implementación.»*
>
> Toda cifra, tarifa o plazo va con su norma y su fecha. Si no hay fuente oficial enlazada,
> el dato no se publica.
