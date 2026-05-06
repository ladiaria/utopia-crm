# Panel de Issues Abiertos en la Consola del Vendedor y Renderizado Seguro de Mensajes

- **Fecha:** 2026-03-25
- **Autor:** Tanya Tree + Claude Sonnet 4.6
- **Ticket:** t1069
- **Tipo:** Mejora de UX
- **Componente:** Support, Consola del Vendedor, Gestión de Issues
- **Impacto:** Experiencia de Usuario, Flujo de Trabajo del Vendedor

## 🎯 Resumen

Los vendedores que trabajan en la consola no tenían visibilidad sobre si el contacto al que estaban llamando tenía issues abiertos registrados en el sistema. Este cambio agrega dos indicadores complementarios: un badge rojo junto al nombre del contacto en el encabezado de la consola advierte de un vistazo cuando existen issues abiertos e instruye al vendedor a revisar el panel derecho, y una nueva tarjeta "Issues abiertos del contacto" aparece en la barra lateral derecha listando cada issue no terminal con su categoría, subcategoría, estado, fecha y notas. Como corrección independiente en la misma rama, se actualizó la plantilla base de mensajes para respetar el tag `safe` ya utilizado por el mensaje de confirmación de creación de issues — anteriormente, el enlace HTML de ese mensaje se mostraba como texto plano en lugar de un hipervínculo renderizado.

## ✨ Cambios

### 1. Badge de Issues Abiertos en el Encabezado de la Consola

**Archivo:** `support/templates/seller_console.html`

Un badge `badge-danger` rojo se renderiza condicionalmente junto al nombre del contacto cuando `open_issues_count > 0`. El badge incluye un conteo y una indicación para revisar el panel derecho:

```html
{% if open_issues_count > 0 %}
  <span class="badge badge-danger ml-2"
        title="{% trans "This contact has open issues — check the right panel" %}">
    <i class="fas fa-exclamation-circle"></i>
    {% blocktrans with count=open_issues_count %}{{ count }} open issue(s) — check right panel{% endblocktrans %}
  </span>
{% endif %}
```

El badge se ubica junto a los badges de estado existentes "No encontrado" y "Llamar más tarde", manteniendo la consistencia visual del encabezado.

### 2. Panel de Issues Abiertos en la Barra Lateral Derecha

**Archivo:** `support/templates/seller_console.html`

Una nueva tarjeta `card card-danger card-outline` se agrega al final de la columna derecha, debajo del partial HTMX `last_read_articles`. Solo se renderiza cuando `open_issues` no está vacío. Cada issue muestra su categoría y subcategoría, badge de estado, fecha de creación, un enlace a la vista de detalle del issue (se abre en una nueva pestaña), y las notas completas sin truncar:

```html
{% if open_issues %}
  <div class="card card-danger card-outline mt-2">
    ...
    {% for issue in open_issues %}
      <div class="list-group-item py-2 px-3">
        <span class="font-weight-bold">{{ issue.get_category }}{% if issue.get_subcategory %} – {{ issue.get_subcategory }}{% endif %}</span>
        <span class="badge badge-secondary">{{ issue.get_status|default_if_none:"" }}</span>
        <span class="text-muted">{{ issue.date_created|date:"d/m/Y" }}</span>
        <a href="{% url "view_issue" issue.id %}" target="_blank">...</a>
        {% if issue.notes %}
          <div class="text-muted mt-1"><small>{{ issue.notes }}</small></div>
        {% endif %}
      </div>
    {% endfor %}
  </div>
{% endif %}
```

Las notas se muestran completas — sin truncar — porque se espera que los vendedores las lean en su totalidad y es poco probable que un contacto tenga muchos issues abiertos al mismo tiempo.

### 3. Contexto de Issues Abiertos en la Vista de la Consola del Vendedor

**Archivo:** `support/views/seller_console.py`

Dentro de `SellerConsoleView.get_context_data()`, el queryset de issues abiertos se construye filtrando todos los registros `Issue` del contacto actual y excluyendo aquellos cuyo slug de estado esté listado en `settings.ISSUE_STATUS_FINISHED_LIST`. Esto replica el mismo patrón utilizado en `all_views.py` para la consola comunitaria y los dashboards de issues:

```python
terminal_statuses = getattr(settings, 'ISSUE_STATUS_FINISHED_LIST', [])
open_issues = Issue.objects.filter(contact=contact).exclude(
    status__slug__in=terminal_statuses
).order_by("-date_created")

context.update({
    ...
    'open_issues': open_issues,
    'open_issues_count': open_issues.count(),
})
```

Se pasan tanto `open_issues` (para el panel) como `open_issues_count` (para el badge) para que la plantilla pueda renderizar cada uno de forma independiente sin re-evaluar el queryset.

### 4. Renderizado Seguro de HTML en los Mensajes de Django

**Archivo:** `templates/adminlte/lib/_messages.html`

