# Changelog

## v0.5.1

## 2026-09-04 — t1175 Cierre forzado de agendas perdidas

- Las agendas viejas que nadie volvió a trabajar dejaban al contacto colgado para siempre: seguía en la cola del vendedor y, sobre todo, **quedaba bloqueado para todas las campañas activas**, porque tener una actividad pendiente lo saca de la cola de "no contactados" de cualquier campaña. Un comando nuevo las cierra en tanda, y el estado de campaña queda marcado con una resolución nueva, **"Finalizado por agenda perdida"**, para que se sepa que el cierre fue automático y no de un vendedor
- El contacto no cambia de balde: a quien se le había hablado queda como **finalizado con contacto**, y sólo quien nunca atendió queda como finalizado sin contacto. Esto importa porque mandarlos a todos al mismo lado habría metido en el listado de "inubicables" a gente con la que sí se habló, y hundido los porcentajes históricos de todas esas campañas. Las ventas ya registradas nunca se pisan
- El comando pide la fecha de corte sin default —nadie cierra agendas por accidente—, tiene modo de prueba que no escribe nada y puede volcar a un CSV las filas que va a tocar, para revisarlas antes de ejecutar. La fecha pactada de cada agenda se conserva, igual que la fecha de última acción del contacto
- Se reemplazó el comando viejo `close_old_pending_activities_and_campaign_status`, que hacía lo mismo de forma destructiva: cerraba **todo** como "sin contacto" sin mirar lo que ya estaba resuelto y, cuando se corrió en producción el 2025-07-01, **pisó 181 ventas**. Ahora aborta con un mensaje que apunta al nuevo. Reparar esas 181 ventas queda para otro ticket
- Deployment: **se requieren migraciones** (`core.0122` y `support.0041`, sólo choices), hay que correr `populate_seller_console_actions` después de migrar (si no, el comando aborta) y `compilemessages` para que la etiqueta se vea en español
- **Author:** Tanya Tree + Claude Opus 5

## 2026-08-27 — t1157-cola-takeover Cola de takeovers de email para el call center

- Cuando alguien quiere usar un email que en la web pertenece a otra cuenta suya sin vincular, el call center se trababa y **no se podía guardar nada** de la ficha: ni el teléfono, ni la dirección, ni lo que el operador acabara de corregir. Ahora el email es lo único que no se aplica —el resto del contacto se guarda— y queda anotado un pedido para resolverlo aparte. Sin el pedido, el conflicto no dejaba ningún rastro: nadie sabía que había existido
- El pedido lo resuelve alguien con el permiso `core.can_takeover_email` desde una pantalla nueva, que muestra las dos cuentas web y qué pasaría al aprobar antes de decidir. **El operador que archiva el pedido no puede aprobarlo, y es a propósito:** aprobar puede borrar una cuenta web. Escribir la URL de la pantalla a mano da 403
- Encolar es **opt-in por vista**: cada pantalla que quiere archivar pedidos lo declara. Todo lo demás —tareas nocturnas, comandos, importaciones— se comporta exactamente como antes, así que una carga masiva no llena la cola
- Al aprobar, las newsletters de las dos cuentas se unen en la que queda —nunca se pierden— y recién después se borra la vieja. Rechazar no toca nada. Un takeover hecho a mano deja el mismo rastro auditable que uno venido de la cola
- Se corrigieron cinco cadenas de traducción al español que habían quedado marcadas `fuzzy` con la traducción de otra cadena parecida, y por eso salían sin traducir
- Deployment: **se requiere migración** (`core.0121`), y hay que correr `compilemessages` o la pantalla se ve en inglés. El aviso a los revisores se configura con `EMAIL_TAKEOVER_NOTIFY_RECIPIENTS` y `EMAIL_TAKEOVER_NOTIFY_BASE_URL`; sin destinatarios cae en `mail_managers`
- **Author:** Tanya Tree + Claude Opus 5

## 2026-08-24 — fix/upload_do_not_call_numbers Reemplazo atómico de la lista de "no llame"

