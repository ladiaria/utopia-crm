# Edición de Estado de Campaña para Managers y Admins

- **Fecha:** 2026-04-06
- **Autor:** Tanya Tree + Claude Sonnet 4.6
- **Ticket:** t1091
- **Tipo:** Funcionalidad
- **Componente:** Support, Gestión de Campañas, Detalle de Contacto
- **Impacto:** Experiencia de Usuario, Control de Acceso

## 🎯 Resumen

Managers, Admins y superusuarios pueden ahora editar el registro `ContactCampaignStatus` (CCS) de un contacto directamente desde la página de detalle del contacto, sin necesidad de acceder al admin de Django. Una vista dedicada expone únicamente los tres campos editables — estado, resolución de campaña y motivo de resolución — mientras muestra el resto de la información de campaña en modo solo lectura. El personal regular (vendedores, soporte) no percibe ningún cambio. El acceso se controla tanto en la vista (redireccionando a usuarios no autorizados) como en el template (el botón no se renderiza para usuarios sin permiso).

## ✨ Cambios

### 1. Helper de permisos y vista de edición

**Archivo:** `support/views/contacts.py`

Una función auxiliar independiente `user_can_edit_campaign_status()` centraliza la verificación de permisos:

```python
def user_can_edit_campaign_status(user):
    return user.is_active and (
        user.is_superuser or user.groups.filter(name__in=["Managers", "Admin"]).exists()
    )
```

`ContactCampaignStatusEditView` es un `UpdateView` que:

- Llama al helper en `dispatch()` y redirige a usuarios no autorizados de vuelta a la página de detalle del contacto con un mensaje de error.
- Muestra información de campaña (nombre del contacto, vendedor, fechas) en modo solo lectura en el encabezado del template.
- Guarda únicamente los campos `status`, `campaign_resolution` y `resolution_reason`.
- Redirige a la página de detalle del contacto al guardar con un mensaje de confirmación.

`ContactDetailView.get_context_data()` ahora también incluye `can_edit_campaign_status` en el contexto para que el template pueda mostrar u ocultar el botón sin consultas adicionales por cada tarjeta de campaña:

```python
context["can_edit_campaign_status"] = user.is_superuser or user.groups.filter(
    name__in=["Managers", "Admin"]
).exists()
```

### 2. Formulario de edición

**Archivo:** `support/forms.py`

`ContactCampaignStatusEditForm` es un `ModelForm` restringido a los tres campos editables, cada uno renderizado con el widget Bootstrap `form-control`:

```python
class ContactCampaignStatusEditForm(forms.ModelForm):
    class Meta:
        model = ContactCampaignStatus
        fields = ("status", "campaign_resolution", "resolution_reason")
```

### 3. Registro de URL

**Archivo:** `support/urls.py`

Se agrega la URL nombrada `edit_campaign_status` que mapea `campaign_status/<int:pk>/edit/` a la nueva vista.

### 4. Template de edición de estado de campaña

**Archivo:** `support/templates/contact_detail/edit_campaign_status.html`

Página de dos paneles siguiendo las convenciones de AdminLTE:

- Tarjeta superior: resumen de solo lectura del registro CCS (nombre de campaña, contacto, vendedor, fechas).
- Tarjeta inferior: el formulario de edición con botones Guardar y Cancelar. Cancelar vuelve a la página de detalle del contacto.

### 5. Botón "Editar estado" en la pestaña de campañas

**Archivo:** `support/templates/contact_detail/tabs/_campaigns.html`

El encabezado de cada tarjeta de campaña ahora incluye un botón "Editar estado" que enlaza a `edit_campaign_status` con el `pk` del CCS. El botón está envuelto en `{% if can_edit_campaign_status %}` para que solo se renderice para usuarios autorizados.

## 📁 Archivos Modificados

- **`support/forms.py`** — Se agregó `ContactCampaignStatusEditForm`; se agregó `ContactCampaignStatus` a los imports del modelo
- **`support/views/contacts.py`** — Se agregó el helper `user_can_edit_campaign_status()`, `ContactCampaignStatusEditView`, el contexto `can_edit_campaign_status` en `ContactDetailView`, y se actualizaron los imports (`Group`, `ContactCampaignStatusEditForm`)
- **`support/urls.py`** — Se agregó la URL `campaign_status/<int:pk>/edit/` y el import de `ContactCampaignStatusEditView`
- **`support/templates/contact_detail/tabs/_campaigns.html`** — Se agregó el botón "Editar estado" controlado por la variable de contexto `can_edit_campaign_status`

