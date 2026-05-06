# Advertencias de No Llamar en Campos de Teléfono

**Fecha:** 2026-03-23
**Autor:** Tanya Tree + programador AI en par
**Ticket:** t1063
**Tipo:** Mejora de UX, Corrección
**Componente:** Support, Modelos Core
**Impacto:** Experiencia de Usuario, Integridad de Datos

## 🎯 Resumen

El personal no tenía forma de identificar a simple vista si el número de teléfono de un contacto estaba en el registro de No Llamar. El número aparecía normalmente en las vistas de detalle del contacto y en los formularios de suscripción y edición, sin ninguna indicación de que llamarlo podría ser un problema de cumplimiento normativo. Este cambio agrega advertencias visibles en toda la interfaz: en las pestañas de resumen e información del detalle del contacto, el número se muestra en rojo con un ícono ✕ y el mensaje "Number in do not call list"; en los formularios de edición (datos del contacto y nueva suscripción), la etiqueta del campo se torna roja con el mismo ícono y mensaje. Adicionalmente, el método `Contact.do_not_call()` del modelo fue reforzado para manejar casos en los que un atributo de teléfono contiene un string plano en lugar de un objeto `PhoneNumber`, lo que causaba el error `'str' object has no attribute 'national_number'` en ciertos flujos de vista.

## ✨ Cambios

### 1. Advertencias de No Llamar en las Vistas de Detalle del Contacto

**Archivos:** `support/templates/contact_detail/tabs/_overview.html`, `support/templates/contact_detail/tabs/_information.html`

En ambas pestañas, los bloques de visualización de `phone`, `mobile` y `work_phone` ahora llaman a los métodos correspondientes del modelo (`do_not_call_phone`, `do_not_call_mobile`, `do_not_call_work_phone`) y renderizan condicionalmente una advertencia. Cuando el número está marcado, el enlace del teléfono y el texto circundante se envuelven en `text-danger`, el enlace `tel:` también recibe `text-danger`, y a continuación aparece un ícono `fa-times-circle` con un mensaje corto:

```html
{% if contact.do_not_call_phone %}
  <span class="text-danger">
    <a href="tel:{{ contact.phone }}" class="text-danger">{{ contact.phone.as_national }}</a>
    <i class="fas fa-times-circle ml-1" title="{% trans "Number in do not call list" %}"></i>
    <small>{% trans "Number in do not call list" %}</small>
  </span>
{% else %}
  <a href="tel:{{ contact.phone }}">{{ contact.phone.as_national }}</a>
{% endif %}
```

El mismo patrón se aplica a `mobile` y `work_phone` en ambas plantillas.

### 2. Advertencias de No Llamar en el Formulario de Edición de Contacto

**Archivo:** `support/templates/create_contact/tabs/_data.html`

Las etiquetas de los campos Teléfono, Celular y Teléfono institucional verifican `contact.do_not_call_phone`, `contact.do_not_call_mobile` y `contact.do_not_call_work_phone` respectivamente. Cuando está marcado, la etiqueta se renderiza en rojo con el ícono y el mensaje en lugar del texto normal. La verificación usa `{% if contact and contact.do_not_call_phone %}` para que se omita de forma segura en el formulario de creación de contacto, donde todavía no existe un objeto contact:

```html
<label for="">
  {% if contact and contact.do_not_call_phone %}
    <span class="text-danger">
      <i class="fas fa-times-circle"></i> {% trans "Phone" %} — {% trans "Number in do not call list" %}
    </span>
  {% else %}
    {% trans "Phone" %}
  {% endif %}
</label>
```

### 3. Advertencias de No Llamar en el Formulario de Nueva Suscripción

**Archivos:** `support/templates/new_subscription.html`, `support/views/subscriptions.py` (base), `utopia-crm-ladiaria: views/subscriptions.py` (mixin)

Las etiquetas de Teléfono y Celular en `new_subscription.html` usan las variables de contexto booleanas `dnc_phone` y `dnc_mobile` en lugar de llamar al método del modelo directamente. Esto evita un error que ocurría cuando `contact.mobile` había sido mutado a un string plano durante el procesamiento del POST.

`SubscriptionCreateView.get_context_data()` y `SubscriptionUpdateView.get_context_data()` en la aplicación base ahora incluyen estas dos variables llamando a los métodos del modelo sobre el objeto contact limpio. En la extensión de ladiaria, `LadiariaSubscriptionMixin.get_context_data()` recarga el contacto desde la base de datos antes de calcular los flags, asegurando que los valores reflejen los datos de teléfono almacenados independientemente de cualquier mutación en memoria:

```python
# Reload contact from DB to ensure clean phone values for DNC checks
contact = Contact.objects.get(pk=self.contact.pk)
...
"dnc_phone": contact.do_not_call_phone(),
"dnc_mobile": contact.do_not_call_mobile(),
```

### 4. Método `Contact.do_not_call()` Reforzado contra Valores de Teléfono como String

**Archivo:** `core/models.py`

El método `do_not_call()` asumía previamente que `number` era siempre un objeto `PhoneNumber`, llamando a `number.national_number` incondicionalmente. Si `number` contenía un string plano (por ejemplo, un string vacío `""` proveniente de los datos limpiados del formulario que se asignaron de vuelta al contacto en memoria), esto generaba `AttributeError: 'str' object has no attribute 'national_number'`. El método ahora maneja todos los casos de forma defensiva:

