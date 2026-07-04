# Advertencias de Rebote de Email en Campos de Correo

**Fecha:** 2026-03-24
**Autor:** Tanya Tree + programador AI en par
**Ticket:** t1065
**Tipo:** Mejora de UX
**Componente:** Support, Modelos Core
**Impacto:** Experiencia de Usuario, Integridad de Datos

## 🎯 Resumen

El personal no tenía ninguna indicación visual de que la dirección de email de un contacto estuviera registrada en el modelo `EmailBounceActionLog`. La dirección aparecía normalmente en todas las vistas de detalle del contacto y en los formularios de suscripción y consola de ventas, sin ninguna señal de que los mensajes enviados a esa dirección hayan rebotado. Este cambio agrega advertencias visibles en toda la interfaz: en las pestañas de resumen e información del detalle del contacto, la dirección de email se muestra en rojo con un ícono ✕ y el tipo de acción de rebote mostrado en línea; en los formularios de edición (datos del contacto y nueva suscripción) y en la consola de ventas, la etiqueta del campo de email o la fila de la tabla se vuelve roja con la misma información. La implementación sigue el mismo patrón introducido para los números de teléfono en la lista "No Llamar" en el ticket t1063.

## ✨ Cambios

### 1. Nuevo Método `get_email_bounce_action()` en Contact

**Archivo:** `core/models.py`

Se agrega un nuevo método en `Contact` que recupera la entrada más reciente de `EmailBounceActionLog` para la dirección de email del contacto (ordenada por `-created`), devolviendo `None` si el email está vacío o no existe ninguna entrada:

```python
def get_email_bounce_action(self):
    if not self.email:
        return None
    return EmailBounceActionLog.objects.filter(email=self.email).order_by("-created").first()
```

El método devuelve la instancia completa del modelo para que los templates puedan llamar a `get_action_display` y obtener el nombre legible de la acción (por ejemplo, "invalid email" o "max bounce reached"). En cada template se utiliza un bloque `{% with %}` para evitar llamar al método —y golpear la base de datos— más de una vez por renderizado.

### 2. Advertencias de Rebote en las Vistas de Detalle del Contacto

**Archivos:** `support/templates/contact_detail/tabs/_overview.html`, `support/templates/contact_detail/tabs/_information.html`

En ambas pestañas, el bloque de visualización del email ahora llama a `contact.get_email_bounce_action` y renderiza condicionalmente una advertencia. Cuando existe una entrada en el log de rebotes, el enlace `mailto:` y el texto circundante se envuelven en `text-danger`, se agrega un ícono `fa-times-circle` y el nombre de la acción se muestra como elemento `<small>`:

```html
{% with email_bounce=contact.get_email_bounce_action %}
  {% if contact.email %}
    {% if email_bounce %}
      <span class="text-danger">
        <a href="mailto:{{ contact.email }}" class="text-danger">{{ contact.email }}</a>
        <i class="fas fa-times-circle ml-1" title="{{ email_bounce.get_action_display }}"></i>
        <small>{{ email_bounce.get_action_display }}</small>
      </span>
    {% else %}
      <a href="mailto:{{ contact.email }}">{{ contact.email }}</a>
    {% endif %}
  {% else %}
    -
  {% endif %}
{% endwith %}
```

### 3. Advertencia de Rebote en el Formulario de Edición del Contacto

**Archivo:** `support/templates/create_contact/tabs/_data.html`

La etiqueta del campo Email ahora verifica `contact.get_email_bounce_action`. Cuando está marcado, la etiqueta se renderiza en rojo con un ícono ✕ y el nombre de la acción. La guardia `{% if contact %}` exterior asegura que la verificación se omita de forma segura en el formulario de creación de nuevo contacto, donde aún no existe un objeto contacto:

```html
<label for="">
  {% if contact %}
    {% with email_bounce=contact.get_email_bounce_action %}
      {% if email_bounce %}
        <span class="text-danger">
          <i class="fas fa-times-circle"></i> {% trans "Email" %} — {{ email_bounce.get_action_display }}
        </span>
      {% else %}
        {% trans "Email" %}
      {% endif %}
    {% endwith %}
  {% else %}
    {% trans "Email" %}
  {% endif %}
</label>
```

### 4. Advertencia de Rebote en el Formulario de Nueva Suscripción

**Archivo:** `support/templates/new_subscription.html`

La etiqueta del campo Email usa `contact.get_email_bounce_action` directamente (el objeto `contact` siempre está presente en esta vista). Cuando existe una entrada en el log de rebotes, la etiqueta se renderiza en rojo con ícono y nombre de acción, siguiendo el mismo patrón de etiqueta DNC ya utilizado para el teléfono en el mismo template:

```html
<label for="id_email">
  {% with email_bounce=contact.get_email_bounce_action %}
    {% if email_bounce %}
      <span class="text-danger">
        <i class="fas fa-times-circle"></i> {{ form.email.label }} — {{ email_bounce.get_action_display }}
      </span>
    {% else %}
      {{ form.email.label }}
    {% endif %}
  {% endwith %}
</label>
```

### 5. Advertencia de Rebote en la Consola de Ventas

**Archivo:** `support/templates/seller_console.html`

La fila de la tabla de email ahora verifica `contact.get_email_bounce_action`. Cuando está marcado, la fila recibe `class="table-danger"` (igual al estilo usado para las filas de teléfono DNC en el mismo template) y el nombre de la acción se antepone a la dirección de email como etiqueta prefija:

```html
{% with email_bounce=contact.get_email_bounce_action %}
  <tr {% if email_bounce %}class="table-danger"{% endif %}>
    <td><i class="fas fa-at"></i> {% trans "Email" %}:</td>
    <td>
      {% if email_bounce %}<span>{{ email_bounce.get_action_display }}:</span> {% endif %}
      {{ contact.email }}
    </td>
  </tr>
{% endwith %}
```

## 📁 Archivos Modificados

- **`core/models.py`** — Se agrega el método `Contact.get_email_bounce_action()`
- **`support/templates/contact_detail/tabs/_overview.html`** — Se agrega advertencia de rebote al email en la pestaña de resumen
- **`support/templates/contact_detail/tabs/_information.html`** — Se agrega advertencia de rebote al email en la pestaña de información
- **`support/templates/create_contact/tabs/_data.html`** — Se agrega advertencia de rebote a la etiqueta del campo Email en el formulario de edición del contacto
- **`support/templates/new_subscription.html`** — Se agrega advertencia de rebote a la etiqueta del campo Email en el formulario de nueva suscripción
- **`support/templates/seller_console.html`** — Se agrega advertencia de rebote a la fila de email en la consola de ventas

## 📚 Detalles Técnicos

- `EmailBounceActionLog` tiene dos tipos de acción: `EMAIL_BOUNCE_ACTION_INVALID = 1` ("invalid email") y `EMAIL_BOUNCE_ACTION_MAXREACH = 2` ("max bounce reached"), definidos en `core/choices.py`.
- El método estático existente `EmailBounceActionLog.email_is_bouncer()` solo verifica entradas de tipo `EMAIL_BOUNCE_ACTION_MAXREACH` en los últimos 90 días. El nuevo método `get_email_bounce_action()` devuelve intencionalmente la entrada más reciente de **cualquier** tipo de acción sin importar la antigüedad — la presencia de cualquier entrada en el log se considera razón suficiente para mostrar una advertencia.
- No se requirieron cambios en las vistas: `contact` está disponible en todos los templates afectados, y `{% with %}` almacena en caché la única consulta a la base de datos por renderizado sin necesidad de agregar variables de contexto adicionales.
- El método devuelve la instancia completa de `EmailBounceActionLog` en lugar de un booleano, para que los templates puedan llamar a `get_action_display` y mostrar qué tipo de rebote fue registrado.

## 🧪 Pruebas Manuales

1. **Caso exitoso — email con rebote mostrado en rojo en la pestaña de resumen:**
   - Crear una entrada de `EmailBounceActionLog` para el email de un contacto desde el admin de Django (elegir cualquier tipo de acción).
   - Abrir la página de detalle de ese contacto y navegar a la pestaña Resumen.
   - **Verificar:** La dirección de email aparece en rojo con un ícono ✕ y el nombre de la acción (ej. "max bounce reached") mostrado en línea.

2. **Caso exitoso — advertencia mostrada en la pestaña de información:**
   - Con el mismo contacto del escenario 1, navegar a la pestaña Información.
   - **Verificar:** Mismo email en rojo con ícono y nombre de acción.

3. **Caso exitoso — advertencia mostrada en el formulario de edición del contacto:**
   - Abrir el formulario de edición del mismo contacto.
   - **Verificar:** La etiqueta del campo Email se renderiza en rojo con el ícono ✕ y el nombre de la acción al inicio.

4. **Caso exitoso — advertencia mostrada en el formulario de nueva suscripción:**
   - Navegar a la página de Nueva Suscripción para el mismo contacto.
   - **Verificar:** La etiqueta Email muestra la advertencia de rebote en rojo.

5. **Caso exitoso — advertencia mostrada en la consola de ventas:**
   - Abrir la consola de ventas para una campaña que incluya al mismo contacto.
   - **Verificar:** La fila del email está resaltada en rojo (`table-danger`) y el nombre de la acción aparece como prefijo antes de la dirección de email.

6. **Caso borde — contacto sin dirección de email:**
   - Abrir un contacto que no tenga email configurado.
   - Navegar a las páginas de Resumen, Información, Edición y Nueva Suscripción.
   - **Verificar:** No aparece ninguna advertencia; no se producen errores; el campo de email renderiza su estado normal "-" o vacío.

7. **Caso borde — contacto con email pero sin entradas en el log de rebotes:**
   - Abrir un contacto cuyo email no tenga registros en `EmailBounceActionLog`.
   - **Verificar:** La dirección de email se renderiza normalmente (enlace `mailto:` en negro, etiqueta sin advertencia), sin ícono ni texto de advertencia.

8. **Caso borde — formulario de creación de nuevo contacto:**
   - Navegar al formulario de Nuevo Contacto (sin objeto contacto existente).
   - **Verificar:** La etiqueta Email se renderiza como texto plano "Email"; no se intenta verificar rebotes; no se producen errores.

## 📝 Notas de Despliegue

- No se requieren migraciones de base de datos.
- No se requieren cambios de configuración.
- No se requiere ejecutar comandos de administración.

## 🚀 Mejoras Futuras

- Considerar mostrar la fecha del rebote junto al tipo de acción para mayor contexto a simple vista
- Agregar un tooltip o detalle expandible que muestre el historial completo de rebotes para el email de un contacto

---

**Fecha:** 2026-03-24
**Autor:** Tanya Tree + programador AI en par
**Branch:** t1065
**Tipo de cambio:** Mejora de UX
**Módulos afectados:** Core, Support, Subscriptions
