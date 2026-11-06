# Contexto Legal Avanzado por País

> Cargar este archivo cuando el artículo requiera validación de compliance fiscal,
> comparación de features regulatorios o cuando se mencione una norma específica.

---

## 🇲🇽 México — SAT / CFDI

### Marco regulatorio vigente
- **Ente:** Servicio de Administración Tributaria (SAT)
- **Comprobante fiscal:** CFDI (Comprobante Fiscal Digital por Internet)
- **Versión activa:** CFDI 4.0 (obligatoria desde enero 2022; CFDI 3.3 cancelado)
- **PAC:** Proveedor Autorizado de Certificación — intermediario obligatorio para timbrado

### CFDI 4.0 — Cambios críticos que deben reflejarse en software
1. **RFC del receptor obligatorio y validado:** El sistema debe verificar que el RFC existe en el listado del SAT en tiempo real. Los sistemas que no hacen esta verificación generan errores de timbrado.
2. **Régimen fiscal del receptor:** Nuevo campo obligatorio. Los sistemas deben almacenar y autocompletar el régimen fiscal por cliente.
3. **Uso del CFDI:** Campo "UsoCFDI" actualizado con nuevos valores. Catálogos deben estar actualizados.
4. **Domicilio fiscal:** Campo obligatorio del receptor. Impacto en base de datos de clientes.
5. **CFDI de nómina 1.2:** Complemento específico para nómina con campos de IMSS, INFONAVIT, ISR.

### Errores comunes de implementación
- **Error SAT 301:** RFC receptor no encontrado — causa: el sistema no validó contra lista del SAT o el cliente tiene RFC incorrecto.
- **Error SAT 305:** Régimen fiscal del receptor no corresponde al uso del CFDI — causa: catálogos no actualizados.
- **Complementos de pago:** Los sistemas que no generan automáticamente el CFDI de complemento de pago al registrar un cobro generan problemas de deducibilidad para el receptor.
- **Cancelación de CFDI:** Desde 2022, el receptor debe aceptar cancelaciones. Los sistemas sin flujo de cancelación automático generan fricciones operativas.

### Impuestos y retenciones que el sistema debe calcular
- IVA 16% general / 0% exportaciones / exento
- IVA fronterizo 8% (región fronteriza norte)
- IEPS (si aplica por giro)
- ISR retención (honorarios, arrendamiento)
- IVA retención (personas morales pagando a personas físicas)

### Declaraciones que el software debe facilitar
- **DIOT (Declaración Informativa de Operaciones con Terceros):** Mensual. Los softwares avanzados generan el archivo .txt directamente.
- **Declaración mensual de IVA/ISR**
- **Declaración anual personas físicas/morales**

### Integración bancaria relevante
- SPEI: transferencias en tiempo real. Los sistemas con conciliación bancaria deben reconocer referencias SPEI.
- CLABE interbancaria: campo obligatorio en pagos.

### Señales de que un software NO está al día en México
- No soporta CFDI 4.0 completo (algunos aún en 3.3)
- No genera DIOT automáticamente
- No valida RFC en tiempo real
- No tiene complemento de pago automático
- No maneja retenciones de IVA/ISR

---

## 🇨🇴 Colombia — DIAN / Facturación Electrónica

### Marco regulatorio vigente
- **Ente:** Dirección de Impuestos y Aduanas Nacionales (DIAN)
- **Comprobante:** Factura Electrónica de Venta
- **Estándar técnico:** UBL 2.1 (Universal Business Language)
- **Resolución clave:** Resolución 000042 de 2020 (base del sistema actual)
- **Habilitación obligatoria:** Según calendario DIAN, prácticamente todas las empresas deben estar habilitadas

### Documentos electrónicos que el sistema debe soportar
1. **Factura de venta electrónica:** Documento principal de venta
2. **Nota débito y nota crédito:** Ajustes a facturas emitidas
3. **Documento equivalente:** Para operaciones sin factura (tiquetes de máquina registradora electrónica)
4. **Nómina electrónica:** Obligatoria desde 2022 para empleadores habilitados. CUFE de nómina.

### Proceso técnico de emisión DIAN
1. Generación del XML en formato UBL 2.1
2. Firma digital con certificado habilitado
3. Validación previa en DIAN (sistema de validación en línea)
4. Envío al adquirente (receptor)
5. Acuse de recibo del adquirente (obligatorio para deducción)

### Errores comunes de implementación Colombia
- **Errores de validación CUFE:** El Código Único de Factura Electrónica debe generarse con el algoritmo SHA384 correcto. Errores aquí anulan la factura.
- **Nómina electrónica incompleta:** Muchos sistemas facturan bien pero no tienen módulo de nómina electrónica. Esto obliga a usar una herramienta separada.
- **Retención en la fuente:** Los sistemas deben calcular automáticamente retención en la fuente según concepto (honorarios, compras, servicios). Tablas deben estar actualizadas anualmente.
- **ICA (Impuesto de Industria y Comercio):** Varía por municipio. Los sistemas que no parametrizan por municipio generan declaraciones incorrectas.

