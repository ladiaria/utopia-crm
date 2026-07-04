# Funcionalidad: Exportar a CSV el estado de contactos de todas las campañas

- **Fecha:** 2026-06-19
- **Autor:** Tanya Tree + Claude Opus 4.8
- **Ticket:** feature/export-all-campaigns-status
- **Tipo:** Funcionalidad (+ Corrección)
- **Componente:** Support — Gestión de Campañas, Modelos Core (ContactCampaignStatus, Activity)
- **Impacto:** Reportes de Campaña, Exportación de Datos, Integridad de Datos

## 🎯 Resumen

La vista de estadísticas por campaña existente (`/support/campaign_statistics/<pk>/`) permite exportar los registros de `ContactCampaignStatus` de una sola campaña, pero no había forma de exportarlos de **todas** las campañas a la vez. Este cambio agrega una nueva vista, `AllCampaignsStatusExportView`, que genera por streaming un CSV con el estado de los contactos a través de todas las campañas, usando los mismos filtros que la vista por campaña. Como ese conjunto de datos sería enorme, la vista no devuelve nada por defecto: requiere un filtro de fecha de asignado (desde) antes de mostrar o exportar datos. Al construirla confirmamos un bug que la usuaria sospechaba: la columna "Veces contactado" mostraba casi siempre `0` porque leía el campo persistido `ContactCampaignStatus.times_contacted`, que nunca se incrementa en ninguna parte del código. Ahora se calcula al vuelo contando las llamadas completadas de ese contacto en esa campaña, tanto en la vista nueva como en la exportación por campaña existente.

## ✨ Cambios

### 1. Nueva vista de exportación global

**Archivo:** `support/views/all_views.py`

`AllCampaignsStatusExportView` es un `FilterView` sobre `ContactCampaignStatus` (no acotado a una campaña). Replica los permisos de la vista por campaña (grupo `Managers` o superuser, `staff_member_required`). No devuelve nada hasta que se selecciona una fecha:

```python
def has_date_filter(self):
    return bool(self.request.GET.get("date_assigned_min"))

def get_queryset(self):
    if not self.has_date_filter():
        return ContactCampaignStatus.objects.none()
    return ContactCampaignStatus.objects.all()
```

La página muestra un formulario de filtros y una vista previa paginada; `?export=csv` dispara un `StreamingHttpResponse` (BOM UTF-8 para Excel, buffer `io.StringIO` vaciado por fila, `iterator(chunk_size=1000)`), siguiendo el patrón de exportación de asistencia de vendedores que ya existe en el código.

### 2. Cálculo correcto de "Veces contactado" (correlacionado por campaña)

**Archivo:** `support/views/all_views.py`

Como la consulta global abarca muchas campañas, el conteo de llamadas completadas debe correlacionar el `Activity.campaign` con la `ContactCampaignStatus.campaign` de cada fila. Se usa un `Subquery` correlacionado (no un `Count` con `F('campaign')`, poco confiable bajo un `GROUP BY` multi-campaña):

```python
times_contacted_sq = (
    Activity.objects.filter(
        contact=OuterRef("contact"),
        campaign=OuterRef("campaign"),
        activity_type="C",
        status="C",
    )
    .order_by()
    .values("contact")
    .annotate(c=Count("id"))
    .values("c")
)
filtered_qs = filtered_qs.annotate(
    times_contacted_real=Coalesce(Subquery(times_contacted_sq, output_field=IntegerField()), 0),
    activity_count=Coalesce(Subquery(activity_count_sq, output_field=IntegerField()), 0),
)
```

`activity_count` usa la misma correlación (sin el filtro de tipo/estado) para que el conteo corresponda a ese par contacto-campaña y no a otra campaña del mismo contacto. Los productos vendidos se mapean por `(contact_id, campaign_id)` desde `SalesRecord.products`, construidos una sola vez antes del streaming y acotados por los contactos/campañas filtrados.

### 3. Corrección del mismo bug en la exportación por campaña existente

**Archivo:** `support/views/all_views.py`

`CampaignStatisticsDetailView.export_csv` exportaba el campo `ccs.times_contacted` crudo (siempre `0`). Como esa vista es de una sola campaña, alcanza con un `Count` simple con filtro de campaña constante (sin Subquery):

```python
times_contacted_real=Count(
    "contact__activity",
    filter=Q(
        contact__activity__campaign=self.campaign,
        contact__activity__activity_type="C",
        contact__activity__status="C",
    ),
)
```

La fila del CSV ahora usa `ccs.times_contacted_real`. No se toca el campo del modelo (no se agrega lógica de persistencia); el conteo al vuelo coincide con lo que ya calcula la consola de vendedores.

### 4. Nuevo filtro, URL, card del menú e ítem del sidebar

**Archivos:** `support/filters.py`, `support/urls.py`, `support/templates/campaign_management_menu.html`, `templates/components/sidebar_items/_campaign_management.html`

`AllCampaignsContactStatusFilter` reutiliza los mismos campos que `ContactCampaignStatusFilter` (vendedor, estado, `date_assigned_min/max`, `last_action_date_min/max`) más un filtro opcional `campaign` para acotar a un subconjunto. El comportamiento de "vacío por defecto" se aplica en la vista, no en el filtro, para que el filtro siga siendo reutilizable. Se agregaron una nueva URL (`all_campaigns_status_export`), una card en la sección "Tracking and reports" del menú de gestión de campañas y un ítem en el sidebar.

