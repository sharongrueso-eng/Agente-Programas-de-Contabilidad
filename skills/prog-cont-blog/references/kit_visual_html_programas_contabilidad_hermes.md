# Biblioteca de bloques HTML editoriales --- Programas de Contabilidad

## Guía de implementación para Hermes

### Propósito

Incorporar componentes HTML reutilizables en los artículos de
**Programas de Contabilidad** para enriquecer la lectura, organizar
información compleja y ayudar al lector a comparar y evaluar soluciones
de software.

Los bloques deben funcionar como recursos editoriales: cada uno debe
facilitar la comprensión de una idea, resumir información relevante o
apoyar una decisión. No deben utilizarse como decoración ni repetirse
mecánicamente en todos los artículos.

### Instrucción principal

Desarrolla y utiliza una biblioteca de bloques HTML que respete **la
identidad visual que ya tiene ProgramasContabilidad.com**.

-   Antes de definir estilos, inspecciona la web actual, su logotipo,
    cabecera, botones, tipografías, fondos, colores, bordes y
    componentes existentes.
-   Extrae los colores y tokens visuales reales del sitio. No inventes
    una paleta nueva ni reutilices automáticamente la de otro proyecto.
-   Mantén coherencia con el diseño actual del blog y con sus estilos
    globales.
-   Los ejemplos incluidos en este documento son estructuras de
    referencia. Adapta sus colores, tipografías, radios, sombras y
    espaciados a los tokens reales del sitio.
-   Evita que los estilos de los bloques alteren otros elementos del
    artículo o del tema de WordPress.

------------------------------------------------------------------------

## 1. Principios de diseño y desarrollo

### Identidad visual

1.  Usar los colores reales de la web, identificados mediante inspección
    del sitio y sus estilos.
2.  Respetar las tipografías y jerarquías tipográficas existentes.
3.  Mantener contraste suficiente entre texto y fondo.
4.  Utilizar acentos de marca para destacar datos, etiquetas y elementos
    de navegación, sin saturar el diseño.
5.  Evitar estilos visuales genéricos que hagan que los bloques parezcan
    insertados desde otra plantilla.

### Experiencia de lectura

-   Diseñar primero para lectura rápida, sin sacrificar contexto.
-   Utilizar títulos breves y descriptivos.
-   Separar visualmente conceptos, datos y conclusiones.
-   Mantener párrafos concisos y una longitud de línea cómoda.
-   Evitar tarjetas con demasiado texto. Si el contenido es extenso,
    elegir una tabla, lista estructurada o bloque de análisis.
-   En móvil, reorganizar las columnas en una sola columna o en el
    patrón más legible.

### Requisitos técnicos para WordPress

-   El código debe poder insertarse en un bloque **HTML personalizado**.
-   Encapsular los estilos con un prefijo único, por ejemplo `pc-`, para
    reducir conflictos con el tema.
-   No utilizar selectores globales como `h4`, `p`, `a` o `div` sin
    limitarlos al contenedor del componente.
-   Preferir CSS Grid y Flexbox con reglas responsivas.
-   No depender de JavaScript para la presentación básica.
-   No cargar librerías externas, fuentes, iconos ni scripts sin
    autorización.
-   No incluir estilos que afecten al resto de la entrada.
-   Comprobar que el editor y la configuración de WordPress permiten
    conservar las etiquetas `<style>`. Si las eliminan, entregar el CSS
    en el mecanismo global autorizado por el proyecto y dejar el HTML
    del bloque en el artículo.
-   Mantener los enlaces como enlaces HTML estándar y descriptivos.
-   Utilizar HTML semántico siempre que sea posible.

### Integridad editorial

-   No inventar precios, puntuaciones, rankings, disponibilidad,
    integraciones, funcionalidades ni resultados.
-   No mostrar porcentajes, barras de progreso o indicadores como si
    fueran mediciones reales cuando no existe una metodología y una
    fuente que los respalde.
-   Diferenciar con claridad los ejemplos ilustrativos de los datos
    verificados.
-   En comparativas, usar los mismos criterios para todos los
    proveedores y señalar diferencias de plan, país, fecha o
    condiciones.
-   Si un dato no está verificado, no convertirlo en un indicador
    visual. Marcarlo para revisión o excluirlo.
-   Los bloques no deben cambiar el sentido de la información original.

------------------------------------------------------------------------

# 2. Componentes propuestos

La biblioteca inicial contempla tres componentes principales:

1.  **Tech Cards:** tarjetas para explicar funcionalidades, criterios o
    conceptos.
2.  **Software Comparison:** comparador estructurado de dos o más
    soluciones.
3.  **Tech Dashboard:** panel de indicadores para resumir datos
    verificables.

Cada componente responde a una necesidad editorial distinta. Hermes debe
seleccionar el que mejor se adapte al contenido, no insertar los tres
por defecto.

------------------------------------------------------------------------

# 3. Componente 1 --- Tech Cards

## Objetivo

Organizar tres conceptos relacionados en tarjetas visuales. Facilita la
lectura de funcionalidades, criterios de evaluación, características o
etapas de un proceso.

## Cuándo utilizarlo

-   Explicar funcionalidades de un software.
-   Presentar criterios para elegir una herramienta.
-   Resumir características de una categoría de software.
-   Desglosar tres ventajas, limitaciones o aspectos que el lector debe
    evaluar.
-   Presentar pasos o conceptos que tengan una jerarquía similar.

## Reglas editoriales

-   Preferir tres tarjetas cuando el contenido lo permita.
-   Cada tarjeta debe contener una etiqueta o número, un título y una
    explicación breve.
-   Mantener una extensión equilibrada entre tarjetas.
-   No forzar tres columnas si el contenido necesita más espacio.
-   Si hay cuatro o más elementos, valorar una cuadrícula de dos o tres
    columnas según la longitud del texto.
-   No convertir afirmaciones no verificadas en claims.

## Ejemplo HTML

> Los valores de las variables CSS deben conectarse con los colores y
> tokens reales del sitio. No asignar colores nuevos por defecto.

``` html
<style>
.pc-tech-cards {
  /* Conectar estas variables con los tokens reales del sitio. */
  --pc-brand-primary: var(--site-primary);
  --pc-brand-secondary: var(--site-secondary);
  --pc-brand-accent: var(--site-accent);
  --pc-surface: var(--site-surface);
  --pc-text: var(--site-text);
  --pc-muted: var(--site-muted);
  --pc-border: var(--site-border);

  margin: 24px 0;
  color: var(--pc-text);
}

.pc-tech-cards,
.pc-tech-cards * {
  box-sizing: border-box;
}

.pc-tech-cards__eyebrow {
  margin: 0 0 10px;
  color: var(--pc-brand-secondary);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 1.4px;
  text-transform: uppercase;
}

.pc-tech-cards__title {
  margin: 0 0 18px;
  color: var(--pc-text);
  font-size: clamp(21px, 3vw, 28px);
  line-height: 1.25;
}

.pc-tech-cards__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.pc-tech-cards__item {
  min-width: 0;
  padding: 22px;
  border: 1px solid var(--pc-border);
  border-radius: var(--site-card-radius, 12px);
  background: var(--pc-surface);
}

.pc-tech-cards__number {
  display: block;
  margin-bottom: 18px;
  color: var(--pc-brand-accent);
  font-size: 25px;
  font-weight: 800;
}

.pc-tech-cards__item h4 {
  margin: 0 0 9px;
  color: var(--pc-text);
  font-size: 18px;
  line-height: 1.3;
}

.pc-tech-cards__item p {
  margin: 0;
  color: var(--pc-muted);
  font-size: 14px;
  line-height: 1.65;
}

@media (max-width: 680px) {
  .pc-tech-cards__grid {
    grid-template-columns: 1fr;
  }
}
</style>

<section class="pc-tech-cards" aria-labelledby="pc-tech-cards-title">
  <p class="pc-tech-cards__eyebrow">Análisis de software</p>
  <h3 class="pc-tech-cards__title" id="pc-tech-cards-title">
    ¿Qué debes evaluar en un software contable?
  </h3>

  <div class="pc-tech-cards__grid">
    <article class="pc-tech-cards__item">
      <span class="pc-tech-cards__number">01</span>
      <h4>Tecnología cloud</h4>
      <p>Evalúa el acceso remoto, la disponibilidad y la forma en que se actualiza la plataforma.</p>
    </article>

    <article class="pc-tech-cards__item">
      <span class="pc-tech-cards__number">02</span>
      <h4>Integraciones</h4>
      <p>Comprueba su conexión con bancos, plataformas de pago y otros sistemas de trabajo.</p>
    </article>

    <article class="pc-tech-cards__item">
      <span class="pc-tech-cards__number">03</span>
      <h4>Reportes</h4>
      <p>Revisa qué informes ofrece y si permiten consultar la información que necesita el negocio.</p>
    </article>
  </div>
</section>
```