- La subida de la lista de "no llame" borraba los números en una transacción e insertaba los nuevos en otra. Si dos subidas se pisaban (un doble clic en el botón, un reenvío del formulario) la segunda podía chocar con lo que la primera estaba insertando y fallar con un error de clave duplicada; y si el insert fallaba por cualquier motivo, la lista quedaba **vacía**, con lo que el call center pasaba a poder llamar a todo el mundo. Ahora el borrado y la inserción ocurren en una sola transacción: o entra la lista nueva completa, o queda la anterior intacta
- Un archivo con números repetidos, filas vacías o valores demasiado largos abortaba la carga entera. Ahora esas filas se descartan y la pantalla informa cuántos números se cargaron y cuántas filas se ignoraron. Un archivo del que no sale ningún número válido no borra nada
- Mejoró el tiempo de carga (de 7,0 s a 4,7 s con un archivo de 512.734 números) y el consumo de memoria, y dos subidas simultáneas ahora se serializan en vez de pisarse
- La herramienta pasa a estar restringida a superusuarios y al grupo Admins, porque destruye la lista completa; los accesos del menú de Gestión de Campañas y del sidebar se ocultan al resto. La pantalla se reescribió: tenía textos de "información complementaria de direcciones" por un copy-paste y no explicaba que reemplaza la lista entera. Además ahora permite elegir cuántas filas de encabezado saltear y acepta archivos en latin-1
- Deployment: no se requieren migraciones
- **Author:** Tanya Tree + Claude Opus 5

## 2026-07-03 — t1160 Mejoras al flujo de direcciones y georreferenciación

- `address_1` y `address_2` pasan a ser obligatorios en el formulario de direcciones (agregar y editar), porque los operarios se estaban olvidando de cargarlos
- Editar una dirección pasa a ser un flujo de un solo paso: buscador de sugerencias + checkbox de "cargar manualmente", igual que agregar dirección, sin depender de la pantalla de normalizar dirección para el caso común (esa pantalla se sigue usando para el georef masivo y como acceso directo desde la ficha del contacto)
- Se corrigieron varios bugs donde una dirección quedaba marcada como verificada con coordenadas que ya no correspondían al texto cargado (al editar el texto sin rehacer la búsqueda, o al tildar "no encuentro la dirección"), y un error no manejado en normalizar dirección que expulsaba al usuario con un mensaje confuso cuando la sugerencia elegida no tenía departamento
- En la ficha de contacto (pestaña resumen), una dirección con "necesita georreferenciación" ya no oculta el botón para normalizarla
- El servicio de georreferenciación (Uruguay) ahora tiene timeout y manejo de errores de red para no colgarse cuando el servicio no responde, con un interruptor dinámico vía el admin (`Variable` "georef_services_enabled") que se puede apagar a mano o que se apaga solo tras 3 fallos consecutivos
- Deployment: no se requieren migraciones
- **Author:** Tanya Tree + Claude Sonnet 5

## 2026-06-29 — desmapeo-newsletters (t1158) El CMS pasa a ser la fuente de verdad de las newsletters

- El CRM dejó de mantener su espejo de newsletters como verdad: ahora las lee y edita a demanda contra el CMS. En la ficha de contacto, en el formulario de edición y en la consola de vendedores las newsletters se cargan por AJAX desde el CMS, y los cambios se guardan uno por uno (alta/baja puntual) directo en el CMS, sin pisar el resto
- Se apagó el envío destructivo de newsletters del CRM al CMS (el que en cada guardado de contacto reemplazaba la lista completa). Queda detrás de una opción de configuración para poder prenderlo/apagarlo
- Se eliminó el diálogo de "newsletters por defecto" al crear suscripciones: ahora las aplica el CMS al crear la cuenta. Se retiraron además los mapeos de newsletters que ya no se usan
- El filtro de contactos por newsletter queda temporalmente sin datos nuevos (sigue leyendo el espejo viejo) hasta un proceso futuro de repoblado; el espejo no se borró
- Deployment: no se requieren migraciones. Hay que desplegar en la misma ventana los cambios del CMS y poner `WEB_UPDATE_USER_NEWSLETTERS_ENABLED = False` en producción (ver el pre-deploy checklist del frente)
- **Author:** Tanya Tree + Claude Opus 4.8