## 📁 Archivos Creados

- **`support/templates/contact_detail/edit_campaign_status.html`** — Página de edición del estado de campaña, mostrando información de solo lectura del CCS junto al formulario de edición

## 🧪 Pruebas Manuales

1. **Caso exitoso — un manager edita el estado de campaña:**
   - Iniciar sesión como usuario del grupo "Managers".
   - Abrir el detalle de cualquier contacto que tenga al menos una entrada de campaña en la pestaña Campañas.
   - Hacer clic en el botón "Editar estado" en una tarjeta de campaña.
   - **Verificar:** La página de edición carga mostrando el nombre de campaña, contacto, vendedor y fechas en modo solo lectura. Los campos de estado, resolución y motivo son editables.
   - Cambiar el estado y hacer clic en Guardar.
   - **Verificar:** Se redirige a la página de detalle del contacto y se muestra un mensaje de éxito. La tarjeta de campaña refleja el nuevo badge de estado.

2. **Control de acceso — un vendedor no puede acceder a la vista de edición:**
   - Iniciar sesión como usuario del grupo "Sellers" (sin pertenencia a Managers ni Admin, sin ser superusuario).
   - Abrir el detalle de cualquier contacto con una entrada de campaña.
   - **Verificar:** No hay botón "Editar estado" visible en las tarjetas de campaña.
   - Intentar acceder a la URL de edición directamente (`/campaign_status/<pk>/edit/`).
   - **Verificar:** Se redirige a la página de detalle del contacto con un mensaje de error y no se guarda ningún cambio.

3. **Caso borde — acceso de superusuario:**
   - Iniciar sesión como superusuario.
   - **Verificar:** El botón "Editar estado" es visible en todas las tarjetas de campaña y la vista de edición funciona igual que en el caso exitoso.

4. **Caso borde — solo tres campos son editables:**
   - Abrir la vista de edición como manager.
   - **Verificar:** Solo aparecen los campos `status`, `campaign_resolution` y `resolution_reason` en el formulario. Vendedor, fechas y contacto se muestran en modo solo lectura en la tarjeta de información, no como inputs del formulario.

## 📝 Notas de Despliegue

- No se requieren migraciones de base de datos.
- No se requieren cambios de configuración.
- La verificación de permisos usa los nombres de grupo `"Managers"` y `"Admin"` — asegurarse de que estos grupos existan en el entorno destino.

## 🎓 Decisiones de Diseño

Se eligió una vista dedicada en lugar de enlazar directamente al admin de Django por dos razones: se integra con la UI existente del CRM (tarjetas AdminLTE, breadcrumbs, mensajes), y permite restringir los campos editables únicamente a los que tiene sentido modificar manualmente (`status`, `campaign_resolution`, `resolution_reason`). El admin expone todos los campos, incluyendo `seller`, `date_assigned`, `times_contacted` y `last_console_action`, que no deberían editarse manualmente.

La verificación de permisos se duplica intencionalmente entre `ContactDetailView` (para el botón del template) y `ContactCampaignStatusEditView.dispatch()` (como guarda de la URL). La verificación en el template evita renderizar el botón para usuarios no autorizados; la verificación en la vista asegura que la URL no pueda accederse directamente. Ambas usan el mismo helper `user_can_edit_campaign_status()` para mantenerse sincronizadas.

## 🚀 Mejoras Futuras

- Agregar una traza de auditoría (entrada en el log de actividades) cuando un manager sobreescribe manualmente un estado de campaña.
- Considerar edición inline con HTMX directamente en la tarjeta de campaña para evitar una navegación de página completa.

---

- **Fecha:** 2026-04-06
- **Autor:** Tanya Tree + Claude Sonnet 4.6
- **Branch:** t1091
- **Tipo de cambio:** Funcionalidad
- **Módulos afectados:** Support, Gestión de Campañas, Detalle de Contacto
