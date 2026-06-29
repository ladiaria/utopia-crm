# Desmapeo de Newsletters: el CMS pasa a ser la Fuente de Verdad

- **Fecha:** 2026-06-29
- **Autor:** Tanya Tree + Claude Opus 4.8
- **Ticket:** t1158 (branch `desmapeo-newsletters`)
- **Tipo:** Refactorización
- **Componente:** Core, Support, Invoicing, Settings, templates de contacto
- **Impacto:** Integridad de Datos, Experiencia de Usuario, sync CRM↔CMS

## 🎯 Resumen

El CRM mantenía un espejo local de las newsletters de cada contacto (`SubscriptionNewsletter`) y lo trataba como la verdad: en cada guardado de `Contact` empujaba la foto completa al CMS con un `.set()` destructivo, que pisaba newsletters que el CRM no conocía. Este trabajo invierte el modelo para que el **CMS sea la fuente de verdad**. El CRM deja de confiar en su espejo: **lee y edita las newsletters a demanda** contra el CMS por htmx (ficha de contacto, formulario de edición y consola de vendedores), las ediciones se aplican como **deltas no destructivos** (alta/baja de una sola newsletter), se apaga el push destructivo CRM→CMS detrás de una opción de configuración, se elimina el rudimentario diálogo de "newsletters por defecto" (ahora el CMS aplica sus propias defaults al crear la cuenta) y se retiran los mapeos de newsletters que ya no se usan. El espejo local se deja a propósito en su lugar pero congelado; el filtro por newsletter lo sigue leyendo hasta que exista un comando futuro de repoblado.

Esta es la mitad de la app base (`utopia-crm`); se complementa con endpoints REST nuevos de lectura/delta en el CMS (`utopia-cms`) y debe desplegarse junto con ellos.

## ✨ Cambios

### 1. Lectura/edición de newsletters a demanda por un proxy htmx

**Archivos:** `support/views/newsletters.py` (nuevo), `support/urls.py`, `support/views/__init__.py`,
`support/templates/contact_detail/tabs/_overview.html`,
`support/templates/contact_detail/htmx/_newsletters_htmx.html` (nuevo),
`support/templates/create_contact/tabs/_newsletters.html`,
`support/templates/create_contact/htmx/_newsletters_form_htmx.html` (nuevo),
`support/templates/create_contact/htmx/_newsletter_item.html` (nuevo),
`support/templates/create_contact/create_contact.html`, `support/views/contacts.py`

Se agregaron tres vistas proxy solo-staff. El navegador habla con el CRM (htmx); el CRM habla con el CMS con la API key que ya tiene del lado del servidor, vía `cms_rest_api_request`:

- `contact_newsletters_overview` — parcial de solo lectura para el card de la ficha de contacto.
- `contact_newsletters_form` — parcial editable (checkboxes por tipo) para el tab de Newsletters de la edición de contacto.
- `contact_newsletter_toggle` — persiste un cambio de una sola newsletter directo al CMS como **delta**, independiente del submit del formulario de contacto (así nunca pasa por `Contact.save()` ni por el espejo local).

El card de la ficha y el tab de Newsletters de la edición ahora cargan por AJAX (`hx-trigger`), separando **Newsletters** (publicación) de **Áreas** (categoría). El overview ya no precalcula el espejo (`get_all_querysets_and_lists`), y `ContactAdminFormWithNewsletters` quedó reducido a un formulario pelado (se le sacó el campo `newsletters` y su save).

Se encontraron y corrigieron dos bugs al construir el widget:

1. El item htmx de newsletter **no** debe inyectar campos enviables en el `<form>` de contacto: sus inputs ocultos `name=...` colisionaban con el campo `name` del propio Contact, así que al guardar el contacto se reemplazaba el nombre del contacto por el de una newsletter. El item ahora no lleva inputs enviables; los datos viajan solo con el request htmx vía `hx-vals` (claves `nl_*` con namespace).
2. `hx-vals='js:{...}'` no liga `this` al elemento en htmx 1.9.2, así que `this.dataset` tiraba error y **abortaba el request** (el toggle nunca se disparaba). Ahora el checkbox se referencia por `id`.

### 2. Card de Newsletters en la consola de vendedores

**Archivo:** `support/templates/seller_console.html`

Se agregó un card **Newsletters** colapsable en la columna lateral derecha, debajo del card de "Web Reading". Reusa el mismo proxy `contact_newsletters_overview` y el parcial de solo lectura, cargando por htmx — sin backend nuevo.

### 3. Apagado del push destructivo CRM→CMS detrás de una opción de configuración

**Archivos:** `core/models.py`, `settings.py`