## 2026-06-19 — feature/export-all-campaigns-status Exportación CSV de estado de contactos en todas las campañas

- Se agregó una nueva herramienta en el menú de Gestión de Campañas para descargar por CSV el estado de los contactos (ContactCampaignStatus) de todas las campañas a la vez, con los mismos filtros que la vista de estadísticas por campaña. Cada fila es un estado de contacto, así que un mismo contacto puede aparecer varias veces si pertenece a más de una campaña
- Por defecto la vista no devuelve nada: hay que elegir una "fecha de asignado (desde)" para que filtre y exporte, evitando descargar todo el histórico. El resto de los filtros (campaña, vendedor, estado) son opcionales y si no se elige campaña se incluyen todas
- Se corrigió el cálculo de "Veces contactado", que venía mostrando 0 casi siempre porque leía un campo del modelo que nunca se persiste. Ahora se calcula contando las llamadas completadas registradas para ese contacto en esa campaña, tanto en la vista nueva como en la vista de estadísticas por campaña existente
- Deployment: no se requieren migraciones
- **Author:** Tanya Tree + Claude Opus 4.8

## 2026-06-16 — t1156 Infraestructura de reporte de errores: logging y soporte de Sentry

- Se agregó configuración de logging que mantiene el comportamiento por defecto de Django: los errores no atrapados se mandan por email a los `ADMINS` y todo se escribe en la salida estándar para que el log de uWSGI lo capture. No se crean archivos de log en disco
- Se incorporó `sentry-sdk` como dependencia y se documentó en el `local_settings_sample.py` cómo inicializar Sentry (solo en producción) para que los errores del CRM lleguen al panel de Sentry
- Se documentaron las nuevas variables de configuración: `ADMINS`/`MANAGERS`, las de Sentry y la lista de destinatarios de errores de alta de suscripción por MercadoPago (la lógica que las usa vive en utopia-crm-ladiaria)
- Deployment: requiere instalar la nueva dependencia (`pip install -r requirements.txt`); no se requieren migraciones. Sentry y los destinatarios se configuran en `local_settings.py` de cada ambiente
- **Author:** Tanya Tree + Claude Opus 4.8

## 2026-06-15 — t1154 Reasignación masiva de estado de incidencias

- Desde el listado de incidencias ahora se puede cambiar el estado de varias incidencias a la vez: se seleccionan con casillas por fila y una casilla que marca todas las visibles de la página
- Cuando la página está toda seleccionada, aparece la opción de extender la selección a todas las incidencias del filtro (estilo Gmail); esa opción solo se ofrece y solo se acepta cuando el filtro tiene un estado y una subcategoría elegidos, para evitar reasignar absolutamente todas las incidencias por accidente
- Antes de aplicar, una pantalla de confirmación muestra cuántas incidencias se van a tocar, el desglose por estado actual y el rango de fechas (la más vieja y la más nueva)
- La herramienta es solo para superusuarios y el grupo Admins; cada cambio queda registrado en el log de administración (estado anterior → nuevo)
- No se requieren migraciones
- **Author:** Tanya Tree + Claude Opus 4.8

## 2026-06-09 — t1151 La consola de vendedores siempre registra una actividad y agenda con la acción correcta

- Al resolver un contacto nuevo desde la consola, ahora siempre se crea un registro de actividad — incluso para acciones como "No interesado", "No llamar" o "Logística", y aunque el campo de notas quede vacío. Antes estas acciones cerraban el estado de campaña sin dejar ningún registro de actividad
- El único caso que no deja actividad es el botón "Omitir y pasar al siguiente contacto", que simplemente saltea el contacto sin registrar resolución
- Al agendar, la actividad pendiente futura (la llamada agendada) ahora queda con la acción de consola "Agendar"; antes nacía sin acción. Cuando el vendedor atiende esa llamada, la acción se sobreescribe con la resolución real elegida
- No se requieren migraciones
- **Author:** Tanya Tree + Claude Opus 4.8

