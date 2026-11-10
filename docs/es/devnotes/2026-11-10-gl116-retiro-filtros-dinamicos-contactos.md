# Se retiran las pantallas «Filtros de contactos» de Soporte

- **Fecha:** 2026-11-10
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#116
- **Tipo:** Refactorización
- **Componente:** Support, Core
- **Impacto:** Experiencia de usuario, Mantenimiento

## 🎯 Resumen

Las pantallas **Soporte » Filtros de contactos** (`DynamicContactFilter`) se hicieron para mantener listas que se sincronizaran solas con Mailtrain, no para filtrar contactos. Se las seguía usando para filtrar contactos, y estaban rotas: editar un filtro daba un error 500 en producción, y crearlo daba otro. En vez de arreglar una funcionalidad que nadie debería usar, se sacan sus pantallas y sus comandos de Mailtrain. El modelo y su admin quedan, así que los 44 filtros guardados en producción no se pierden y no hay migración.

## ✨ Cambios

### 1. Se van las pantallas y la entrada del menú

**Archivos:** `support/views/all_views.py`, `support/urls.py`, `support/forms.py`, `templates/components/sidebar_items/_support.html`

Se sacan las seis vistas (`dynamic_contact_filter_new`, `dynamic_contact_filter_list`, `dynamic_contact_filter_edit`, `export_dcf_emails`, `advanced_export_dcf_list`, `sync_with_mailtrain`), sus URLs, `NewDynamicContactFilterForm`, los tres templates y la entrada del menú lateral. Las URLs viejas ahora devuelven 404.

Las dos variantes de la pantalla estaban rotas:

- **Editar** asignaba un many-to-many directamente, cosa que Django prohíbe desde la 2.0. Desde el refactor del 2024-11-02 daba `TypeError: Direct assignment to the forward side of a many-to-many set is prohibited`:

  ```python
  dcf.products = products  # necesita dcf.products.set(products)
  ```

- **Crear** usaba `debtor_contacts` sin leerlo del form, así que el paso de vista previa daba `NameError`.

Además, el modo newsletters lee `SubscriptionNewsletter`, un espejo que ya no se actualiza, así que sus conteos eran viejos incluso cuando la pantalla andaba.

### 2. Se van los comandos de Mailtrain

**Archivos:** `support/management/commands/sync_all_filters.py`, `support/management/commands/sync_one_filter.py`, `core/management/commands/synchronize_contact_filters_mailtrain.py`

Los tres comandos sincronizaban filtros con listas de Mailtrain. Sólo `synchronize_contact_filters_mailtrain` estuvo alguna vez en el cron de la diaria, y está comentado desde hace mucho. En producción ningún filtro tiene `autosync`, y la última sincronización fue el 2023-03-20.

### 3. Quedan el modelo, su admin y sus tests

**Archivos:** `core/models.py`, `core/admin.py`, `tests/test_dynamiccontactfilter.py` (sin cambios)

`DynamicContactFilter` mantiene sus campos y métodos, incluido `sync_with_mailtrain_list`. Los filtros guardados se pueden seguir consultando desde el admin, y los tests del modelo siguen pasando.

## 📁 Archivos Modificados

- **`support/views/all_views.py`** — Se sacan las seis vistas y sus imports sin uso
- **`support/urls.py`** — Se sacan sus URLs
- **`support/forms.py`** — Se saca `NewDynamicContactFilterForm`
- **`templates/components/sidebar_items/_support.html`** — Se saca la entrada «Filtros de contactos»
- **`CHANGELOG.md`** — Entrada de este cambio

## 📁 Archivos Eliminados

- **`support/templates/dynamic_contact_filter.html`** — Pantalla de alta
- **`support/templates/dynamic_contact_filter_details.html`** — Pantalla de edición
- **`support/templates/dynamic_contact_filter_list.html`** — Pantalla de listado
- **`support/management/commands/sync_all_filters.py`** — Sincronización con Mailtrain de todos los filtros con `autosync`
- **`support/management/commands/sync_one_filter.py`** — Sincronización con Mailtrain de un filtro
- **`core/management/commands/synchronize_contact_filters_mailtrain.py`** — Igual que `sync_all_filters`, el que estaba en el cron

## 🧪 Pruebas Manuales

1. **Camino feliz, el menú:**
   - Abrir el menú **Soporte**.
   - **Verificar:** «Filtros de contactos» no está, y el resto de las entradas (incluidas las de un paquete de customización) sí.

2. **Caso borde, un marcador viejo:**
   - Abrir `/support/dynamic_contact_filter/5/` o `/support/dynamic_contact_filter_list/`.
   - **Verificar:** 404.

3. **Caso borde, los filtros guardados:**
   - Abrir **Admin » Core » Dynamic Contact Filters**.
   - **Verificar:** Los filtros guardados aparecen en la lista y se pueden abrir.

## 📝 Notas de Despliegue

- No se requieren migraciones de base de datos.
- Después de deployar, borrar la línea comentada de `synchronize_contact_filters_mailtrain` del cron (en la diaria: `ss_conf/etc/cron.d/crm`). El comando ya no existe, así que descomentarla fallaría.
- Deployado en producción de la diaria el 2026-11-10 (`b00e68c0`).

## 🚀 Mejoras Futuras

- Borrar el modelo `DynamicContactFilter`, su admin, su test y su factory, con una migración.

## 🎓 Decisiones de Diseño

- **Retirarla en vez de arreglarla:** arreglar los dos errores 500 traería de vuelta una pantalla que filtra por menos criterios que el filtro de contactos que la gente debería usar, y con datos viejos de newsletters. Arreglarla además seguiría invitando a usarla.
- **Sin feature flag:** un flag mantendría vivo código roto que nadie iba a arreglar.
- **Sin redirección:** un marcador viejo da 404, y así la gente se entera de que la pantalla ya no está.
- **El modelo queda por ahora:** los filtros guardados se pueden seguir leyendo y el deploy no necesita migración.

---

- **Fecha:** 2026-11-10
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl116-retirar-filtros-de-contactos
- **Tipo de cambio:** Refactorización
- **Módulos afectados:** support, core, templates
