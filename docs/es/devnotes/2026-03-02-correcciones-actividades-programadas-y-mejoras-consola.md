# Consola de Vendedor: Correcciones de Actividades Programadas y Mejoras en Página de Actividades

**Fecha:** 2026-03-02
**Tipo:** Corrección de Errores, Mejora de Funcionalidad, Mejora de UI
**Componente:** Consola de Vendedor, Página de Actividades Programadas
**Impacto:** Flujo de Trabajo del Vendedor, Gestión de Campañas, Experiencia de Usuario
**Tarea:** t1037

## Resumen

Esta actualización corrige tres errores en el modo "act" (actividades programadas) de la consola de vendedor y mejora significativamente la página de Actividades Programadas con mejor filtrado, retroalimentación visual e integración de Select2. También agrega el ordenamiento correcto de contactos en modo "new" por fecha de asignación.

## Correcciones de Errores

### 1. `seller_console_action` No Se Guardaba en la Actividad en Modo "act"

**Archivo:** `support/views/seller_console.py`

**Problema:** Al procesar una actividad programada en modo "act", la actividad existente se actualizaba con notas, estado y fecha, pero el campo `seller_console_action` nunca se establecía. Esto significaba que la acción realizada por el vendedor no quedaba registrada en la actividad.

**Causa raíz:** El método `handle_post_request` actualizaba los campos de la actividad pero omitía establecer `activity.seller_console_action = seller_console_action` antes de llamar a `activity.save()`.

**Corrección:** Se agregó `activity.seller_console_action = seller_console_action` al bloque de actualización de actividad en modo "act".

### 2. Cuadro de Notas Pre-llenado con Mensaje de Programación

**Archivo:** `support/templates/seller_console.html`

**Problema:** Cuando un vendedor abría una actividad programada en la consola, el cuadro de notas venía pre-llenado con el mensaje de programación (ej: "Agendado para 2026-03-05 10:00"), obligando al vendedor a borrarlo manualmente.

**Causa raíz:** La plantilla tenía un condicional que pre-llenaba el textarea con `{{ console_instance.notes }}` en modo "act".

**Corrección:** Se eliminó el condicional — el textarea ahora siempre está vacío para que el vendedor escriba notas nuevas para cada acción.

### 3. "No Encontrado" / "Llamar más tarde" Eliminaba Contacto de la Cola "act"

**Archivo:** `support/views/seller_console.py`

**Problema:** Al hacer clic en "No encontrado" o "Llamar más tarde" en modo "act", el contacto desaparecía de la cola de actividades programadas y caía a la sección "new".

**Causa raíz:** El flujo era:

1. La actividad pendiente existente se marcaba como COMPLETADA
2. `process_activity_result` establecía `ccs.status = 3` (CALLED_COULD_NOT_CONTACT)
3. No se creaba una nueva actividad pendiente (solo ocurría cuando `KEEP_CONTACTS_IN_CAMPAIGNS_INDEFINITELY` estaba habilitado)
4. Sin actividad pendiente, el contacto caía fuera de la cola "act" (que filtra `status="P"`)
5. Con `ccs.status = 3`, el contacto aparecía en la cola "new" (`get_not_contacted` filtra `status__in=[1, 3]`)

**Corrección:** Dos cambios:

- En `handle_post_request`: CALL_LATER y NOT_FOUND en modo "act" ahora siempre llaman a `register_new_activity`, independientemente de la configuración `KEEP_CONTACTS_IN_CAMPAIGNS_INDEFINITELY`.
- En `register_new_activity`: Se agregó un camino de retorno anticipado para CALL_LATER/NOT_FOUND en modo "act" que siempre crea una nueva actividad pendiente usando la configuración `SELLER_CONSOLE_CALL_LATER_DAYS` (por defecto: 1 día), manteniendo al contacto en la cola "act".

## Mejoras de Funcionalidad

### 4. Contactos con Colores en Modo "act"

**Archivos:** `support/views/seller_console.py`, `support/templates/seller_console.html`

**Problema:** Las tarjetas de contacto con colores (naranja para "No encontrado", azul para "Llamar más tarde") y la insignia en el encabezado con fecha/hora de la acción solo funcionaban en modo "new" porque dependían de `ContactCampaignStatus.last_console_action`, que no existe en objetos `Activity`.

**Solución:**

- **Plantilla:** Se usó el filtro `|default` de Django para verificar ambos campos: `{% with action=instance.last_console_action|default:instance.seller_console_action %}`.
- **Vista:** Se agregó `select_related('seller_console_action')` a ambos querysets del modo "act" para prevenir consultas N+1.
- **Vista:** Se actualizó la lógica de `last_action_datetime` para usar `getattr` con fallback, verificando tanto `last_console_action` como `seller_console_action`.

### 5. Ordenamiento de Contactos por Fecha de Asignación en Modo "new"

**Archivo:** `core/models.py`

**Problema:** Los contactos en modo "new" no tenían ordenamiento explícito, cayendo al default `Meta.ordering = ["id"]`. Esto significaba que contactos asignados después podían aparecer antes que los asignados anteriormente.

