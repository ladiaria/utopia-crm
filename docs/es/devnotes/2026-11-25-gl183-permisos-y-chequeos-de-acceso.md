# Tres permisos nuevos y chequeos de acceso que no hacían lo que parecía

- **Fecha:** 2026-11-25
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#183, #184
- **Tipo:** Corrección / Funcionalidad
- **Componente:** Modelos de core, Support
- **Impacto:** Permisos, Seguridad

## 🎯 Resumen

Una revisión de todos los chequeos de acceso del CRM encontró botones escondidos a un grupo con la vista abierta,
vistas sin ningún login y un nombre de grupo mal escrito. Este cambio arregla los del base y agrega tres permisos, para
que un paquete de customización le pueda dar a un grupo que no es Admins lo que hoy sólo puede Admins o Managers.

## ✨ Cambios

### 1. Tres permisos nuevos

**Archivos:** `core/models.py`, `core/migrations/0130_permisos_exportar_no_llamar_activar.py`

| Permiso | Modelo | Qué habilita |
|---|---|---|
| `core.can_export_contacts` | `Contact` | Exportar a CSV la lista de contactos |
| `core.can_activate_in_web` | `Subscription` | Lo chequean los paquetes que activan una suscripción en la web a pedido |
| `core.can_upload_do_not_call_numbers` | `DoNotCallNumber` | Subir la lista de no llamar |

Ningún grupo los recibe al migrar. Admins y los superusuarios siguen pasando sin ellos.

### 2. Exportar la lista de contactos

**Archivos:** `support/views/contacts.py`, `support/templates/contact_list.html`

El botón «Exportar a CSV» se mostraba sólo a Managers, pero `ContactListView.get` exportaba para cualquier usuario
staff con `?export=…`. Ahora `user_can_export_contacts(user)` lo chequea en la vista: Managers (por `in_group`, que
deja pasar también a Admins y a superusuarios) o `core.can_export_contacts`. Si no, 403. El botón sigue la misma regla.

### 3. Lista de no llamar

**Archivos:** `support/views/all_views.py`, `templates/components/sidebar_items/_campaign_management.html`,
`support/templates/campaign_management_menu.html`

`upload_do_not_call_numbers` deja pasar a Admins, a superusuarios y a `core.can_upload_do_not_call_numbers`, y lo mismo
su link y su tarjeta. El link y la tarjeta de «Borrado masivo de estados de campaña» ahora se muestran sólo a Admins,
igual que la vista: un Manager los veía y no podía usarlos.

### 4. Vistas que ahora piden staff

**Archivos:** `support/views/contacts.py`, `support/views/all_views.py`

`contact_invoices_htmx` y `contact_activities_htmx` sólo chequeaban el header `HX-Request`, que cualquiera puede
mandar, y `api_new_address` creaba una dirección en cualquier contacto. Las tres tienen ahora `@staff_member_required`,
y `api_new_address` además `@require_POST`: sólo hace algo con un POST, y hoy no la llama ningún template ni otro
sistema.

Ninguna es una API externa. Las dos htmx las carga la propia pantalla del CRM, desde el navegador de quien mira el
contacto, así que la sesión viaja con el pedido y el decorador no las rompe. Ahora lo dicen sus docstrings.

### 5. Nombres de grupo

**Archivos:** `support/views/contacts.py`, `support/templates/location/editar_direccion.html`,
`support/templates/location/agregar_direccion.html`

- Editar el estado de campaña de un contacto pedía `Managers` o `Admin`. El grupo es `Admins`, así que Admins no podía.
- La búsqueda manual de direcciones se escondía con `{% if not … in_group:"Sellers" %}`. `in_group` deja pasar a
  Admins, así que también se le escondía a Admins. Ahora se esconde sólo a quien está de verdad en Sellers y no es
  Admins.

## 📁 Archivos Modificados

- **`core/models.py`**: los tres permisos
- **`locale/es/LC_MESSAGES/django.po`**: sus traducciones, agregadas a mano
- **`support/views/contacts.py`**: chequeo del export, grupo del estado de campaña, staff en las dos vistas htmx
- **`support/views/all_views.py`**: permiso de no llamar, staff en `api_new_address`
- **`support/templates/contact_list.html`**, **`support/templates/campaign_management_menu.html`**,
  **`templates/components/sidebar_items/_campaign_management.html`**, **`support/templates/location/editar_direccion.html`**,
  **`support/templates/location/agregar_direccion.html`**
- **`tests/test_upload_do_not_call_numbers.py`**: el permiso deja subir la lista a alguien que no es Admin
- **`CHANGELOG.md`**

## 📁 Archivos Creados

- **`core/migrations/0130_permisos_exportar_no_llamar_activar.py`**
- **`tests/test_access_checks.py`**: export, estado de campaña y el menú de Gestión de campañas

## 🧪 Pruebas Manuales

1. **Caso normal:**
   - Darle a un Manager que no es Admin «Puede exportar contactos» y «Puede subir la lista de no llamar»
   - **Verificar:** puede exportar la lista de contactos y ve y usa «Subir lista de no llamar»
2. **Caso borde:**
   - Con un usuario de Support, abrir `/support/contacts/?export=1`
   - **Verificar:** 403, no se descarga nada. Sin `export`, la lista abre como siempre

## 📝 Notas de Despliegue

- **Se requieren migraciones:** `python manage.py migrate`
- Mergear antes que el MR del paquete de la diaria, que chequea `core.can_activate_in_web` y `core.can_export_contacts`.
  En el otro orden no se rompe nada: sin los permisos pasan sólo Admins, superusuarios y Managers, como hasta ahora.

## 🎓 Decisiones de Diseño

- **Los otros exports del base siguen abiertos a staff** (fines de suscripción, incidencias, deudores, tareas
  programadas): sus botones nunca se le escondieron a nadie.
- **`can_activate_in_web` vive en `Subscription`** aunque el base no lo use, al lado de los otros permisos de la
  suscripción, igual que `can_merge_contacts` vive en `Contact`.

---

- **Fecha:** 2026-11-25
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl183-permisos-y-chequeos-de-acceso
- **Tipo:** Corrección / Funcionalidad
- **Módulos afectados:** core, support