### 5. Template con nota de uso

**Archivo:** `support/templates/all_campaigns_status_export.html` (nuevo)

La página aclara que **solo** la fecha de asignado es obligatoria y que los demás filtros son opcionales — si se deja la campaña vacía se incluyen todas — para que los operadores no confundan los campos no obligatorios con obligatorios.

## 📁 Archivos Modificados

- **`support/views/all_views.py`** — Se agregó `AllCampaignsStatusExportView`; se agregaron imports (`io`, `Subquery`, `IntegerField`, `Coalesce`); se corrigió `times_contacted` en `CampaignStatisticsDetailView.export_csv`
- **`support/filters.py`** — Se agregó `AllCampaignsContactStatusFilter`
- **`support/urls.py`** — Se agregó la ruta `all_campaigns_status_export`
- **`support/templates/campaign_management_menu.html`** — Se agregó la card "Export all campaigns status"
- **`templates/components/sidebar_items/_campaign_management.html`** — Se agregó el ítem del sidebar

## 📁 Archivos Creados

- **`support/templates/all_campaigns_status_export.html`** — Formulario de filtros, nota de uso, vista previa paginada y botón de descarga del CSV

## 📚 Detalles Técnicos

**Por qué el campo daba siempre 0:** `ContactCampaignStatus.times_contacted` es un `SmallIntegerField(default=0)` que nunca se incrementa ni se guarda en ninguna parte del código. La consola de vendedores calcula el valor real al vuelo (`contact.activity_set.filter(activity_type="C", status="C", campaign=campaign).count()`) pero no lo persiste, así que cualquier lectura del campo crudo veía `0`. La corrección calcula el mismo valor en tiempo de consulta en lugar de tocar el modelo.

**Por qué Subquery y no `F('campaign')` en la vista global:** un `Count('contact__activity', filter=Q(... campaign=F('campaign')))` une `Activity` por contacto y puede inflar o correlacionar mal los conteos bajo un `GROUP BY` multi-campaña. Un `Subquery` correlacionado con `OuterRef("campaign")` devuelve un escalar por fila, correctamente asociado a la campaña de esa fila, sin inflar filas.

## 🧪 Pruebas Manuales

1. **Caso exitoso — exportar con una fecha:**
   - Abrir Gestión de Campañas → "Export all campaigns status".
   - Seleccionar una "fecha de asignado (desde)" dentro de un período con datos y hacer clic en "Descargar CSV".
   - **Verificar:** Se descarga un CSV con una fila por estado de contacto a través de todas las campañas; el encabezado está traducido y la columna "Veces contactado" muestra conteos reales (no todos ceros).

2. **Veces contactado coincide con la consola de vendedores:**
   - Elegir un contacto con varias llamadas completadas en una campaña.
   - **Verificar:** El "Veces contactado" del CSV para ese par contacto-campaña es igual al conteo que muestra la consola de vendedores (ej. 6 llamadas → 6).

3. **Caso borde — sin fecha no devuelve nada:**
   - Abrir la vista sin seleccionar fecha; probar también `?export=csv` sin fecha.
   - **Verificar:** La vista previa está vacía con una nota para seleccionar una fecha; el CSV contiene solo el encabezado (0 filas de datos).

4. **Caso borde — campaña vacía incluye todas las campañas:**
   - Filtrar solo por fecha, dejando el selector de campaña vacío.
   - **Verificar:** La exportación incluye estados de varias campañas.

5. **Permisos:**
   - Acceder a la vista como usuario sin grupo Managers ni superuser.
   - **Verificar:** Se deniega el acceso (403/redirección).

## 📝 Notas de Despliegue

- No se requieren migraciones de base de datos.
- No se requieren cambios de configuración.
- No se rellenan valores históricos de `times_contacted`; la columna se calcula en el momento de la exportación, así que no se necesita migración de datos.

## 🎓 Decisiones de Diseño

La regla de "vacío por defecto" se aplica en la vista (`get_queryset` devuelve `.none()` sin fecha) y no en el filtro, para que `AllCampaignsContactStatusFilter` siga siendo un FilterSet simple, reutilizable y testeable. El campo persistido `times_contacted` se deja en su lugar, sin usar para lecturas, en vez de eliminarlo o rellenarlo, manteniendo el cambio de bajo riesgo y consistente con el cálculo al vuelo que ya hace la consola de vendedores.

## 🚀 Mejoras Futuras

- Considerar persistir `times_contacted` (o eliminar el campo muerto) para que no confunda a futuros lectores.
- Agregar un índice en `Activity(contact, campaign)` si los subqueries correlacionados se vuelven un cuello de botella en rangos de fecha muy amplios.

---

**Fecha:** 2026-06-19
**Autor:** Tanya Tree + Claude Opus 4.8
**Branch:** feature/export-all-campaigns-status
**Tipo de cambio:** Funcionalidad (+ Corrección)
**Módulos afectados:** Support, Core (ContactCampaignStatus, Activity)