### Personalización permitida

Hermes puede adaptar la cantidad de tarjetas, sus títulos, el texto y la
distribución de columnas. Debe conservar el sistema de clases
encapsulado y los tokens visuales del sitio.

------------------------------------------------------------------------

# 4. Componente 2 --- Software Comparison

## Objetivo

Comparar dos soluciones de software con criterios equivalentes para que
el lector identifique semejanzas, diferencias y condiciones relevantes.

## Cuándo utilizarlo

-   Comparativas entre dos programas.
-   Artículos del tipo «A vs. B».
-   Comparación de planes o funcionalidades.
-   Análisis de software contable, ERP, POS, nómina o facturación.
-   Evaluación de integraciones, límites, soporte y modalidades.

## Reglas editoriales

1.  Comparar criterios equivalentes y relevantes para el lector.
2.  Identificar claramente cada proveedor o plan.
3.  Utilizar estados comprensibles: «Incluido», «No disponible», «Según
    plan», «Con integración» o «Por confirmar», siempre que estén
    respaldados.
4.  No asumir que una función está incluida en todos los planes.
5.  Indicar país, plan y fecha de consulta cuando puedan cambiar los
    resultados.
6.  Evitar declarar un ganador si no existe una metodología explícita.
7.  En móvil, permitir una lectura ordenada de cada criterio y sus
    resultados.

## Ejemplo HTML

``` html
<style>
.pc-comparison {
  --pc-primary: var(--site-primary);
  --pc-secondary: var(--site-secondary);
  --pc-accent: var(--site-accent);
  --pc-surface: var(--site-surface);
  --pc-soft: var(--site-surface-secondary);
  --pc-text: var(--site-text);
  --pc-muted: var(--site-muted);
  --pc-border: var(--site-border);

  margin: 24px 0;
  color: var(--pc-text);
}

.pc-comparison,
.pc-comparison * {
  box-sizing: border-box;
}

.pc-comparison__eyebrow {
  margin: 0 0 9px;
  color: var(--pc-secondary);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 1.4px;
  text-transform: uppercase;
}

.pc-comparison__title {
  margin: 0 0 18px;
  color: var(--pc-text);
  font-size: clamp(21px, 3vw, 28px);
  line-height: 1.25;
}

.pc-comparison__products {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.pc-comparison__product {
  padding: 18px;
  border-radius: var(--site-card-radius, 12px);
  background: var(--pc-primary);
  color: var(--site-on-primary, #fff);
}

.pc-comparison__product:nth-child(2) {
  background: var(--pc-secondary);
}

.pc-comparison__product span {
  display: block;
  margin-bottom: 7px;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 1px;
}

.pc-comparison__product h4 {
  margin: 0 0 4px;
  color: inherit;
  font-size: 20px;
}

.pc-comparison__product p {
  margin: 0;
  color: inherit;
  font-size: 12px;
}

.pc-comparison__table-wrap {
  overflow-x: auto;
  border: 1px solid var(--pc-border);
  border-radius: var(--site-card-radius, 12px);
}

.pc-comparison__table {
  width: 100%;
  border-collapse: collapse;
  background: var(--pc-surface);
}

.pc-comparison__table th,
.pc-comparison__table td {
  padding: 13px 12px;
  border-bottom: 1px solid var(--pc-border);
  text-align: left;
  font-size: 13px;
  vertical-align: middle;
}

.pc-comparison__table th {
  background: var(--pc-soft);
  color: var(--pc-text);
  font-size: 11px;
  font-weight: 800;
}

.pc-comparison__table td:first-child {
  color: var(--pc-text);
  font-weight: 700;
}

.pc-comparison__table tr:last-child td {
  border-bottom: 0;
}

.pc-comparison__note {
  margin: 11px 0 0;
  color: var(--pc-muted);
  font-size: 11px;
  line-height: 1.5;
}

@media (max-width: 560px) {
  .pc-comparison__products {
    grid-template-columns: 1fr;
  }

  .pc-comparison__table th,
  .pc-comparison__table td {
    padding: 10px 8px;
    font-size: 12px;
  }
}
</style>

<section class="pc-comparison" aria-labelledby="pc-comparison-title">
  <p class="pc-comparison__eyebrow">Comparativa de software</p>
  <h3 class="pc-comparison__title" id="pc-comparison-title">
    Compara funcionalidades
  </h3>

  <div class="pc-comparison__products">
    <article class="pc-comparison__product">
      <span>Solución A</span>
      <h4>Software A</h4>
      <p>Descripción o categoría del producto</p>
    </article>

    <article class="pc-comparison__product">
      <span>Solución B</span>
      <h4>Software B</h4>
      <p>Descripción o categoría del producto</p>
    </article>
  </div>

  <div class="pc-comparison__table-wrap">
    <table class="pc-comparison__table">
      <thead>
        <tr>
          <th scope="col">Funcionalidad</th>
          <th scope="col">Software A</th>
          <th scope="col">Software B</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>Facturación electrónica</td>
          <td>Dato verificado</td>
          <td>Dato verificado</td>
        </tr>
        <tr>
          <td>Conciliación bancaria</td>
          <td>Dato verificado</td>
          <td>Dato verificado</td>
        </tr>
        <tr>
          <td>Inventario</td>
          <td>Dato verificado</td>
          <td>Dato verificado</td>
        </tr>
        <tr>
          <td>API e integraciones</td>
          <td>Dato verificado</td>
          <td>Dato verificado</td>
        </tr>
      </tbody>
    </table>
  </div>

  <p class="pc-comparison__note">
    Indica la fecha de consulta, el país y los planes revisados cuando corresponda.
  </p>
</section>
```

