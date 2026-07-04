# Redefinición de Tasas en Estadísticas de Campaña y Centralización de Estados Contactados

- **Fecha:** 2026-03-26
- **Autor:** Tanya Tree + Claude Sonnet 4.6
- **Ticket:** t1071
- **Tipo:** Mejora
- **Componente:** Estadísticas de Campaña, Modelos Core, Vistas de Support
- **Impacto:** Precisión de reportes, Mantenibilidad del código

## 🎯 Resumen

Las estadísticas de campaña reportaban las tasas de "contactados" y "éxitos" contra denominadores engañosos: los contactados se dividían por el total de contactos en la campaña, y los éxitos por ese mismo total. El pedido fue redefinir los contactados como proporción de todos los contactos efectivamente llamados, y los éxitos como proporción de los contactados. Al mismo tiempo, el conjunto de estados considerados "contactados" se amplió para incluir `SWITCH_TO_MORNING` (6) y `SWITCH_TO_AFTERNOON` (7) — estados que requieren haber hablado con la persona — y se centralizó en un único helper `get_contacted_statuses()` en `core/choices.py` para que ninguna vista necesite codificar enteros de estado en duro. También se eliminaron tres métodos del modelo `Campaign` que no tenían llamadores en ninguno de los dos proyectos.

## ✨ Cambios

### 1. Centralización de la definición de estados "contactado"

**Archivo:** `core/choices.py`

Se agregó la función helper `get_contacted_statuses()` inmediatamente antes de `CAMPAIGN_RESOLUTION_CHOICES`. Devuelve los cuatro estados que requieren contacto real con la persona, expresados como miembros del enum `CAMPAIGN_STATUS` en lugar de enteros crudos:

```python
def get_contacted_statuses():
    return [
        CAMPAIGN_STATUS.CONTACTED,          # 2
        CAMPAIGN_STATUS.ENDED_WITH_CONTACT, # 4
        CAMPAIGN_STATUS.SWITCH_TO_MORNING,  # 6
        CAMPAIGN_STATUS.SWITCH_TO_AFTERNOON,# 7
    ]
```

Los estados 6 y 7 (cambiar a mañana y cambiar a tarde/noche) estaban excluidos anteriormente a pesar de representar contactos donde hubo una conversación — la persona atendió y pidió que la llamaran en otro horario. Ahora se incluyen.

### 2. Reemplazo de todos los literales de estado en las vistas de estadísticas de campaña

**Archivo:** `support/views/all_views.py`

Las seis ocurrencias de `status__in=[2, 4]` (o `(2, 4)`) en cuatro funciones fueron reemplazadas por `core_choices.get_contacted_statuses()`:

- `campaign_statistics_list` — conteo de contactados por campaña
- `CampaignStatisticsDetailView.get_context_data` — conteo de contactados y `ccs_with_resolution_contacted_count` usado para porcentajes de resolución
- `campaign_statistics_per_seller` — conteo de contactados por vendedor
- `seller_performance_by_time` — conteo de contactados para totales y el loop por vendedor

### 3. Redefinición de denominadores de tasas

**Archivo:** `support/views/all_views.py`

Se aplicaron dos cambios de denominador en todas las funciones de estadísticas:

**Tasa de contactados:** antes era `contactados / total_en_campaña`, ahora es `contactados / total_llamados` (status >= 2). Que un contacto esté en la campaña no significa que alguien haya atendido; dividir por los efectivamente llamados da una tasa de conversión con significado real.

**Tasa de éxitos:** antes era `éxitos / total_en_campaña` (o `/ asignados`), ahora es `éxitos / contactados`. Esto mide qué tan bien convierten los vendedores a los contactos con quienes efectivamente hablaron, no sobre la base cruda de la campaña.

En `CampaignStatisticsDetailView` se introdujo una variable local `called_count` para evitar una consulta adicional:

```python
called_count = filtered_qs.filter(status__gte=2).count()
context['contacted_pct'] = (context['contacted_count'] * 100) / (called_count or 1)
```

En `campaign_statistics_per_seller`, el porcentaje de éxito por vendedor ahora divide por el conteo de contactados de ese vendedor:

```python
seller.success_pct = (seller.success_count * 100) / (seller.contacted_count or 1)
```

### 4. Actualización de etiquetas en templates para reflejar la nueva semántica

**Archivos:** `support/templates/campaign_statistics_detail.html`, `support/templates/campaign_statistics_per_seller.html`

- La card "Conversión de la base" en la vista de detalle antes decía `% del total`; ahora dice `% de contactados`.
- El tooltip de la columna de porcentaje de contactados en la tabla por vendedor se actualizó a `Porcentaje contactado sobre llamados`, y el de porcentaje de suscriptos a `Porcentaje suscrito sobre contactados`.

### 5. Eliminación de métodos muertos del modelo Campaign

**Archivo:** `core/models.py`

Se eliminaron tres métodos sin llamadores en ninguno de los dos proyectos (`utopia-crm` ni `utopia-crm-ladiaria`):

- `get_activities_by_seller(seller, status, type, datetime)` — se usaba en la vista de lista de campañas de la consola de vendedores hasta febrero de 2021, cuando se simplificó el algoritmo y se eliminó la llamada.
- `get_already_contacted(seller_id)` — devolvía contactos con `status=2` únicamente; estaba muerto desde el commit inicial de la versión open source.
- `get_already_contacted_count(seller_id)` — delegaba a `get_already_contacted`; igualmente muerto.