### Obligaciones tributarias que el software debe facilitar
- Declaración IVA bimestral/cuatrimestral/anual (según tamaño)
- Retención en la fuente mensual
- ICA municipal
- Renta anual
- Información exógena DIAN (grandes contribuyentes)

### Señales de que un software NO está al día en Colombia
- No genera nómina electrónica con CUFE
- No valida en tiempo real con DIAN
- No calcula retenciones automáticamente
- No tiene módulo de información exógena

---

## 🇨🇷 Costa Rica — Ministerio de Hacienda / ATV

### Marco regulatorio vigente
- **Ente:** Ministerio de Hacienda
- **Sistema:** ATV (Administración Tributaria Virtual)
- **Comprobante:** Factura Electrónica, Tiquete Electrónico, Nota de Débito/Crédito, Comprobante de Retención
- **Versión:** Resolución DGT-R-48-2016 y actualizaciones

### Características técnicas
- **Formato:** XML con firma digital
- **Hacienda valida en tiempo real:** El sistema envía la factura a Hacienda y recibe confirmación (aceptada/rechazada/contingencia)
- **Modo contingencia:** Cuando Hacienda no responde, el sistema debe almacenar y reenviar. Los sistemas sin modo contingencia robusto generan facturas sin timbre válido.

### Impuestos que el sistema debe manejar
- **IVA (Impuesto al Valor Agregado):** 13% general. Tasas reducidas: 4% (medicamentos, materias primas), 2% (canasta básica), 1% (algunos productos)
- **Impuesto de Renta:** Declaración anual personas físicas y jurídicas
- **Retenciones de renta:** En pagos a no domiciliados

### Errores comunes CR
- Sistemas que no manejan las tasas diferenciadas de IVA (solo configuran 13% y no las reducidas)
- Falta de modo contingencia robusto
- No soportan todos los tipos de documento (tiquete vs factura vs comprobante retención)
- XML no pasa validación XSD de Hacienda por campos mal formateados

### Contexto de mercado CR
- Mercado más pequeño que MX/CO pero con obligatoriedad estricta
- Alta penetración de software cloud por tamaño del mercado
- Contadores certificados como "Contadores Públicos" (CPC) tienen rol importante en validación

---

## 🇩🇴 República Dominicana — DGII

### Marco regulatorio vigente
- **Ente:** Dirección General de Impuestos Internos (DGII)
- **Comprobante:** NCF (Número de Comprobante Fiscal)
- **Evolución:** Transición hacia e-CF (Comprobante Fiscal Electrónico) en proceso

### Estado actual de facturación electrónica
- El sistema de e-CF está en fase de implementación gradual
- Empresas grandes ya obligadas; la obligatoriedad se extiende progresivamente
- Los sistemas deben soportar NCF tradicional Y e-CF electrónico en paralelo durante la transición

### Impuestos clave
- **ITBIS (equivalente al IVA):** 18% general, 16% para algunos bienes
- **ISR:** Impuesto sobre la Renta personas físicas y jurídicas
- **Retenciones ITBIS:** En pagos entre contribuyentes designados

### Errores comunes RD
- Sistemas configurados para NCF pero no preparados para transición a e-CF
- Catálogos de tipos de comprobante desactualizados

---

## 🇵🇦 Panamá — DGI

### Marco regulatorio vigente
- **Ente:** Dirección General de Ingresos (DGI)
- **Facturación electrónica:** Sistema SFEP (Sistema de Facturación Electrónica de Panamá)
- **Estado:** Implementación en curso, obligatoriedad por sectores y tamaño de empresa

### Impuestos clave
- **ITBMS (Impuesto de Transferencia de Bienes Muebles y Servicios):** 7% general
- **Tasa reducida:** 10% para alcohol y hoteles; 15% para cigarrillos
- **Impuesto sobre la Renta**

### Nota de implementación
Panamá tiene menor presión de adopción de facturación electrónica vs MX/CO. Los sistemas que cubren Panamá deben documentar claramente qué tipo de emisor ya está obligado al SFEP y cuál puede aún usar factura física.

---

## Regla de oro de Leandro sobre contexto legal

> Nunca cruzar normas entre países. El CFDI es México. El CUFE es Colombia. El NCF es República Dominicana.  
> Si una feature fiscal no está documentada públicamente para el país en cuestión, escribir:  
> *"[Feature] no está documentado públicamente para [País] en la versión actual. Verificar directamente con el proveedor antes de tomar decisiones de implementación."*