## 2026-05-11 — t1144 Ranking de productos y métricas de conversión en estadísticas de campaña

- La vista de estadísticas de campaña ahora muestra los productos vendidos ordenados de mayor a menor, filtrando los que no tienen ventas; la antigua tabla plana sin orden fue reemplazada
- La tarjeta "Producto más vendido" fue expandida a un ranking con podio visual (trofeo dorado, medalla plateada, medalla bronce para los primeros tres) y lista simple para el resto
- Se agregaron dos nuevas tarjetas en la columna lateral: total de productos vendidos y promedio de productos por suscriptor con éxito (resolución S2)
- La tarjeta "Conversión de la base" ahora muestra un gráfico de dona (doughnut) junto al texto usando Chart.js, ya incluido en AdminLTE
- Se corrigió un N+1: el conteo de ventas por producto pasó de N queries individuales a una sola query con GROUP BY
- No se requieren migraciones
- **Author:** Tanya Tree + Claude Sonnet 4.6

## 2026-05-08 — t1143 Fix seller takeover in ValidateSalesRecord and SalesRecordCreate

- Validating a sale with "can be commissioned" no longer overwrites the seller of every type-S product on the subscription — the update now applies only to products explicitly listed in that specific SalesRecord
- This prevented a silent data-integrity bug: after a product change or additional-product flow, validating the partial SalesRecord could reassign another seller's products to the validating seller
- The fix applies to both `ValidateSubscriptionSalesRecord` and `SalesRecordCreateView`; both shared the same overly broad bulk-update
- Two regression tests added to `tests/test_product_change_seller.py` to lock this behaviour
- No migrations required
- **Author:** Tanya Tree + Claude Sonnet 4.6

## 2026-04-29 — t1132 Seller attendance tracking for call center staff

- New `Shift`, `AbsenceReason`, `AttendanceRecord`, and `SellerAttendance` models allow daily attendance and absence tracking for call center sellers
- Two new boolean fields on `Seller`: `call_center` marks who is subject to attendance tracking; `shift` (FK) links to a configurable `Shift` with start and end times editable from the admin
- A new "Seller Attendance" view under Campaign Management lets managers consult daily attendance and admins/superusers record it; statuses are Present or Absent, with a required justified/unjustified reason for absences
- `BreadcrumbsMixin` in `core/mixins.py` now has full docstring explaining usage and the `@cached_property` / plain-method / `get_context_data` interaction
- Migrations required; load `support/fixtures/shifts.json` after migrating to seed the two default shifts (Matutino 09:00–17:00, Vespertino 17:00–21:00)
- **Author:** Tanya Tree + Claude Sonnet 4.6

## v0.5.0 (2026-04-29)

## 2026-04-24 — t1126 SalesRecord creation for product change, additional product, and retention flows

- Product change, additional product, and retention discount views now always create a `SalesRecord` (type PARTIAL) so sales appear in the manager sales filter — they were previously invisible there
- In the ladiaria `edit_subscription` view, multiple products added in one session now produce a single PARTIAL `SalesRecord` instead of one per product
- The validate-sale form (`can_be_commissioned` checkbox) now defaults to checked for all sale types; an explanatory note was added so managers understand the commission implications
- Fixed an `AttributeError` bug: `SalesRecord.TYPES.PARTIAL` corrected to `SalesRecord.SALE_TYPE.PARTIAL` in `book_additional_product`
- No migrations required
- **Author:** Tanya Tree + Claude Sonnet 4.6

## 2026-04-08 — t0243 Canceled invoices report view in invoicing app

- A new `CanceledInvoicesReportView` is available in the base CRM, replacing the function view that previously existed only in the ladiaria customisation layer
- Access is restricted to the Admins group, the Finances group, and superusers
- A date-range form renders a CSV download of canceled invoices with prefetched line items and credit notes to avoid slow queries on large datasets
- All column headers are marked for translation
- No migrations required
- **Author:** Tanya Tree + Claude Sonnet 4.6

## 2026-04-07 — t1093 added_products field on Subscription