**Solución:** Se agregó ordenamiento explícito a `get_not_contacted()`:

```python
.order_by(F('date_assigned').asc(nulls_last=True), 'contact__id')
```

Esto asegura:

1. **`date_assigned` ascendente** — contactos asignados primero aparecen primero
2. **`contact__id` ascendente** — desempate por fecha igual (contactos más antiguos primero)
3. **Nulos al final** — contactos sin fecha de asignación van al final

### 6. Renovación de la Página de Actividades Programadas

**Archivos:** `support/filters.py`, `support/views/activities.py`, `support/templates/scheduled_activities.html`

#### 6a. Solo Campañas Activas en el Filtro

El desplegable de campañas ahora solo muestra campañas activas, ordenadas por nombre:

```python
campaign = django_filters.ModelChoiceFilter(
    queryset=Campaign.objects.filter(active=True).order_by('name'),
)
```

#### 6b. Integración de Select2

Los tres desplegables de filtro (Estado, Campaña, Acción de Consola) ahora usan Select2 con tema Bootstrap 4, proporcionando búsqueda y funcionalidad de limpiar.

#### 6c. Colores Pastel en las Filas

Las actividades ahora tienen colores según su fecha relativa a hoy:

- **Rojo pastel** (`#fce4e4`) — actividades vencidas (fecha < hoy)
- **Amarillo pastel** (`#fff9e6`) — actividades de hoy
- **Azul pastel** (`#e8f4fd`) — actividades futuras

Se muestra una leyenda de colores en el encabezado de la tabla. Se eliminó la clase `table-striped` para que los colores pastel se vean correctamente.

#### 6d. Botones de Rango de Fechas Predefinidos

Seis botones de rango de fechas reemplazan la entrada manual para casos de uso comunes:

| Botón | Filtro | Color |
| ------- | -------- | ------- |
| Pasado (vencido) | `datetime < hoy` | Peligro (rojo) |
| Hoy | `datetime = hoy` | Advertencia (amarillo) |
| Futuro | `datetime > hoy` | Info (azul) |
| Pasado + Hoy | `datetime <= hoy` | Secundario (gris) |
| Hoy + Futuro | `datetime >= hoy` | Primario (azul) |
| Personalizado | Muestra campos date_from/date_to | Oscuro |

**Comportamiento:**

- Los presets no-personalizados envían el formulario automáticamente al hacer clic
- Los botones son alternables (clic de nuevo para deseleccionar y enviar)
- "Personalizado" abre los campos date_from/date_to con animación deslizante; requiere clic manual en Buscar
- El estado activo persiste después del envío del formulario

#### 6e. Separación Visual de Secciones de Fechas

Se agregó un separador `<hr>` y se cambió el ícono de `fa-calendar-alt` a `fa-file-contract` para los campos de fecha de fin de suscripción, haciéndolos visualmente distintos de los filtros de fecha de actividad.

## Detalles Técnicos

### Archivos Modificados

1. **`support/views/seller_console.py`**
   - Corrección: `seller_console_action` ahora se guarda en la actividad en modo "act"
   - Corrección: CALL_LATER/NOT_FOUND en modo "act" siempre crea nueva actividad pendiente
   - Agregado: `select_related('seller_console_action')` en querysets modo "act"
   - Actualizado: Lógica de `last_action_datetime` maneja ambos modos "new" y "act"

2. **`support/templates/seller_console.html`**
   - Corrección: Textarea de notas siempre vacío
   - Actualizado: Colores de tarjetas usan `|default` para verificar ambos campos
   - Actualizado: Insignia del encabezado usa mismo patrón `|default`

3. **`core/models.py`**
   - Agregado: Import de `F` para expresiones de ordenamiento
   - Agregado: `.order_by(F('date_assigned').asc(nulls_last=True), 'contact__id')` en `get_not_contacted()`

4. **`support/filters.py`**
   - Agregado: Tupla `ACTIVITY_DATE_CHOICES` con 6 opciones predefinidas
   - Agregado: `date_range` ChoiceFilter con widget HiddenInput y método `filter_by_date_range`
   - Agregado: Filtros `date_from` y `date_to` para rangos personalizados
   - Actualizado: Queryset de filtro de campaña solo campañas activas

5. **`support/views/activities.py`**
   - Agregado: Import de `date`
   - Agregado: `today` al contexto para comparación de colores de filas

6. **`support/templates/scheduled_activities.html`**
   - Agregado: Includes de CSS/JS de Select2
   - Agregado: Clases CSS de colores pastel (`.row-overdue`, `.row-today`, `.row-future`)
   - Agregado: Grupo de botones de rango de fechas con auto-envío
   - Agregado: Campos de fecha personalizada (ocultos por defecto)
   - Agregado: Leyenda de colores en encabezado de tabla
   - Agregado: Separador `<hr>` e ícono distinto para campos de fecha de suscripción
   - Agregado: JavaScript de inicialización Select2
   - Eliminado: `table-striped` para permitir colores pastel

### Impacto en Base de Datos

- **No se requieren migraciones** — todos los cambios son a nivel de vista/plantilla/filtro
- El ordenamiento `F('date_assigned')` usa un campo indexado existente