El partial compartido de mensajes renderizaba previamente todos los mensajes con el auto-escape de Django (`{{ message }}`), lo que causaba que el enlace HTML del mensaje de confirmación de creación de issues se mostrara como texto plano. La corrección verifica si `'safe'` está presente en `message.tags` y aplica el filtro `|safe` solo en ese caso:

```html
{% if 'safe' in message.tags %}{{ message|safe }}{% else %}{{ message }}{% endif %}
```

Este cambio se aplica a las tres variantes de alerta (success, danger, info), por lo que cualquier mensaje futuro que requiera renderizado HTML puede usar `extra_tags='safe'` y se mostrará correctamente.

## 📁 Archivos Modificados

- **`support/views/seller_console.py`** — Agregados el queryset `open_issues` y `open_issues_count` en `SellerConsoleView.get_context_data()`
- **`support/templates/seller_console.html`** — Agregados el badge de issues abiertos en el encabezado y el panel de issues abiertos en la barra lateral derecha
- **`templates/adminlte/lib/_messages.html`** — Agregada verificación del tag `safe` para que los mensajes enviados con `extra_tags='safe'` se rendericen como HTML

## 📚 Detalles Técnicos

- Los estados terminales están definidos por el setting `ISSUE_STATUS_FINISHED_LIST` (una lista de slugs de estado). Si el setting no está configurado, se usa una lista vacía y todos los issues se muestran como abiertos. Esto es consistente con el funcionamiento de todas las demás consultas de issues abiertos en el código base.
- Se pasan tanto `open_issues` como `open_issues_count` a la plantilla. Llamar a `.count()` en el queryset ejecuta una consulta SQL `COUNT` en lugar de traer todas las filas, lo que es eficiente para la verificación del badge. El queryset completo se evalúa solo cuando la plantilla itera sobre él en el panel.
- El filtro `|safe` se aplica únicamente cuando el tag `'safe'` es establecido explícitamente por la vista. Los mensajes sin ese tag continúan siendo auto-escapados, preservando la protección contra XSS para todos los demás mensajes.

## 🧪 Pruebas Manuales

1. **Caso exitoso — contacto con issues abiertos:**
   - Abrir la consola del vendedor para una campaña y navegar a un contacto que tenga al menos un issue que no esté en estado terminal.
   - **Verificar:** Aparece un badge rojo junto al nombre del contacto mostrando el conteo y "check right panel". La barra lateral derecha muestra la tarjeta "Issues abiertos del contacto" con la categoría, estado, fecha de creación, enlace de vista y notas completas del issue.

2. **Caso exitoso — contacto sin issues abiertos:**
   - Navegar a un contacto que no tenga issues, o cuyos issues estén todos en estados terminales.
   - **Verificar:** No aparece ningún badge junto al nombre del contacto. No aparece ninguna tarjeta de issues abiertos en la barra lateral derecha.

3. **Caso exitoso — el mensaje de creación de issue se renderiza como enlace:**
   - Desde la página de detalle de un contacto, crear un nuevo issue mediante el formulario Nueva Issue.
   - **Verificar:** Tras el envío del formulario, el mensaje de éxito en la parte superior de la página de detalle del contacto muestra "Issue #X created for contact Nombre" donde `#X` es un enlace clicable que abre la vista de detalle del issue.

4. **Caso borde — contacto con mezcla de issues abiertos y terminales:**
   - Configurar un contacto con un issue abierto (estado no terminal) y un issue resuelto (estado terminal).
   - **Verificar:** El badge muestra "1 open issue(s)" y solo el issue abierto aparece en el panel derecho. El issue resuelto no se muestra.

5. **Caso borde — issue sin notas:**
   - Navegar a un contacto cuyo issue abierto tenga el campo de notas vacío.
   - **Verificar:** El issue aparece en el panel con categoría, estado y fecha, pero no se renderiza ningún bloque de notas.

## 📝 Notas de Despliegue

- No se requieren migraciones de base de datos.
- No se necesitan cambios de configuración, siempre que `ISSUE_STATUS_FINISHED_LIST` ya esté configurado. Si no está definido, todos los issues del contacto serán tratados como abiertos.
- Ejecutar `python manage.py compilemessages` después del despliegue si las nuevas cadenas traducibles (`open issue(s) — check right panel`, `Contact's open issues`, etc.) han sido traducidas en el archivo `.po`.

## 🚀 Mejoras Futuras

- Agregar un botón de acceso directo "Crear issue" en el panel de issues abiertos para registrar issues rápidamente desde dentro de la consola del vendedor
- Considerar mostrar un indicador de conteo en los botones de la lista de contactos de la tarjeta "Contactos" colapsada cuando un contacto tiene issues abiertos

---

- **Fecha:** 2026-03-25
- **Autor:** Tanya Tree + Claude Sonnet 4.6
- **Branch:** t1069
- **Tipo de cambio:** Mejora de UX
- **Módulos afectados:** Support, Consola del Vendedor, Gestión de Issues