```python
def do_not_call(self, phone_att="phone"):
    number = getattr(self, phone_att)
    if phone_att == "work_phone":
        return DoNotCallNumber.objects.filter(number__iexact=number).exists()
    elif not number:
        return False
    elif isinstance(number, str):
        return DoNotCallNumber.objects.filter(number__contains=number).exists()
    elif number.national_number is None:
        return False
    return DoNotCallNumber.objects.filter(number__contains=number.national_number).exists()
```

- Vacío o `None` → retorna `False` sin error
- String plano con valor → consulta por contenido del string (misma estrategia que `work_phone`)
- Objeto `PhoneNumber` → comportamiento original sin cambios

## 📁 Archivos Modificados

- **`core/models.py`** — Método `Contact.do_not_call()` reforzado para manejar valores de teléfono como string o vacíos
- **`support/templates/contact_detail/tabs/_overview.html`** — Advertencias DNC agregadas para phone, mobile y work_phone en la pestaña de resumen
- **`support/templates/contact_detail/tabs/_information.html`** — Advertencias DNC agregadas para phone, mobile y work_phone en la pestaña de información
- **`support/templates/create_contact/tabs/_data.html`** — Advertencias DNC agregadas en las etiquetas de Teléfono, Celular y Teléfono institucional del formulario de edición
- **`support/templates/new_subscription.html`** — Etiquetas de teléfono/celular cambiadas para usar variables booleanas de contexto `dnc_phone`/`dnc_mobile`
- **`support/views/subscriptions.py`** — Variables `dnc_phone` y `dnc_mobile` agregadas al contexto en `SubscriptionCreateView` y `SubscriptionUpdateView`

## 📚 Detalles Técnicos

- La URL `new_subscription` de ladiaria está gestionada por `LadiariaSubscriptionCreateView` / `LadiariaSubscriptionUpdateView` (basadas en clases, en `utopia_crm_ladiaria/views/subscriptions.py`), no por la función `ladiaria_new_subscription` (que ahora solo es accesible vía `new_subscription_old`). Las variables de contexto DNC se inyectan a través de `LadiariaSubscriptionMixin.get_context_data()`.
- La recarga desde la BD en `LadiariaSubscriptionMixin.get_context_data()` es una medida defensiva: en la vista basada en funciones legacy, la vista muta `contact.phone`/`contact.mobile` en memoria mediante `setattr` antes de intentar `contact.save()`. Si ese guardado falla (o el formulario es inválido y llega al render), el objeto contact en memoria puede contener valores de cleaned_data en lugar de los objetos `PhoneNumber` originales, desencadenando el error.
- Los métodos `do_not_call_*` se llaman directamente desde las plantillas solo donde el objeto contact tiene garantía de ser una instancia fresca de la BD (vistas de detalle). En las vistas de formulario donde el contacto puede estar mutado, los booleanos se precalculan en Python y se pasan como contexto.

## 🧪 Pruebas Manuales

1. **Caso exitoso — número DNC mostrado en rojo en la pestaña de resumen:**
   - Agregar un número de teléfono a `DoNotCallNumber` mediante el admin de Django (por ejemplo, un string de número nacional como `099123456`).
   - Abrir un contacto cuyo `phone` o `mobile` coincida con ese número.
   - Navegar a la pestaña de Resumen (Overview).
   - **Verificar:** El número de teléfono coincidente aparece en rojo, con un ícono ✕ y la etiqueta "Number in do not call list". Los números que no coinciden aparecen normalmente.

2. **Caso exitoso — advertencia DNC en el formulario de edición de contacto:**
   - Abrir el formulario de edición del contacto del escenario 1.
   - **Verificar:** La etiqueta Teléfono (o Celular) se renderiza en rojo con el ícono ✕ y el mensaje. Las demás etiquetas no se ven afectadas.

3. **Caso exitoso — advertencia DNC en el formulario de nueva suscripción:**
   - Navegar a la página de Nueva Suscripción para el mismo contacto.
   - **Verificar:** La etiqueta de Teléfono y/o Celular muestra la advertencia DNC en rojo.

4. **Caso borde — contacto sin número de teléfono:**
   - Abrir un contacto que no tenga `phone` ni `mobile` asignados.
   - Navegar a las pestañas de Resumen, Información y Edición.
   - **Verificar:** No aparece ninguna advertencia DNC; no se generan errores.

5. **Caso borde — número de teléfono almacenado como string vacío:**
   - Este es un caso borde interno; verificar que el método do_not_call lo maneje.
   - **Verificar:** No se genera `AttributeError`; el método retorna `False` para strings vacíos.

6. **Caso borde — formulario de creación de contacto (sin objeto contact existente):**
   - Navegar al formulario de creación de Nuevo Contacto.
   - **Verificar:** Las etiquetas de Teléfono, Celular y Teléfono institucional se renderizan normalmente (no se intenta verificar DNC sobre un contacto inexistente).

## 📝 Notas de Despliegue

- No se requieren migraciones de base de datos.
- No se requieren cambios de configuración.
- No hay comandos de gestión para ejecutar.

## 🚀 Mejoras Futuras

- Extender las advertencias DNC a la consola de vendedores / vistas de llamadas de campaña donde los agentes realizan llamadas salientes
- Considerar mostrar una confirmación modal no bloqueante si un usuario intenta hacer clic en un enlace `tel:` de un número marcado como DNC

---

**Fecha:** 2026-03-23
**Autor:** Tanya Tree + programador AI en par
**Branch:** t1063
**Tipo de cambio:** Mejora de UX, Corrección
**Módulos afectados:** Core, Support, Suscripciones
