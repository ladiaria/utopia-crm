# t1026: Modernización de la Vista de Filtro de Facturas

**Fecha:** 2026-02-06
**Tipo:** Refactorización, Optimización de Rendimiento y Mejora de UI
**Componente:** Filtro de facturas (`invoicing`)
**Impacto:** Rendimiento, Experiencia de Usuario, Mantenibilidad

## Resumen

Modernización integral de la página de filtro de facturas: conversión de la vista basada en función a una `FilterView` basada en clase, optimización de consultas a la base de datos, implementación de exportación CSV con streaming, mejora del CSV con campos adicionales del contacto, nuevas opciones de filtro y mejoras significativas en la interfaz de usuario.

## Cambios

### 1. Conversión de Vista: FBV → CBV

**Archivo:** `invoicing/views.py`

Se convirtió la vista `invoice_filter` (basada en función) a `InvoiceFilterView`, una vista basada en clase que hereda de `FilterView` y `BreadcrumbsMixin`.

- `filterset_class = InvoiceFilter`
- `paginate_by = 200`, `page_kwarg = 'p'`
- `context_object_name = 'invoices'`
- Breadcrumbs: Inicio → Filtro de facturas
- Alias de compatibilidad: `invoice_filter = InvoiceFilterView.as_view()`

### 2. Optimización del Queryset

**Archivo:** `invoicing/views.py`

- Se agregó `select_related('contact', 'subscription')` — elimina consultas N+1 para acceso a contacto y suscripción (la suscripción no estaba incluida anteriormente)
- Se agregó `prefetch_related('invoiceitem_set')` — precarga los ítems de factura para la columna de descripción

### 3. Exportación CSV con Streaming

**Archivo:** `invoicing/views.py`

Se reemplazó `HttpResponse` por `StreamingHttpResponse` usando un patrón generador con buffer `io.StringIO`. Utiliza `iterator(chunk_size=1000)` para procesamiento eficiente en memoria de grandes conjuntos de datos.

- Inicia la descarga inmediatamente en lugar de construir toda la respuesta en memoria
- Previene timeouts en exportaciones grandes

### 4. Campos Adicionales en Exportación CSV

**Archivo:** `invoicing/views.py`

Se agregaron 4 campos nuevos del contacto al CSV (después del ID de contacto):

- **Documento de identidad** (`contact.id_document`)
- **Email** (`contact.email`)
- **Teléfono** (`contact.phone`)
- **Celular** (`contact.mobile`)

### 5. Nuevos Campos de Filtro

**Archivo:** `invoicing/filters.py`

Se agregaron 3 filtros nuevos para buscar facturas por información del contacto:

- **`contact_email`** — filtra por `contact__email__icontains`
- **`contact_id_document`** — filtra por `contact__id_document__icontains`
- **`contact_phone`** — busca tanto en `contact__phone` como en `contact__mobile` usando objetos `Q`

Todos los filtros incluyen texto placeholder y `autocomplete="off"` en los atributos del widget.

### 6. Selectores de Fecha HTML5 Nativos

**Archivos:** `invoicing/filters.py`, `invoicing/templates/invoice_filter.html`

Se reemplazaron los datepickers de jQuery UI por `<input type="date">` nativos de HTML5:

- Se cambiaron todos los widgets de filtros de fecha de `forms.TextInput` a `forms.DateInput(attrs={'type': 'date', 'autocomplete': 'off'})`
- Se eliminó la inicialización de jQuery `.datepicker()` del template
- Se suprimen las sugerencias de autocompletado del navegador

### 7. Filtro "Hoy" por Defecto al Cargar

**Archivo:** `invoicing/views.py`

Cuando la página se carga sin parámetros GET, ahora redirige a `?creation_date=today` para que la opción "Hoy" esté visiblemente seleccionada en el dropdown, coincidiendo con los datos mostrados. Anteriormente, el queryset se filtraba silenciosamente por hoy pero el dropdown aparecía vacío, confundiendo a los usuarios.

