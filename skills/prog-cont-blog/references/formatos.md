# Reseña y comparativa — plantillas exactas

Ambas salen en **bloques Gutenberg** (el sitio no renderiza bien el HTML plano en el editor).
Los callouts van con `<!-- wp:html -->`.

## Callout (único estilo de marca del portal)

```html
<!-- wp:html -->
<div style="background:#cce4f7;border-left:8px solid #159bd7;padding:18px 32px;margin:24px 0">
<p style="margin:0"><strong>Título del aviso.</strong> Texto del aviso.</p>
</div>
<!-- /wp:html -->
```

## Tabla comparativa

```html
<!-- wp:table {"className":"is-style-stripes","style":{"color":{"background":"#cce4f7"}}} -->
<figure class="wp-block-table is-style-stripes"><table class="has-background has-fixed-layout" style="background-color:#cce4f7"><thead><tr><th>Aspecto</th><th>Opción A</th><th>Opción B</th></tr></thead><tbody>
<tr><td>Enfoque</td><td>…</td><td>…</td></tr>
</tbody></table></figure>
<!-- /wp:table -->
```

## H2 con el color del tema

```html
<!-- wp:heading {"style":{"elements":{"link":{"color":{"text":"var:preset|color|theme-secondary"}}}},"textColor":"theme-secondary"} -->
<h2 class="wp-block-heading has-theme-secondary-color has-text-color has-link-color">Título</h2>
<!-- /wp:heading -->
```

## Esqueleto de reseña

1. H2 `[Software] reseña: ficha rápida` + tabla: qué es · país · precio de entrada · facturación
electrónica · ideal para · punto débil.
2. H2 `¿Qué es [software]?`
3. H2 `Funciones y módulos principales` (H3 por bloque: facturación, inventario, contabilidad, POS)
4. H2 `¿Cómo funciona [software]?`
5. H2 `Precios publicados de [software] en {año}` + tabla, solo si los precios aportan a la
   decisión; sin fecha de consulta
6. H2 `[Software] y la facturación electrónica en {país}` (norma local: CFDI/SAT, DIAN, TRIBU-CR,
e-CF/DGII, SUNAT, DGI/ITBMS)
7. H2 `Ventajas y puntos de atención` con H3 `👍 Ventajas` / `👎 Puntos de atención`
8. H2 `¿Para quién puede ser adecuado [software]?`
9. H2 `¿Qué debe preguntar antes de implementar [software]?`
10. H2 `Veredicto: ¿vale la pena [software]?`
11. H2 `Preguntas frecuentes` + H3 por pregunta
12. H2 `Fuentes y fecha de actualización`

## Esqueleto de comparativa

1. H2 `Respuesta rápida: ¿A o B?` — dos párrafos: "Conviene A si…", "Considera B si…"
2. H2 `A vs. B: diferencias principales` — tabla (enfoque, mercado, facturación, inventario,
   contabilidad, precios, curva de adopción).
3. H2 `¿Qué es A?` + H2 `Precios publicados de A en {país}`
4. H2 `¿Qué es B?` + H2 `Planes publicados de B`
5. H2 `¿Cuál conviene según tu operación?` + H3 por perfil (servicios profesionales, comercio,
   varias sucursales, manufactura).
6. H2 `Checklist antes de contratar` (lista numerada de 5-7 puntos verificables)
7. H2 `Veredicto: ¿A o B?`
8. H2 `Preguntas frecuentes` + H3
9. H2 `Fuentes y fecha de actualización`

## Reglas de redacción

- Párrafo máximo 4 líneas; frases cortas; nada de "en el mundo actual".
- Cada afirmación de precio o función debe poder rastrearse a la página oficial citada.
- Nada de datos de otro país: si la pieza es de México, no se habla de DIAN.
- Nada de superlativos sin número: "el más barato" solo si se compara el precio publicado.
- La mención de Alegra va condicionada a un perfil ("si tu prioridad es X…"), nunca como conclusión
  absoluta, y con un solo enlace con UTM.
