# Se borran el locale `es_CO` y tres campos de suscripción sin uso

- **Fecha:** 2026-11-20
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#91
- **Tipo de cambio:** Refactor
- **Componente:** Core Models, Traducciones
- **Impacto:** Esquema de la base (se borran tres columnas), traducciones

## 🎯 Resumen

Una instalación que ya no usa el CRM dejó un locale y tres campos de `Subscription` que sólo usaba su paquete de customización. `locale/es_CO/` (2.312 cadenas) no estaba en `LANGUAGES`, pero `makemessages -a` lo seguía actualizando, así que cada cambio de traducciones lo arrastraba en el diff. `purchase_date` se mostraba en el admin, pero nadie lo editaba, así que repetía el día de `creation_date`. `zoho_synced` y `zoho_sync_date` sólo los leía y escribía la sincronización con Zoho de ese paquete. Este cambio borra el locale y los tres campos.

## ✨ Cambios

### 1. Se borra `locale/es_CO/`

**Archivo:** `locale/es_CO/LC_MESSAGES/django.po`

`LANGUAGES` es `en` y `es`, y `LANGUAGE_CODE` es `es`, así que nadie lo cargaba. De ahora en más, las traducciones se actualizan con `makemessages -l es` en vez de `-a`: `-a` sólo regenera los locales que ya existen, así que `es_CO` no vuelve, pero `-l es` deja clara la intención. `compilemessages` (con o sin `-l es`) no cambia.

### 2. Se borran `Subscription.purchase_date`, `zoho_synced` y `zoho_sync_date`

**Archivos:** `core/models.py`, `core/admin.py`, `core/migrations/0128_remove_subscription_cambio_fields.py`

- Se sacan los tres campos de `Subscription`, y la línea de `purchase_date` del fieldset del admin de suscripciones.
- La migración `core.0128` borra las tres columnas de `core_subscription` y de `core_historicalsubscription`.
- Para la fecha en que se vendió una suscripción, usar `creation_date`.

## 📁 Archivos Modificados

- **`core/models.py`** — Se sacan `purchase_date`, `zoho_synced` y `zoho_sync_date` de `Subscription`
- **`core/admin.py`** — Se saca `purchase_date` del fieldset de suscripciones
- **`CHANGELOG.md`** — Entrada de este cambio

## 📁 Archivos Creados

- **`core/migrations/0128_remove_subscription_cambio_fields.py`** — Borra las tres columnas de `Subscription` y `HistoricalSubscription`

## 📁 Archivos Borrados

- **`locale/es_CO/LC_MESSAGES/django.po`** — El locale de español de Colombia, sin uso

## 📚 Detalles Técnicos

- Los campos entraron con `core.0091` (`purchase_date`, 2025-01-31) y `core.0092` (los de Zoho, 2025-02-27). Esas migraciones se quedan: sacarlas rompería el historial de migraciones de toda base existente.
- Antes de borrar se buscó en todo `~/git` (el base, el paquete de la diaria, rponline, los repos del CMS y la documentación) `purchase_date`, `zoho_synced`, `zoho_sync_date`, `es_CO` y `es-co`. Fuera de este repo sólo aparecen en clones viejos de la instalación que ya no usa el CRM.
- En la diaria, `purchase_date` coincidía con el día de `creation_date` en las 3.456 suscripciones Normal y Promoción de agosto a octubre de 2026, así que no se pierde información.
- Borrar una columna no se revierte con sus datos: `migrate core 0127` vuelve a crear las columnas vacías (con sus valores por defecto).

## 🧪 Pruebas Manuales

1. **Admin de suscripciones:** abrir una suscripción en el admin. **Verificar:** carga, y la última fila del fieldset sólo muestra el tipo de renovación.
2. **Suscripción nueva:** crear una suscripción desde un contacto (o desde la consola de ventas). **Verificar:** se guarda, y su historial no da error.
3. **Traducciones:** con el idioma en español, abrir cualquier página del CRM. **Verificar:** los textos siguen en español (el locale `es` no se toca).

## 📝 Notas de Despliegue

- **Requiere migración, apenas se mergea:** `python manage.py migrate`. Hasta que corra, **guardar cualquier suscripción falla**. `zoho_synced` es `NOT NULL` sin valor por defecto en la base (Django guarda el default sólo en Python), el código nuevo ya no lo manda, y cada guardado inserta además una fila en `HistoricalSubscription`. La ventana es lo que va del hook de deploy al `migrate`. Mergear con poca gente trabajando y fuera de la ventana de mantenimiento nocturno, que crea y actualiza suscripciones.
- Otras instalaciones: si un paquete de customización lee o escribe alguno de los tres campos, o tiene `es-co` en `LANGUAGES`, tiene que dejar de hacerlo antes de actualizar.

---

- **Fecha:** 2026-11-20
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl18-gl91-codigo-muerto
- **Tipo de cambio:** Refactor
- **Módulos afectados:** Core, Traducciones