- Added `added_products` M2M field to `Subscription` (mirrors `unsubscription_products` on the departing subscription)
- Extended `add_product()` with an optional `track_as_added=False` parameter; when `True`, the product is also recorded in `added_products`
- `book_additional_product()` and `product_change()` in `support/views/subscriptions.py` now pass `track_as_added=True` for genuinely new products (copied products are unaffected)
- **Migration:** `0118_subscription_added_products`
- **Author:** Tanya Tree + Claude Sonnet 4.6

## 2026-04-06 — t1091 Campaign status edit for managers and admins

- Managers, Admins, and superusers can now edit the campaign status (status, resolution, and resolution reason) of a contact directly from the contact detail page
- A dedicated edit view shows the campaign info read-only alongside a small form restricted to the editable fields
- Non-authorised staff see the campaigns tab as before — no change to their experience
- No migrations required
- **Author:** Tanya Tree + Claude Sonnet 4.6

## 2026-04-06 — t1088 Campaign statistics: count sold products only

- Campaign statistics detail view now counts only products registered as sold via SalesRecord, not all products currently on the subscription linked to the campaign
- CSV export of campaign statistics fixed with the same approach, accumulating products across multiple sale records per contact when present
- No migrations required
- **Author:** Tanya Tree + Claude Sonnet 4.6

## 2026-04-01 - t1082 Bugfix

- Reactivate subscription was not marking it as active
- No migration required

## 2026-03-31 — t1081 Invoice detail view UX improvements

- Improved layout and readability of the invoice detail view
- No migrations required

## 2026-03-26 — t1071 Campaign statistics rate redefinitions

- Redefined campaign statistics rates and centralised contacted statuses logic
- No migrations required

## 2026-03-25 — t1069 Open issues panel in seller console + safe message fixes

- Added open issues summary panel to the seller console
- Fixed safe message rendering issues
- No migrations required

## 2026-03-24 — t1065 Email bounce warnings

- Added email bounce warnings to contact views and forms
- No migrations required

## 2026-03-23 — t1063 Do-not-call warnings

- Added do-not-call warnings to phone fields across views
- No migrations required

## 2026-03-23 — t1062 Subscription reactivation improvements

- Fixed billing date shift on reactivation; added payment method editing
- No migrations required

## 2026-03-20 — t1060 Contact detail overview UX and performance

- Redesigned overview tab with compact layout and expand/collapse functionality
- Optimized contact detail view queries
- No migrations required

## 2026-03-10 — t1052 Campaign statistics CSV export

- Added CSV export to the campaign statistics detail view with optimized queries
- No migrations required

## 2026-03-06 — Issue confirmation messages

- Added confirmation dialogs to issue state-change actions
- No migrations required

## 2026-03-05 — t1047 Issue detail view UX refinements

- Follow-up UX improvements to the issue detail view redesign
- No migrations required

## 2026-03-04 — t1044 Issue detail view redesign + date_modified field

- Redesigned issue detail view with compact layout
- Added `date_modified` field to the Issue model
- Migrations required

## 2026-03-02 — Seller console scheduled activity fixes

- Fixed scheduled activity display and date filtering in the seller activities page
- No migrations required

## 2026-02-27 — Seller console "Not found" button

- Added "Not found" action to the seller console with visual indicators
- No migrations required

## 2026-02-23 — t1034 Community manager dashboard and assignment

- Added community manager dashboard with issue assignment and team overview
- Improved issue assignment with status handling and optimized saves
- No migrations required

## 2026-02-10 — t1030 Community management console

- Added community management console with permission-based access and temporal issue grouping
- Migrations required

## 2026-02-06 — t1026 Invoice filter view modernization

- Modernized invoice filter view with additional contact search fields and improved UI
- No migrations required

## 2026-01-28 — t1017 Issue resolution field integration

- Added IssueResolution model with dynamic subcategory-based filtering and admin interface
- Migrations required

## 2026-01-26 — Subscription route change with special route automation

- Added individual subscription route change system with automatic issue creation for special routes
- Migrations required

## 2026-01-21 — Issue next action date automation and filtering

- Added automatic next_action_date setting on status change
- Added advanced filtering and sortable columns to issue management
- No migrations required

