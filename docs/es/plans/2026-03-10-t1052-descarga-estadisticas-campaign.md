# Plan: Descarga de estadísticas de campañas (Trello: t1052)

**Responsable:** @tanyatree · **Estado:** ✅ Completado · **Actualizado:** 2026-03-10

## Contexto

Agregar un botón de descarga de estadísticas de campañas en la vista de campañas.

Se nos proveyó desde el equipo de ventas el siguiente texto como petición:

> Posibilidad de descargar csv asociado a una campaña, con resultado de cada contacto. Todos los prospectos, con resolución de campaña y productos vendidos (separados por coma), fecha de asignación, fecha de resolución, cantidad de actividades, vendedor, fecha de inicio de la suscripción.

En la vista CampaignStatisticsDetailView se muestra la información de cada contacto de la campaña, se debe agregar un botón de descarga de estadísticas de campañas en la vista de campañas.

El equipo de ventas refiere a los "prospectos" como los contactos de la campaña (cada uno de los contactos con ContactCampaignStatus). Si la suscripción fue exitosa, se debe mostrar la fecha de inicio de la suscripción y los productos que fueron vendidos separados por coma. ContactCampaignStatus tiene bastantes campos que pueden ser útiles para esta descarga, ponderar usar la mayor cantidad de estos campos posibles y más cosas relevantes para el usuario como por ejemplo la cantidad de actividades. No recuerdo bien cómo se asocia la suscripción con la campaña o cómo se ven los productos vendidos en la campaña así que deberíamos documentar esto en el proceso. Se puede revisar el modelo Subscription para entender cómo se asocia la suscripción con la campaña y también la vista que utilizan los vendedores para poder generar suscripciones (view con el name "new_subscription" o LaDiariaSubscriptionCreateView que extiende de LadiariaSubscriptionMixin y a su vez esta extiende SubscriptionMixin de la aplicación base utopia-crm).

Esto debe generarse en un archivo CSV y de ser posible se debería intentar descargarlo directamente sin necesidad de guardar el archivo en el servidor por lo que cualquier mejora en el proceso sería bienvenida especialmente de base de datos.

## Objetivos y No Objetivos

- Objetivos: Agregar un botón de descarga de estadísticas de campañas en la vista de campañas.

## Documentación: Relación Suscripción-Campaña

El modelo `Subscription` tiene un FK `campaign` hacia `Campaign`. Cuando un vendedor realiza una venta exitosa a través de la consola de vendedor, se vincula la suscripción a la campaña mediante `ContactCampaignStatus.handle_direct_sale()` que ejecuta `subscription.campaign = self.campaign`. Los productos vendidos se obtienen desde `SubscriptionProduct` (through model de `Subscription.products`), cada uno con su FK a `Product`.

Flujo completo:

1. Vendedor usa la consola → marca venta exitosa → `handle_direct_sale()` se ejecuta
2. La suscripción creada recibe `subscription.campaign = campaign`
3. Para la exportación: se consultan todas las `Subscription` con `campaign=X` y sus `SubscriptionProduct` → `Product`

## Implementación Realizada

### Archivos modificados

- **`support/views/all_views.py`** — Se agregaron métodos `get()` y `export_csv()` a `CampaignStatisticsDetailView`
- **`support/templates/campaign_statistics_detail.html`** — Se agregó botón verde "Export CSV" junto a las acciones de filtro

### Columnas del CSV (17)

| Columna | Origen |
| --- | --- |
| ID Contacto, Nombre, Email, Teléfono, Celular | Modelo `Contact` |
| Estado | `ContactCampaignStatus.get_status()` |
| Resolución de campaña | `ContactCampaignStatus.get_campaign_resolution()` |
| Razón de resolución | `ContactCampaignStatus.get_resolution_reason()` |
| Vendedor | `ContactCampaignStatus.seller.name` |
| Fecha asignación, Última acción, Fecha creación | Campos de fecha de `ContactCampaignStatus` |
| Veces contactado | `ContactCampaignStatus.times_contacted` |
| Cantidad de actividades | Anotación `Count` de actividades para esta campaña |
| Última acción de consola | `SellerConsoleAction.name` |
| Fecha inicio suscripción | `Subscription.start_date` |
| Productos vendidos | Nombres de `SubscriptionProduct` separados por coma |

### Optimizaciones de base de datos

- `select_related` para contact, seller, last_console_action (evita N+1 en FKs)
- Anotación `Count` para cantidad de actividades (una sola consulta)
- Precarga masiva de suscripciones en un diccionario `contact_id → datos` (2 consultas totales)
- `iterator(chunk_size=1000)` para eficiencia de memoria
- El CSV se escribe directamente al `HttpResponse` sin guardar archivo en servidor

### Enfoque técnico

Se usó un parámetro GET `?export=csv` en la misma URL del FilterView. El botón es un `<button type="submit" name="export" value="csv">` dentro del `<form>` de filtros existente, lo que automáticamente incluye todos los filtros activos. No se necesitó agregar una URL nueva.

## Changelogs

- EN: `docs/en/changelogs/2026-03-10-t1052-campaign-statistics-csv-export.md`
- ES: `docs/es/changelogs/2026-03-10-t1052-descarga-csv-estadisticas-campana.md`