### Personalización permitida

Hermes puede añadir o quitar filas, adaptar los encabezados, comparar
más criterios y cambiar los nombres de las soluciones. Para tres o más
proveedores, debe evaluar si una tabla sigue siendo legible o si
conviene una comparación por fichas.

------------------------------------------------------------------------

# 5. Componente 3 --- Tech Dashboard

## Objetivo

Presentar un resumen visual de datos cuantitativos o criterios de
evaluación. Permite destacar información importante sin obligar al
lector a interpretar varios párrafos.

## Cuándo utilizarlo

-   Resumir características verificadas.
-   Mostrar cantidad de usuarios, integraciones o módulos cuando exista
    fuente.
-   Presentar métricas de una investigación.
-   Comparar dimensiones de una evaluación.
-   Sintetizar resultados de una encuesta o análisis propio.
-   Mostrar indicadores de precios, límites o capacidades.

## Reglas editoriales

-   Cada indicador debe tener fuente, fecha y contexto.
-   No utilizar porcentajes decorativos.
-   No presentar una escala de evaluación sin explicar su metodología.
-   Las barras de progreso solo se usan si representan datos reales y
    comparables.
-   No confundir cantidad de funcionalidades con calidad del software.
-   Cuando no existan métricas cuantitativas, reemplazar el dashboard
    por una ficha de criterios cualitativos.
-   Incluir una nota que explique cómo interpretar los indicadores.

## Ejemplo HTML