### 8. Rediseño de la Tarjeta de Estadísticas

**Archivos:** `invoicing/views.py`, `invoicing/templates/invoice_filter.html`

- Se reemplazó el bloque `callout` por una **tarjeta colapsable** de AdminLTE (`card-outline card-info`)
- Inicia **expandida** por defecto, colapsable mediante botón `+`/`−`
- Badges de estado con colores: Pagadas (verde), Pendientes (amarillo), Vencidas (rojo), Canceladas (gris), Incobrables (oscuro)
- Cada badge muestra cantidad + monto en dólares
- **Rango de fechas**: muestra la fecha de factura más antigua → más reciente usando agregación `Min`/`Max` sobre `creation_date`
- Botón de reset estilizado como outline-danger con ícono de deshacer
- Los montos usan `floatformat:"-2"` para eliminar decimales `.00` innecesarios

### 9. Tarjeta de Filtros Colapsable

**Archivo:** `invoicing/templates/invoice_filter.html`

Se envolvió el formulario de filtros en una tarjeta colapsable de AdminLTE (`card-outline card-primary`) con encabezado "Filtros" y botón de colapso `−`.

### 10. Mejoras en la Tabla y Template

**Archivo:** `invoicing/templates/invoice_filter.html`

- **Scroll horizontal**: Tabla envuelta en `.table-responsive-custom` con `overflow-x: auto` e indicador visual de scroll
- **Columna de ítems compacta**: CSS elimina viñetas del `<ul>`, agrega líneas separadoras sutiles entre ítems, cada ítem es `nowrap`
- **`nowrap` en columnas clave**: Estado, S/N, Tipo de pago, fechas, Importe, Nombre de contacto, ID — previene saltos de línea incómodos
- **Link en el ID de factura**: El ID de factura ahora es un enlace clickeable a la página de detalle
- **Montos limpios**: `floatformat:"-2"` muestra `245` en lugar de `245.00`, mantiene `1251.50` cuando hay decimales significativos
- **Campo Número**: `autocomplete="off"` previene que el navegador lo trate como número de tarjeta de crédito
- **Estilos de tabla**: Se agregaron clases `table-striped table-bordered`

### 11. Reorganización del Layout de Filtros

**Archivo:** `invoicing/templates/invoice_filter.html`

Se reorganizó en 3 filas lógicas:

- **Fila 1 (Info del contacto)**: Nombre, Email, Documento de identidad, Teléfono (con texto de ayuda "Busca tanto en teléfono como en celular")
- **Fila 2 (Fechas de factura)**: Fecha de emisión + rango Desde/Hasta inline + Estado + Tipo de pago — todos `col` flex para que la fila se llene naturalmente ya sea que el rango personalizado esté visible o no
- **Fila 3 (Pago y serie)**: Pago desde, Pago hasta, Serie, Número, Sin número de serie

### 12. Configuración de URL

**Archivo:** `invoicing/urls.py`

Se actualizó para usar `InvoiceFilterView.as_view()` directamente.

## Archivos Modificados

- `invoicing/views.py` — Nueva CBV `InvoiceFilterView`, CSV con streaming, contexto con rango de fechas
- `invoicing/filters.py` — Nuevos filtros de contacto, widgets de fecha HTML5, placeholders
- `invoicing/templates/invoice_filter.html` — Rediseño completo de la interfaz
- `invoicing/urls.py` — Actualizado a CBV

## Notas de Migración

- No se requieren migraciones de base de datos
- Todos los cambios son a nivel de vista, filtro, template y URL
- Compatible hacia atrás: el alias `invoice_filter` sigue disponible

---

**Fecha:** 2026-02-06
**Issue:** t1026
**Tipo:** Refactorización + Mejora de UI + Rendimiento
**Prioridad:** Media
