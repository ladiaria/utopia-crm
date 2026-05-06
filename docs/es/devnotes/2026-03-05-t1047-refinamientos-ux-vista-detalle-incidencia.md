# Vista de Detalle de Incidencia: Refinamientos de UX y Mejoras de Compacidad

**Fecha:** 2026-03-05
**Tipo:** Mejora de UI/UX
**Componente:** Sistema de Gestión de Incidencias
**Impacto:** Experiencia de Usuario, Usabilidad, Diseño Visual
**Incidencia:** t1047

## Resumen

Siguiendo la retroalimentación de usuarios sobre el rediseño t1044, esta actualización refina la Vista de Detalle de Incidencia con un diseño más compacto y menos colorido, enfocado en maximizar el contenido visible y minimizar el desplazamiento. Las mejoras clave incluyen la eliminación de la barra lateral de actividades, reordenamiento de secciones para priorizar el formulario, reducción de ruido visual, implementación de textareas auto-expandibles, y colapso inteligente de notas.

## Cambios

### 1. Eliminación de la Barra Lateral de Actividades

**Justificación:** Los usuarios reportaron no usar la funcionalidad de actividades, y la barra lateral consumía valioso espacio horizontal.

- **Eliminada toda la columna derecha** (lista de actividades + modal de actividad)
- **Diseño de ancho completo** — el formulario ahora usa todo el ancho de pantalla
- **Limpieza del contexto de la vista** — eliminados `activities`, `activity_form` e `invoice_list` de `IssueDetailView.get_context_data()`
- **Beneficio de rendimiento** — elimina consultas innecesarias a la base de datos para actividades y facturas

**Archivos Modificados:**

- `support/templates/view_issue.html` — eliminada barra lateral de actividades y HTML del modal
- `support/views/all_views.py` — eliminada inicialización de activity_form y datos de contexto

### 2. Reordenamiento de Secciones para Mejor Flujo de Trabajo

**Nuevo Orden (de arriba hacia abajo):**

1. **Badges del encabezado** — Categoría, Subcategoría, Estado (compactos, colores apagados)
2. **Alerta de deuda** (solo incidencias de facturación) — barra amarilla con enlace "Ver facturas"
3. **Clasificación** — Subcategoría + Resolución
4. **Estado y Asignación** — Estado, Asignado a, Fecha próxima acción, Copias, Sobre
5. **Notas de progreso** — Textarea grande para seguimiento principal de progreso
6. **Respuesta 1 / Respuesta 2** — División 4/8 columnas para mejores proporciones
7. **Información de contacto** — Visualización compacta de una línea al final
8. **Notas** — Sección colapsable al final

**Justificación:** Los usuarios querían ver el formulario/progreso inmediatamente al abrir una incidencia, con la información de contacto accesible pero sin ocupar espacio principal de pantalla.

### 3. Diseño Menos Colorido y Más Compacto

**Cambios Visuales:**

- **Eliminados fondos de sección coloreados** — reemplazadas secciones con `background-color: #f8f9fa` por simples separadores de borde
- **Colores de badge apagados** — cambiados de `badge-pill badge-primary/info/secondary` a `badge-dark/badge-secondary`
- **Eliminados la mayoría de íconos** — eliminados íconos FontAwesome de títulos de sección y etiquetas
- **Tipografía más pequeña:**
  - Etiquetas: `0.7rem` (era `0.75rem`)
  - Etiquetas de formulario: `0.75rem` (era default)
  - Controles de formulario: `0.85rem` con `padding: 0.25rem 0.5rem`
  - Títulos de sección: `0.7rem` (era `0.8rem`)
- **Espaciado más ajustado:**
  - Grupos de formulario: `margin-bottom: 0.4rem` (era `0.75rem`)
  - Padding de sección: `0.5rem 0` (era `0.75rem 1rem`)
  - Márgenes de tarjeta: `0.5rem` (era default)

**Clases CSS:**

```css
.issue-section { border-bottom: 1px solid #e9ecef; padding: 0.5rem 0; }
.form-group { margin-bottom: 0.4rem; }
.form-control { font-size: 0.85rem; padding: 0.25rem 0.5rem; }
```

### 4. Textareas Auto-Expandibles

**Implementación:**

- **Textarea de progreso** — comienza en 4 filas (~90px), se auto-expande al escribir contenido
- **Textarea de respuesta 2** — comienza en 2 filas (~44px), se auto-expande al escribir contenido

**JavaScript:**

```javascript
function autoResize(el, minHeight) {
  el.style.height = 'auto';
  el.style.height = Math.max(minHeight, el.scrollHeight) + 'px';
}
```

**Cambios en Widgets de Formulario:**

```python
# support/forms.py - IssueChangeForm e InvoicingIssueChangeForm
"progress": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
"answer_2": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
```

**Beneficios:**

- Los textareas comienzan compactos para mostrar más contenido arriba del pliegue
- Crecen automáticamente para ajustarse al contenido mientras los usuarios escriben
- Se encogen al eliminar contenido
- No se necesita redimensionamiento manual

### 5. Notas Colapsables con Conteo de Líneas Ocultas

**Características:**

- Las notas se colapsan a ~2 líneas por defecto si son más largas
- Muestra "Mostrar más (X líneas ocultas) ▼" cuando están colapsadas
- Clic para expandir/colapsar
- Efecto de degradado cuando están colapsadas para claridad visual