`update_web_user_newsletters` ahora retorna temprano cuando `WEB_UPDATE_USER_NEWSLETTERS_ENABLED` es `False`. Un solo guard cubre los dos callers de signals. La opción default a `True` (compatible hacia atrás); en producción hay que ponerla en `False` para que un guardado de `Contact` no le haga `.set()` al CMS con el espejo local y borre newsletters que el CRM no espeja.

```python
if not getattr(settings, "WEB_UPDATE_USER_NEWSLETTERS_ENABLED", True):
    return
```

### 4. Se eliminó el diálogo de "newsletters por defecto"

**Archivos:** `support/views/all_views.py`, `support/templates/default_newsletters_dialog.html` (eliminado),
`core/models.py`, `core/admin.py`, `invoicing/api.py`, `settings.py`

El diálogo rudimentario que preguntaba si agregar las newsletters por defecto al crear una suscripción se eliminó de punta a punta: la vista y el template, los métodos `Contact.offer_default_newsletters_condition` / `add_default_newsletters` (y el `import_module` que usaban), los cuatro redirects en `core/admin.py` (más el helper `response_add_or_change_next_url`), la llamada en `invoicing/api.py` y la opción `CORE_DEFAULT_NEWSLETTERS`. Ahora el CMS aplica sus propias newsletters por defecto cuando crea la cuenta.

### 5. Se retiraron los mapeos de newsletters y se neutralizó la rama de `update_customer`

**Archivos:** `settings.py`, `migration_settings.py`, `core/models.py`

Se removieron `WEB_UPDATE_NEWSLETTER_MAP` y `WEB_UPDATE_AREA_NEWSLETTER_MAP` (solo los usaban el productor del CSV y `update_customer`). Como `update_customer` (el receptor CMS→CRM) leía esos mapeos dinámicamente, esa rama se neutralizó para que ignore los campos entrantes `newsletters` / `area_newsletters[_remove]`.

### 6. Settings de los endpoints de lectura/delta

**Archivo:** `settings.py`

Se agregaron `WEB_NEWSLETTERS_READ_URI` y `WEB_NEWSLETTERS_UPDATE_URI` (default `None`, derivados de `LDSOCIAL_URL`). Son POSTs que deben funcionar sin importar `WEB_CREATE_USER_ENABLED` (nunca crean usuarios web), así que se agregan a `WEB_CREATE_USER_POST_WHITELIST`.

### 7. Tests

**Archivos:** `tests/test_newsletters_proxy.py` (nuevo), `tests/test_contact.py`

`test_newsletters_proxy.py` cubre las tres vistas proxy con el CMS mockeado (8 tests). `test_contact.py` se ajustó al comportamiento sin las newsletters por defecto.

## 📁 Archivos Modificados

- **`core/models.py`** — guard en `update_web_user_newsletters`; se quitaron `offer_default_newsletters_condition` / `add_default_newsletters`; se neutralizó la rama de newsletters de `update_customer`
- **`core/admin.py`** — se quitaron los cuatro redirects del diálogo de newsletters por defecto y el helper `response_add_or_change_next_url`
- **`invoicing/api.py`** — se quitó la llamada al diálogo de newsletters por defecto
- **`settings.py`** — se agregaron `WEB_NEWSLETTERS_READ_URI` / `WEB_NEWSLETTERS_UPDATE_URI` / `WEB_UPDATE_USER_NEWSLETTERS_ENABLED` + whitelist; se quitaron `CORE_DEFAULT_NEWSLETTERS`, `WEB_UPDATE_NEWSLETTER_MAP`, `WEB_UPDATE_AREA_NEWSLETTER_MAP`
- **`migration_settings.py`** — se quitaron los settings de mapeos removidos
- **`support/views/newsletters.py`** — nuevas vistas proxy (overview / form / toggle)
- **`support/views/__init__.py`** — exporta las vistas nuevas
- **`support/urls.py`** — rutas de las vistas proxy
- **`support/views/contacts.py`** — `ContactAdminFormWithNewsletters` reducido a formulario pelado
- **`support/views/all_views.py`** — se quitó `default_newsletters_dialog`
- **`support/templates/contact_detail/tabs/_overview.html`** — el card de Newsletters carga por htmx; se quitó el precálculo del espejo
- **`support/templates/create_contact/tabs/_newsletters.html`** — el tab carga por htmx
- **`support/templates/create_contact/create_contact.html`** — se agregó el `<script>` de htmx
- **`support/templates/seller_console.html`** — nuevo card de Newsletters
- **`tests/test_contact.py`** — ajustado al nuevo comportamiento

## 📁 Archivos Creados