También se eliminó el import de `get_contacted_statuses` en `models.py`, que había sido agregado únicamente para `get_already_contacted`.

## 📁 Archivos Modificados

- **`core/choices.py`** — Se agregó la función helper `get_contacted_statuses()`
- **`core/models.py`** — Se eliminaron tres métodos muertos de `Campaign`; se eliminó el import de `get_contacted_statuses` que ya no se usaba
- **`support/views/all_views.py`** — Se reemplazaron todos los `status__in=[2, 4]` con `get_contacted_statuses()`; se cambiaron los denominadores de tasas de contactados y éxitos en `campaign_statistics_list`, `CampaignStatisticsDetailView`, `campaign_statistics_per_seller` y `seller_performance_by_time`
- **`support/templates/campaign_statistics_detail.html`** — Se actualizó la etiqueta de tasa de éxito de "del total" a "de contactados"
- **`support/templates/campaign_statistics_per_seller.html`** — Se actualizaron los títulos de tooltip para las columnas de porcentaje de contactados y éxitos

## 📚 Detalles Técnicos

- Todas las guardas contra división por cero usan `(x or 1)` como denominador, consistente con el patrón existente en las vistas de estadísticas.
- `seller_performance_by_time` tuvo su conteo de contactados actualizado para usar `get_contacted_statuses()`, pero el denominador de su tasa de éxito se dejó como `assigned_count` — esa función calcula un tipo diferente de reporte (rendimiento en un rango de fechas, no un embudo de conversión de campaña) y no era parte del pedido original.
- El historial de git muestra que `get_activities_by_seller` fue llamado por última vez en el commit `36f9f01` (febrero de 2021), y que `get_already_contacted` estuvo presente pero sin llamadores desde el commit inicial público `ed3b749`.

## 🧪 Pruebas Manuales

1. **Caso exitoso — lista de estadísticas de campaña:**
   - Abrir `/support/campaign_statistics/` y seleccionar una campaña donde algunos contactos hayan sido llamados.
   - **Verificar:** El porcentaje de "Contactado" ahora es la proporción de contactados (estados 2, 4, 6, 7) sobre llamados (status >= 2), no sobre el total de la campaña. La columna "Éxito (sobre contactados)" también debe reflejar la nueva base de contactados.

2. **Caso exitoso — vista de detalle de estadísticas de campaña:**
   - Abrir la vista de detalle para cualquier campaña.
   - **Verificar:** La fila "Contactado" muestra su porcentaje relativo a los contactos llamados. La card "Conversión de la base" ahora dice `% de contactados` en lugar de `% del total`, y la cifra refleja éxitos sobre contactados, no sobre la base total de la campaña.

3. **Caso exitoso — estadísticas por vendedor:**
   - Abrir `/support/campaign_statistics_per_seller/<id>/` para una campaña con múltiples vendedores.
   - **Verificar:** La columna "%" junto a "Contactado" de cada vendedor muestra contactados/llamados, y la columna "%" junto a "Suscrito" muestra éxitos/contactados. Al pasar el cursor por esos encabezados se confirma el texto de tooltip actualizado.

4. **Caso borde — vendedor sin llamadas realizadas:**
   - Encontrar (o simular) un vendedor asignado a una campaña que aún no haya llamado a nadie (called_count = 0).
   - **Verificar:** El porcentaje de contactados se muestra como 0% sin error de división por cero. El porcentaje de éxito también se muestra como 0%.

5. **Caso borde — campaña con contactos en estado switch-to-morning o switch-to-afternoon:**
   - Encontrar un contacto cuyo `ContactCampaignStatus` tenga estado 6 o 7.
   - **Verificar:** Ese contacto ahora contribuye al conteo de contactados en todas las vistas de estadísticas, mientras que antes quedaba excluido.

## 📝 Notas de Despliegue

- No se requieren migraciones de base de datos.
- No se requieren cambios de configuración.
- El cambio afecta los porcentajes reportados en campañas existentes — los números variarán en cualquier campaña que tenga contactos en estados 6 o 7, o donde los denominadores anteriores basados en el total diferían significativamente de las bases de llamados/contactados.

## 🎓 Decisiones de Diseño

- `get_contacted_statuses()` es una función y no una constante de nivel de módulo para poder referenciar los miembros del enum `CAMPAIGN_STATUS` (definidos antes en el mismo archivo) sin depender del orden de importación. También es consistente con el patrón existente de `get_activity_types()` en el mismo módulo.
- La decisión de incluir los estados 6 y 7 como "contactado" se basa en la semántica operativa: para cambiar a un contacto a otro horario, el vendedor tuvo que haberle hablado. Por lo tanto son contactados en el sentido significativo, aunque la interacción con la campaña aún no esté finalizada.

---

- **Fecha:** 2026-03-26
- **Autor:** Tanya Tree + Claude Sonnet 4.6
- **Branch:** t1071
- **Tipo de cambio:** Mejora
- **Módulos afectados:** Estadísticas de Campaña, Modelos Core, Vistas de Support