## 2026-01-19 — Address merge functionality

- Added side-by-side address merge with field selection
- No migrations required

## 2025-12-29 — Campaign editing in sales validation

- Allowed campaign editing within the sales validation workflow
- No migrations required

## 2025-12-18 — t990 Subscription reactivation feature

- Added subscription reactivation workflow from the contact detail view
- No migrations required

## 2025-12-17 — t989 Fix contact update field clearing

- Fixed a bug where updating a contact incorrectly cleared unrelated fields
- No migrations required

## 2025-12-16 — t988 Corporate/affiliate subscriptions

- Added support for corporate and affiliate subscription types
- Migrations required

## 2025-12-16 — Sales record filter enhancements

- Improved filtering options in the sales record view
- No migrations required

## 2025-12-11 — Campaign resolution tracking

- Added resolution tracking to campaign outcomes
- No migrations required

## 2025-12-08 — Campaign statistics filterview enhancement

- Improved filtering and display in the campaign statistics view
- No migrations required

## 2025-12-04 — Retention discount product addition

- Extended retention discounts to support adding products
- No migrations required

## 2025-12-01 — Retention discount management

- Added retention discount management to the subscription workflow
- Migrations required

## 2025-11-28 — Invoice expiration date logic correction

- Fixed incorrect expiration date calculation for invoices
- No migrations required

## 2025-11-27 — Never-paid issues dedicated page

- Added a dedicated page for contacts with unpaid issues
- No migrations required

## 2025-11-26 — Sales record breadcrumbs and template blocks

- Improved breadcrumb navigation and template block structure in sales record views
- No migrations required

## 2025-11-14 — Bulk delete campaign status

- Added bulk delete for campaign status records
- No migrations required

## 2025-11-13 — Phone matching plus symbol flexibility

- Phone number matching now handles leading `+` symbols correctly
- No migrations required

## 2025-11-12 — Free subscription management

- Added management interface for free subscriptions
- No migrations required

## 2025-11-10 — Contact list CSV export, UI enhancements, issue forms modernization

- Added CSV export to the contact list with optimized queries
- Modernized issue forms UI
- Added email uniqueness validation in promo forms
- Contact list UI enhancements
- No migrations required

## 2025-11-06 — Phone number checking functionality

- Added phone number format checking across contact forms
- No migrations required

## 2025-11-05 — Fix seller preservation in subscription products

- Fixed a bug where seller assignment was lost when modifying subscription products
- No migrations required

## 2025-11-04 — Choices modernization + populate SubscriptionProduct original_datetime

- Modernized Django choices usage across models
- Added management command to backfill `original_datetime` on SubscriptionProduct records
- No migrations required

## 2025-10-31 — Contact detail UI improvements + import contacts enhancements

- Multiple UI improvements to the contact detail view
- Email protection added to import contacts flow
- Updated promo view and subscription UI
- No migrations required

## 2025-10-30 — Product model and subscription form fixes

- Fixed various issues in the product model and subscription form
- No migrations required

## 2025-10-29 — Subscription form UI improvements

- UI polish and usability improvements to the subscription form
- No migrations required

## 2025-10-28 — Import contacts enhancements

- Improved import contacts functionality and documentation
- No migrations required

## 2025-10-21 — Modernize views, optimize performance, seller console UI

- Modernized several views and improved query performance
- UI improvements to the seller console and templates
- No migrations required

## 2025-10-16 — Fix test failures (history and import)

- Fixed failing tests related to contact history and import functionality
- No migrations required

---

## version 0.4.7 (2023-12-31)

- Email validation using a better python module.
- Migration fixes.
- Import contacts fixes.
- Address management fixes.
- Many other minor fixes and improvements.

## version 0.4.6 (2023-10-17)

- First "tagged" release, this "first" version number was set to the same version number that Utopia-CMS will release today, we will use this convention to know better the compatibility of both systems (api calls, custom sync scripts, etc).
- The most important change in this commit is the settings improvements, removing unnecessary settings, adding others that are used in code without specifing a default value, and updating samples files accordingly.