- **`support/templates/contact_detail/htmx/_newsletters_htmx.html`** — parcial de overview de solo lectura
- **`support/templates/create_contact/htmx/_newsletters_form_htmx.html`** — parcial de formulario editable
- **`support/templates/create_contact/htmx/_newsletter_item.html`** — item de toggle de una newsletter
- **`tests/test_newsletters_proxy.py`** — tests de las vistas proxy (CMS mockeado)

## 🧪 Pruebas Manuales

1. **Lectura y edición a demanda (caso exitoso):**
   - Abrir una ficha de contacto cuya persona exista en el CMS → el card de Newsletters carga sus newsletters activas desde el CMS.
   - Abrir el tab de Newsletters de la edición de contacto → marcar/desmarcar una newsletter → confirmar en el `Subscriber` del CMS que **solo esa** cambió.
   - Guardar el contacto → las newsletters del CMS **no** cambian (sin push destructivo).
   - **Verificar:** las lecturas reflejan el CMS en vivo; las ediciones son deltas de una sola newsletter; guardar el contacto nunca pisa el CMS.

2. **Consola de vendedores:**
   - Abrir la consola de vendedores en un contacto asociado a un subscriber del CMS.
   - **Verificar:** el card de Newsletters (debajo de "Web Reading") lista las newsletters activas; se puede colapsar.

3. **CMS inaccesible (caso borde):**
   - Apuntar las URIs del CMS a un host inaccesible (o frenar el CMS) y abrir una ficha de contacto / consola.
   - **Verificar:** la página renderiza normal; solo el card de Newsletters muestra el alert de "no se pudieron cargar las newsletters desde el CMS"; guardar el contacto sigue funcionando.

4. **Persona todavía no existe en el CMS (caso borde):**
   - Abrir un contacto cuya persona no tiene cuenta web.
   - **Verificar:** el card muestra "este contacto todavía no existe en la web" en vez de un error.

## 📝 Notas de Despliegue

- **No se requieren migraciones de base de datos.** El espejo `SubscriptionNewsletter` se deja a propósito **en su lugar y congelado** (no se elimina en este cambio).
- **Desplegar en la misma ventana que la branch del CMS** (`utopia-cms` / `utopia_cms_ladiaria`): el proxy llama a endpoints nuevos del CMS (`usuarios/api/newsletters/`, `usuarios/api/newsletter_update/`).
- **Config de producción (crítico):** poner `WEB_UPDATE_USER_NEWSLETTERS_ENABLED = False` en la config del CRM (`ss_conf`). Si queda en `True`, cada guardado de `Contact` sigue empujando un `.set()` destructivo al CMS.
- Del lado del CMS, poner `CRM_UPDATE_NEWSLETTERS_ENABLED = False` (apaga el push CMS→CRM ya innecesario).
- Las URIs nuevas se derivan de `LDSOCIAL_URL`; verificar que `LDSOCIAL_API_KEY` sea una key válida del CMS.
- Los settings removidos (`CORE_DEFAULT_NEWSLETTERS`, `WEB_UPDATE_NEWSLETTER_MAP`, `WEB_UPDATE_AREA_NEWSLETTER_MAP`) se pueden borrar de la config de prod (opcional; quedan inertes si no).
- Secuencia completa y la regla de horarios del rsync: ver `plans/desync-crm-cms/desmapeo-newsletters/PRE_DEPLOY_CHECKLIST.md`.

## 🎓 Decisiones de Diseño

- **Proxy en el CRM, no navegador→CMS directo:** mantiene la API key del CMS del lado del servidor y le da al front del CRM un único origen.
- **Delta (add/remove), nunca `.set()`:** las ediciones desde el CRM ya no pueden borrar newsletters que el CRM no conoce — ese era el bug de fondo.
- **El espejo se deja congelado, no se borra:** el filtro por newsletter todavía depende de él; eliminarlo (y la maquinaria muerta del push) es una fase de limpieza posterior, una vez que exista el comando de repoblado del filtro.

## 🚀 Mejoras Futuras

- Comando de repoblado/reconciliación (CMS→CRM por email) para restaurar el filtro por newsletter.
- Fase de limpieza: eliminar el push muerto (`update_web_user_newsletters`), su flag y los callers de signals tras un período de prueba en prod.
- Extender el mismo patrón de lectura por htmx a otras vistas que muestren newsletters.

---

- **Fecha:** 2026-06-29
- **Autor:** Tanya Tree + Claude Opus 4.8
- **Branch:** desmapeo-newsletters (t1158)
- **Tipo de cambio:** Refactorización
- **Módulos afectados:** Core, Support, Invoicing, Settings