**JavaScript:**

```javascript
var totalLines = Math.round($notesContent.prop('scrollHeight') / lineHeight);
var hiddenLines = Math.max(0, totalLines - 2);
var showMoreText = 'Mostrar más (' + hiddenLines + ' líneas ocultas) ▼';
```

**Justificación:** Las notas pueden ser muy largas; colapsarlas ahorra espacio vertical mientras las mantiene accesibles con un clic.

### 6. Corrección de Alineación Respuesta 1 / Respuesta 2

**Antes:** Ambos campos usaban `col-md-6` (división 50/50), causando espacio en blanco bajo Respuesta 1 (dropdown) cuando Respuesta 2 (textarea) era alta.

**Después:** Respuesta 1 usa `col-md-4`, Respuesta 2 usa `col-md-8` (división 33/67).

**Justificación:** Respuesta 1 es típicamente un dropdown (altura corta), Respuesta 2 es un textarea (más alto). La división 4/8 da a Respuesta 2 más espacio horizontal y elimina el espacio en blanco incómodo.

### 7. Normalización de Alturas de Selects Choices.js

**Problema:** La librería Choices.js (usada para Subcategoría y Asignado a) renderizaba selects más altos que los selects HTML nativos, creando inconsistencia visual.

**Solución:**

```css
.choices .choices__inner {
  min-height: auto;
  padding: 0.25rem 0.5rem;
  font-size: 0.85rem;
}
```

**Resultado:** Los selects de Choices.js ahora coinciden con la altura y padding de elementos `<select>` nativos.

### 8. Texto Blanco en Botones SIP "Llamar"

**Problema:** El filtro SIP genera enlaces `<a class="button btn-primary">`, pero el texto era negro (pobre contraste sobre fondo azul).

**Solución:**

```css
a.btn-primary, .button.btn-primary { color: #fff !important; }
```

**Resultado:** Todos los botones/enlaces primarios ahora tienen texto blanco para contraste apropiado.

### 9. Visualización Compacta de Información de Contacto

**Diseño:** Fila de una línea con nombre de contacto, fecha de inicio, teléfono, creado por, y producto en columnas.

**Fila adicional (si aplica):** Información de dirección y suscripción.

**Estilo:**

```css
.compact-info { font-size: 0.8rem; }
```

**Justificación:** La información de contacto es importante pero secundaria al formulario. Mostrarla compactamente al final la mantiene accesible sin consumir espacio vertical principal.

## Archivos Modificados

- **`support/templates/view_issue.html`** — Reescritura completa del template: eliminada barra lateral, reordenadas secciones, agregado JS de auto-redimensionamiento, notas colapsables, estilo compacto
- **`support/forms.py`** — Agregado `rows=4` a progress, `rows=2` a answer_2 en `IssueChangeForm` e `InvoicingIssueChangeForm`
- **`support/views/all_views.py`** — Eliminados activity_form, activities e invoice_list del contexto

## Decisiones de Diseño

### ¿Por qué eliminar la barra lateral de actividades?

La retroalimentación de usuarios indicó que la funcionalidad de actividades no se estaba usando, y la barra lateral consumía ~33% del espacio horizontal. Eliminarla permite que el formulario use todo el ancho de pantalla, mostrando más contenido y reduciendo el desplazamiento horizontal en pantallas más pequeñas.

### ¿Por qué reordenar secciones (formulario antes que información de contacto)?

Los usuarios querían ver el textarea de progreso y campos del formulario inmediatamente al abrir una incidencia. La información de contacto sigue siendo accesible pero se movió al final ya que cambia con menos frecuencia que los campos del formulario.

### ¿Por qué textareas auto-expandibles en lugar de alturas fijas?

Los textareas auto-expandibles proporcionan lo mejor de ambos mundos: comienzan compactos (mostrando más contenido arriba del pliegue) pero crecen automáticamente para ajustarse al contenido mientras los usuarios escriben. Esto elimina la necesidad de barras de desplazamiento dentro de textareas y reduce el redimensionamiento manual.

### ¿Por qué colapsar notas por defecto?

Las notas pueden ser muy largas (múltiples párrafos), y típicamente se leen una vez cuando se crea la incidencia pero no se editan frecuentemente. Colapsarlas a 2 líneas ahorra espacio vertical significativo mientras las mantiene a un clic de distancia.

### ¿Por qué la división 4/8 para Respuesta 1/Respuesta 2?

Respuesta 1 es típicamente un dropdown (altura corta), mientras que Respuesta 2 es un textarea (más alto). Una división 50/50 creaba espacio en blanco incómodo bajo Respuesta 1. La división 4/8 da a Respuesta 2 más espacio horizontal (útil para texto más largo) y elimina el desequilibrio visual.

## Compatibilidad con Ladiaria

El bloque `{% block issue_additional_actions %}` permanece en la misma posición (junto al botón Actualizar), por lo que el template de extensión de ladiaria que agrega los botones "Ofrecer Retención" y "Procesar Baja" continúa funcionando sin modificación.

## Notas de Despliegue

- No se requieren migraciones
- No hay nuevas dependencias
- Los cambios de template y formulario son visibles inmediatamente después del despliegue
- Toda la funcionalidad existente preservada (breadcrumbs, validación de formulario, filtrado de subcategorías, etc.)
- Mejora de rendimiento al eliminar consultas de contexto innecesarias