``` html
<style>
.pc-dashboard {
  --pc-primary: var(--site-primary);
  --pc-secondary: var(--site-secondary);
  --pc-accent: var(--site-accent);
  --pc-surface: var(--site-surface);
  --pc-soft: var(--site-surface-secondary);
  --pc-text: var(--site-text);
  --pc-muted: var(--site-muted);
  --pc-border: var(--site-border);

  margin: 24px 0;
  color: var(--pc-text);
}

.pc-dashboard,
.pc-dashboard * {
  box-sizing: border-box;
}

.pc-dashboard__eyebrow {
  margin: 0 0 10px;
  color: var(--pc-secondary);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 1.4px;
  text-transform: uppercase;
}

.pc-dashboard__panel {
  padding: 22px;
  border-radius: var(--site-card-radius, 12px);
  background: var(--pc-primary);
}

.pc-dashboard__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 18px;
}

.pc-dashboard__top h3 {
  margin: 0;
  color: var(--site-on-primary, #fff);
  font-size: 22px;
}

.pc-dashboard__tag {
  padding: 5px 8px;
  border-radius: 5px;
  background: var(--pc-accent);
  color: var(--site-on-accent, #111);
  font-size: 10px;
  font-weight: 800;
}

.pc-dashboard__kpis {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.pc-dashboard__kpi {
  padding: 16px;
  border-radius: 9px;
  background: var(--pc-secondary);
}

.pc-dashboard__kpi span {
  display: block;
  color: var(--site-on-secondary, #fff);
  font-size: 12px;
}

.pc-dashboard__kpi strong {
  display: block;
  margin: 7px 0;
  color: var(--site-on-secondary, #fff);
  font-size: 30px;
}

.pc-dashboard__kpi small {
  color: var(--site-on-secondary, #fff);
  font-size: 11px;
}

.pc-dashboard__content {
  padding: 18px;
  border-radius: 9px;
  background: var(--pc-surface);
}

.pc-dashboard__content h4 {
  margin: 0 0 16px;
  color: var(--pc-text);
  font-size: 15px;
}

.pc-dashboard__metric {
  margin-bottom: 15px;
}

.pc-dashboard__metric:last-child {
  margin-bottom: 0;
}

.pc-dashboard__metric-label {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 7px;
  color: var(--pc-text);
  font-size: 12px;
}

.pc-dashboard__track {
  height: 9px;
  overflow: hidden;
  border-radius: 20px;
  background: var(--pc-soft);
}

.pc-dashboard__fill {
  height: 100%;
  border-radius: 20px;
  background: var(--pc-accent);
}

.pc-dashboard__note {
  margin: 12px 0 0;
  color: var(--pc-muted);
  font-size: 11px;
  line-height: 1.5;
}

.pc-dashboard__insight {
  margin-top: 14px;
  padding: 16px;
  border: 1px solid var(--pc-border);
  border-left: 4px solid var(--pc-accent);
  border-radius: 8px;
  background: var(--pc-soft);
}

.pc-dashboard__insight strong {
  color: var(--pc-secondary);
  font-size: 11px;
  letter-spacing: 1px;
}

.pc-dashboard__insight p {
  margin: 7px 0 0;
  color: var(--pc-text);
  font-size: 13px;
  line-height: 1.6;
}

@media (max-width: 480px) {
  .pc-dashboard__panel {
    padding: 15px;
  }
}
</style>

<section class="pc-dashboard" aria-labelledby="pc-dashboard-title">
  <p class="pc-dashboard__eyebrow">Panel de evaluación</p>

  <div class="pc-dashboard__panel">
    <div class="pc-dashboard__top">
      <h3 id="pc-dashboard-title">Resumen de análisis</h3>
      <span class="pc-dashboard__tag">Datos verificados</span>
    </div>

    <div class="pc-dashboard__kpis">
      <div class="pc-dashboard__kpi">
        <span>Indicador 1</span>
        <strong>24</strong>
        <small>Unidad y fuente</small>
      </div>

      <div class="pc-dashboard__kpi">
        <span>Indicador 2</span>
        <strong>08</strong>
        <small>Unidad y fuente</small>
      </div>
    </div>

    <div class="pc-dashboard__content">
      <h4>Dimensiones evaluadas</h4>

      <div class="pc-dashboard__metric">
        <div class="pc-dashboard__metric-label">
          <span>Criterio A</span>
          <strong>90%</strong>
        </div>
        <div class="pc-dashboard__track">
          <div class="pc-dashboard__fill" style="width:90%"></div>
        </div>
      </div>

      <div class="pc-dashboard__metric">
        <div class="pc-dashboard__metric-label">
          <span>Criterio B</span>
          <strong>75%</strong>
        </div>
        <div class="pc-dashboard__track">
          <div class="pc-dashboard__fill" style="width:75%"></div>
        </div>
      </div>
    </div>

    <p class="pc-dashboard__note">
      Añade aquí la metodología, el período analizado y la fuente de los datos.
    </p>
  </div>

  <div class="pc-dashboard__insight">
    <strong>LECTURA DEL ANÁLISIS</strong>
    <p>Explica en pocas líneas qué significan los indicadores y qué debe tener en cuenta el lector.</p>
  </div>
</section>
```

**Importante:** las cifras y porcentajes del código son valores de
demostración. Hermes debe sustituirlos por datos respaldados antes de
publicar. Si no hay datos cuantitativos, no debe publicar el ejemplo con
esos valores.

------------------------------------------------------------------------

# 6. Cómo elegir el componente adecuado

  Necesidad del artículo                    Componente recomendado
  ----------------------------------------- ---------------------------------
  Explicar tres funcionalidades             Tech Cards
  Presentar criterios de selección          Tech Cards
  Comparar dos proveedores                  Software Comparison
  Comparar planes y precios                 Software Comparison
  Resumir resultados de una investigación   Tech Dashboard
  Mostrar métricas verificadas              Tech Dashboard
  Explicar ventajas y limitaciones          Tech Cards o fichas específicas
  Presentar una guía de evaluación          Tech Cards o checklist derivado

## No insertar bloques por obligación

Hermes debe analizar el contenido y determinar si un bloque aporta valor
real.

No añadir un componente cuando:

-   El texto ya se entiende con claridad.
-   La información no puede resumirse sin perder precisión.
-   El bloque repetiría una tabla o explicación que ya existe.
-   No hay fuentes para respaldar los datos.
-   La estructura visual interrumpiría el flujo de lectura.

------------------------------------------------------------------------

# 7. Reglas de adaptación visual

Los tres ejemplos usan variables CSS de referencia. Antes de generar un
bloque, Hermes debe:

1.  Inspeccionar la identidad visual actual de
    ProgramasContabilidad.com.
2.  Identificar las variables CSS o estilos reales del tema.
3.  Mapear `--site-primary`, `--site-secondary`, `--site-accent`,
    `--site-surface`, `--site-surface-secondary`, `--site-text`,
    `--site-muted` y `--site-border` a los valores reales.
4.  Definir los colores de texto sobre fondos de marca para garantizar
    contraste.
5.  Ajustar radios, bordes, sombras, tipografías y espaciados a los
    componentes actuales.
6.  Mantener las clases con prefijo `pc-` para evitar colisiones.
7.  Probar el resultado en escritorio y móvil.

**No crear una nueva paleta ni introducir colores que no pertenezcan a
la identidad vigente.** Si no se pueden identificar los valores exactos,
solicitar la referencia visual o dejar el bloque pendiente de ajuste; no
inventar códigos HEX.

------------------------------------------------------------------------

# 8. Accesibilidad, SEO y rendimiento

### Accesibilidad

-   Usar encabezados en orden jerárquico.
-   Mantener contraste suficiente.
-   No depender únicamente del color para comunicar estados.
-   Incluir nombres descriptivos en enlaces.
-   Utilizar `scope="col"` en encabezados de tablas.
-   Evitar textos demasiado pequeños.
-   No convertir párrafos completos en imágenes.

### SEO

-   Mantener el contenido importante como texto HTML indexable.
-   Usar títulos descriptivos y coherentes con la estructura del
    artículo.
-   No repetir palabras clave de forma artificial.
-   No esconder información relevante dentro de elementos que solo
    funcionan con JavaScript.
-   Los bloques deben complementar el contenido, no sustituir
    explicaciones necesarias.

### Rendimiento

-   No incorporar librerías externas para componentes sencillos.
-   Evitar scripts innecesarios.
-   Mantener CSS compacto y encapsulado.
-   No cargar recursos gráficos si el componente funciona correctamente
    sin ellos.

------------------------------------------------------------------------

# 9. Checklist de control antes de entregar

-   [ ] El bloque responde a una necesidad real del artículo.
-   [ ] El contenido coincide con la fuente editorial.
-   [ ] No se inventaron precios, métricas, rankings ni funcionalidades.
-   [ ] Los colores corresponden a la identidad actual del blog.
-   [ ] La tipografía y los espaciados son coherentes con la web.
-   [ ] Las clases CSS están encapsuladas con prefijo `pc-`.
-   [ ] El HTML puede insertarse en WordPress.
-   [ ] La visualización funciona en escritorio.
-   [ ] La visualización funciona en móvil.
-   [ ] No se alteran otros elementos del tema.
-   [ ] Las tablas y enlaces son accesibles.
-   [ ] Los datos comparativos tienen fuente, país, plan y fecha cuando
    corresponde.

------------------------------------------------------------------------

# 10. Instrucción final para Hermes

Actúa como desarrollador frontend especializado en WordPress y diseñador
de componentes editoriales para Programas de Contabilidad.

Tu tarea es enriquecer los artículos mediante bloques HTML que ayuden al
lector a comprender, comparar y evaluar software.

Utiliza esta biblioteca como punto de partida, pero adapta cada
componente al contenido específico de la URL intervenida.

**Prioridades, en este orden:**

1.  Exactitud y fidelidad de la información.
2.  Utilidad editorial para el lector.
3.  Coherencia con la identidad visual real del blog.
4.  Legibilidad y accesibilidad.
5.  Compatibilidad con WordPress y dispositivos móviles.
6.  Rendimiento y mantenimiento del código.

No fuerces componentes, no inventes datos y no crees una identidad
visual paralela. El resultado debe sentirse como una parte nativa de
ProgramasContabilidad.com.
