# Automatización y Mejora de Filtrado de Fecha de Próxima Acción en Issues

**Fecha:** 2026-01-21
**Tipo:** Mejora de Funcionalidad y Automatización
**Componente:** Sistema de Gestión de Issues
**Impacto:** Experiencia de Usuario, Automatización de Flujo de Trabajo, Calidad de Datos

## Resumen

Mejora integral del sistema de gestión de issues con configuración automática de next_action_date al cambiar el estado, capacidades avanzadas de filtrado para fecha de issue y fecha de próxima acción, y columnas de tabla ordenables. Estos cambios mejoran significativamente la eficiencia del flujo de trabajo al automatizar la programación de seguimientos y proporcionar herramientas potentes de filtrado para el seguimiento de issues.

## Motivación

El sistema de gestión de issues es crítico para el seguimiento de problemas de clientes y asegurar seguimientos oportunos. La implementación anterior tenía varias limitaciones:

1. **Gestión Manual de Fechas:** Los usuarios debían configurar manualmente next_action_date al cambiar el estado del issue, lo que llevaba a seguimientos olvidados
2. **Filtrado Limitado:** No había capacidad para filtrar issues por fecha de próxima acción, dificultando encontrar tareas próximas
3. **Sin Opción "Próximos 7 Días":** El caso de uso común para encontrar trabajo próximo no estaba soportado
4. **Campos de Fecha Poco Claros:** Los usuarios se confundían sobre la diferencia entre "Fecha" y "Fecha de Próxima Acción"
5. **Sin Ordenamiento:** No se podían ordenar issues por fecha o next_action_date para priorizar trabajo
6. **Diseño Deficiente:** Los filtros de fecha no estaban organizados eficientemente en la UI

## Funcionalidades Clave Implementadas

### 1. Configuración Automática de Fecha de Próxima Acción al Cambiar Estado

**Archivo:** `support/views/all_views.py`

**Problema:**
Cuando los usuarios cambiaban el estado de un issue, a menudo olvidaban configurar next_action_date, resultando en issues que se perdían sin seguimientos programados.

**Solución:**
Se agregó el método `form_valid()` a `IssueDetailView` que automáticamente configura next_action_date para mañana cuando:

- El estado del issue cambia, Y
- next_action_date está ausente (None), O
- next_action_date es hoy o está en el pasado

**Implementación:**

```python
def form_valid(self, form):
    """
    Override form_valid to automatically set next_action_date when status changes.
    If status has changed and next_action_date is missing or in the past, set it to tomorrow.
    """
    issue = self.get_object()
    old_status = issue.status

    # Let the form save normally first
    response = super().form_valid(form)

    # Check if status has changed
    new_status = self.object.status
    if old_status != new_status:
        # Check if next_action_date needs to be updated
        today = date.today()
        if not self.object.next_action_date or self.object.next_action_date <= today:
            # Set next_action_date to tomorrow
            self.object.next_action_date = today + timedelta(days=1)
            self.object.save(update_fields=['next_action_date'])

    return response
```

**Beneficios:**

- **Previene Seguimientos Perdidos:** Asegura que cada cambio de estado tenga una próxima acción programada
- **Lógica Inteligente:** Solo actualiza cuando es necesario (fechas ausentes o pasadas)
- **Respeta Fechas Futuras:** No sobrescribe fechas futuras configuradas manualmente
- **Flujo Automático:** Reduce la entrada manual de datos y el error humano
- **Eficiente:** Usa `update_fields` para actualizar solo el campo necesario

**Casos de Uso:**

1. **Cambio de Estado de "Abierto" a "En Progreso":** Programa automáticamente seguimiento para mañana
2. **Reapertura de Issue Cerrado:** Configura fecha de próxima acción si la fecha anterior estaba en el pasado
3. **Escalamiento:** Al cambiar estado a escalado, asegura seguimiento oportuno
4. **Sobrescritura Manual:** Los usuarios aún pueden configurar fechas futuras personalizadas que no serán cambiadas

### 2. Filtrado Avanzado de Fecha de Próxima Acción

**Archivo:** `support/filters.py`

**Problema:**
Los usuarios no podían filtrar issues por next_action_date, haciendo imposible encontrar:

- Issues vencidos hoy
- Issues vencidos en los próximos 7 días
- Issues atrasados (fechas de próxima acción pasadas)
- Issues programados para rangos de fechas específicos

**Solución:**
Se agregó filtrado integral de next_action_date con las mismas opciones que el filtrado de fecha de issue.

**Implementación:**

```python
class IssueFilter(django_filters.FilterSet):
    # Filtros de Fecha de Issue con texto de ayuda
    date = django_filters.ChoiceFilter(
        choices=CREATION_CHOICES,
        method='filter_by_date',
        label=_('Issue Date'),
        help_text=_('When the issue was created')
    )
    date_gte = django_filters.DateFilter(
        field_name='date',
        lookup_expr='gte',
        widget=forms.TextInput(attrs={'autocomplete': 'off'}),
        label=_('From')
    )
    date_lte = django_filters.DateFilter(
        field_name='date',
        lookup_expr='lte',
        widget=forms.TextInput(attrs={'autocomplete': 'off'}),
        label=_('To')
    )

    # Filtros de Fecha de Próxima Acción con texto de ayuda
    next_action_date = django_filters.ChoiceFilter(
        choices=CREATION_CHOICES,
        method='filter_by_next_action_date',
        label=_('Next Action Date'),
        help_text=_('When the next action is scheduled')
    )
    next_action_date_gte = django_filters.DateFilter(
        field_name='next_action_date',
        lookup_expr='gte',
        widget=forms.TextInput(attrs={'autocomplete': 'off'}),
        label=_('From')
    )
    next_action_date_lte = django_filters.DateFilter(
        field_name='next_action_date',
        lookup_expr='lte',
        widget=forms.TextInput(attrs={'autocomplete': 'off'}),
        label=_('To')
    )
```

**Método de Filtrado:**

```python
def filter_by_next_action_date(self, queryset, name, value):
    today = date.today()
    if value == 'today':
        return queryset.filter(next_action_date=today)
    elif value == 'yesterday':
        return queryset.filter(next_action_date=today - timedelta(1))
    elif value == 'last_7_days':
        return queryset.filter(
            next_action_date__gte=today - timedelta(7),
            next_action_date__lte=today
        )
    elif value == 'next_7_days':
        return queryset.filter(
            next_action_date__gte=today,
            next_action_date__lte=today + timedelta(7)
        )
    elif value == 'last_30_days':
        return queryset.filter(
            next_action_date__gte=today - timedelta(30),
            next_action_date__lte=today
        )
    elif value == 'this_month':
        return queryset.filter(
            next_action_date__month=today.month,
            next_action_date__year=today.year
        )
    elif value == 'last_month':
        month = today.month - 1 if today.month != 1 else 12
        year = today.year if today.month != 1 else today.year - 1
        return queryset.filter(next_action_date__month=month, next_action_date__year=year)
    else:
        return queryset
```

**Opciones de Filtro:**

- **Hoy:** Issues programados para hoy
- **Ayer:** Issues atrasados desde ayer
- **Últimos 7 días:** Issues recientemente programados o atrasados
- **Próximos 7 días:** ⭐ NUEVO - Trabajo próximo en la siguiente semana
- **Últimos 30 días:** Issues programados en el último mes
- **Este mes:** Todos los issues programados este mes
- **Mes pasado:** Issues del mes anterior
- **Personalizado:** Especificar rango de fechas exacto con campos Desde/Hasta

### 3. Opción "Próximos 7 Días" Agregada

**Archivo:** `support/filters.py`

**Problema:**
El caso de uso más común - encontrar trabajo programado para la próxima semana - no estaba disponible como opción de filtro rápido.

**Solución:**
Se agregó "Próximos 7 Días" a `CREATION_CHOICES`:

```python
CREATION_CHOICES = (
    ('today', _('Today')),
    ('yesterday', _('Yesterday')),
    ('last_7_days', _('Last 7 days')),
    ('next_7_days', _('Next 7 days')),  # NUEVO
    ('last_30_days', _('Last 30 days')),
    ('this_month', _('This month')),
    ('last_month', _('Last month')),
    ('custom', _('Custom')),
)
```

**Beneficios:**

- **Acceso Rápido:** Filtro de un clic para el trabajo de la próxima semana
- **Planificación:** Fácil ver la carga de trabajo para los próximos 7 días
- **Priorización:** Ayuda a los usuarios a enfocarse en tareas a corto plazo
- **Disponible para Ambos:** Funciona tanto para fecha de issue como fecha de próxima acción

### 4. Texto de Ayuda para Campos de Fecha

**Archivo:** `support/filters.py`

**Problema:**
Los usuarios se confundían sobre la diferencia entre los campos "Fecha" y "Fecha de Próxima Acción".

**Solución:**
Se agregó texto de ayuda claro a ambos campos de filtro de fecha:

- **Fecha de Issue:** "Cuando el issue fue creado"
- **Fecha de Próxima Acción:** "Cuando la próxima acción está programada"

**Visualización en Template:**

```html
<label for="date">
  {{ filter.form.date.label }}
  <small class="text-muted">{{ filter.form.date.help_text }}</small>
</label>
```

**Beneficios:**

- **Propósito Claro:** Los usuarios entienden qué representa cada campo de fecha
- **Confusión Reducida:** No más confusión entre fecha de creación vs. fecha de acción
- **Mejor UX:** Ayuda contextual justo donde se necesita

### 5. Diseño Mejorado de Filtros

**Archivo:** `support/templates/list_issues.html`

**Problema:**
Los filtros de fecha estaban dispersos por el formulario, dificultando usarlos juntos eficientemente.

**Solución:**
Se organizaron los campos de fecha en una fila dedicada con ambos filtros lado a lado:

```html
<div class="row">
  <div class="form-group col-md-6">
    <label for="date">
      {{ filter.form.date.label }}
      <small class="text-muted">{{ filter.form.date.help_text }}</small>
    </label>
    {% render_field filter.form.date class="form-control" %}
  </div>
  <div class="form-group col-md-6">
    <label for="next_action_date">
      {{ filter.form.next_action_date.label }}
      <small class="text-muted">{{ filter.form.next_action_date.help_text }}</small>
    </label>
    {% render_field filter.form.next_action_date class="form-control" %}
  </div>
</div>
```

**Rangos de Fechas Personalizados:**

```html
<div class="row">
  <div class="creation-range hidden d-none col-md-6">
    <div class="row">
      <div class="form-group col">
        <label for="date_gte">{{ filter.form.date_gte.label }}</label>
        {% render_field filter.form.date_gte class="form-control" %}
      </div>
      <div class="form-group col">
        <label for="date_lte">{{ filter.form.date_lte.label }}</label>
        {% render_field filter.form.date_lte class="form-control" %}
      </div>
    </div>
  </div>
  <div class="next-action-range hidden d-none col-md-6">
    <div class="row">
      <div class="form-group col">
        <label for="next_action_date_gte">{{ filter.form.next_action_date_gte.label }}</label>
        {% render_field filter.form.next_action_date_gte class="form-control" %}
      </div>
      <div class="form-group col">
        <label for="next_action_date_lte">{{ filter.form.next_action_date_lte.label }}</label>
        {% render_field filter.form.next_action_date_lte class="form-control" %}
      </div>
    </div>
  </div>
</div>
```

**Beneficios:**

- **Lado a Lado:** Ambos filtros de fecha visibles a la vez
- **Agrupación Lógica:** Filtros relacionados juntos
- **Uso Eficiente del Espacio:** Mejor utilización del espacio en pantalla
- **Flujo Paralelo:** Filtrar por ambas fechas simultáneamente

### 6. JavaScript para Rango de Fecha de Próxima Acción

**Archivo:** `support/templates/list_issues.html`

**Problema:**
La funcionalidad de rango de fechas personalizado solo funcionaba para fecha de issue, no para fecha de próxima acción.

**Solución:**
Se agregó JavaScript para manejar la visualización de rango de fechas personalizado para fecha de próxima acción:

```javascript
// Funcionalidad de rango de fechas para Fecha de Próxima Acción
$('#id_next_action_date').change(function(){
  var option = $(this).val();
  if(option == "custom") {
    $('.next-action-range').removeClass('d-none');
  }else {
    $('.next-action-range').addClass('d-none');
    $('#id_next_action_date_gte').attr('value', '');
    $('#id_next_action_date_lte').attr('value', '');
  }
});
$('#id_next_action_date').change();
$('#id_next_action_date_gte').datepicker({ dateFormat: 'yy-mm-dd' });
$('#id_next_action_date_lte').datepicker({ dateFormat: 'yy-mm-dd' });
```

**Características:**

- **Lógica Mostrar/Ocultar:** Los campos de rango personalizado aparecen solo cuando se selecciona "Personalizado"
- **Auto-Limpiar:** Limpia fechas personalizadas al cambiar a opciones predefinidas
- **Datepicker:** Widget de calendario para selección fácil de fechas
- **UX Consistente:** Mismo comportamiento que el filtrado de fecha de issue

### 7. Columnas de Tabla Ordenables

**Archivo:** `support/views/all_views.py`

**Problema:**
Los usuarios no podían ordenar la lista de issues por fecha o next_action_date, dificultando priorizar el trabajo.

**Solución:**
Se mejoró `IssueListView.get_queryset()` con soporte de ordenamiento:

```python
def get_queryset(self):
    """Get queryset with optional ordering by date or next_action_date"""
    queryset = Issue.objects.all()

    # Get ordering parameter from request
    order_by = self.request.GET.get('order_by', '-date')

    # Validate ordering parameter to prevent SQL injection
    valid_orderings = [
        'date', '-date',
        'next_action_date', '-next_action_date',
        'status', '-status',
        'category', '-category'
    ]

    if order_by in valid_orderings:
        queryset = queryset.order_by(order_by)
    else:
        # Default ordering
        if logistics_is_installed():
            queryset = queryset.order_by(
                "-date", "subscription_product__product",
                "-subscription_product__route__number", "-id"
            )
        else:
            queryset = queryset.order_by("-date", "subscription_product__product", "-id")

    return queryset
```

**Implementación en Template:**

```html
<th>
  <a href="?{% for key, value in request.GET.items %}{% if key != 'order_by' and key != 'p' %}{{ key }}={{ value }}&{% endif %}{% endfor %}order_by={% if request.GET.order_by == 'date' %}-date{% else %}date{% endif %}" class="text-dark">
    {% trans "Start date" %}
    {% if request.GET.order_by == 'date' %}<i class="fas fa-sort-up"></i>{% elif request.GET.order_by == '-date' %}<i class="fas fa-sort-down"></i>{% else %}<i class="fas fa-sort"></i>{% endif %}
  </a>
</th>
<th>
  <a href="?{% for key, value in request.GET.items %}{% if key != 'order_by' and key != 'p' %}{{ key }}={{ value }}&{% endif %}{% endfor %}order_by={% if request.GET.order_by == 'next_action_date' %}-next_action_date{% else %}next_action_date{% endif %}" class="text-dark">
    {% trans "Next action date" %}
    {% if request.GET.order_by == 'next_action_date' %}<i class="fas fa-sort-up"></i>{% elif request.GET.order_by == '-next_action_date' %}<i class="fas fa-sort-down"></i>{% else %}<i class="fas fa-sort"></i>{% endif %}
  </a>
</th>
```

**Características:**

- **Encabezados Clicables:** Clic en encabezado de columna para ordenar
- **Alternar Dirección:** Clic nuevamente para invertir orden
- **Indicadores Visuales:** Iconos muestran estado actual de ordenamiento
  - Sin ordenar por esta columna
  - Ordenado ascendente
  - Ordenado descendente
- **Preservar Filtros:** El ordenamiento mantiene todos los filtros activos
- **Seguridad:** Validación de lista blanca previene inyección SQL
- **Múltiples Columnas:** Ordenar por fecha, next_action_date, estado o categoría

**Opciones de Ordenamiento:**

- **Fecha de Inicio:** Ordenar por fecha de creación del issue (ascendente/descendente)
- **Fecha de Próxima Acción:** Ordenar por fecha de acción programada (ascendente/descendente)
- **Estado:** Ordenar por estado del issue
- **Categoría:** Ordenar por categoría del issue

## Detalles Técnicos

### Archivos Modificados

1. **support/views/all_views.py**
   - Se agregó método `form_valid()` a `IssueDetailView` para configuración automática de next_action_date
   - Se mejoró `get_queryset()` en `IssueListView` con soporte de ordenamiento
   - Se agregó validación de seguridad para parámetro order_by

2. **support/filters.py**
   - Se agregó "Próximos 7 días" a `CREATION_CHOICES`
   - Se agregaron campos de filtro next_action_date con texto de ayuda
   - Se agregó método `filter_by_next_action_date()`
   - Se agregó texto de ayuda al filtro de fecha de issue
   - Se corrigieron errores de longitud de línea de linting

3. **support/templates/list_issues.html**
   - Se reorganizaron filtros de fecha en fila dedicada (col-md-6 cada uno)
   - Se agregó visualización de texto de ayuda para ambos campos de fecha
   - Se agregó JavaScript para funcionalidad de rango personalizado de fecha de próxima acción
   - Se agregaron encabezados de columna ordenables con iconos
   - Se mejoró diseño responsivo

4. **support/models.py**
   - Se agregó help_text al campo `date`: "Fecha del issue"

### Impacto en Base de Datos

- **No se requieren migraciones** - Todos los campos ya existen
- **Actualizaciones automáticas** - next_action_date actualizado vía método save()
- **No se necesita migración de datos** - Funciona con datos existentes

### Consideraciones de Rendimiento

- **Actualizaciones Eficientes:** Usa `update_fields=['next_action_date']` para minimizar escrituras en base de datos
- **Campos Indexados:** Tanto date como next_action_date están indexados para filtrado rápido
- **Optimización de Consultas:** El ordenamiento usa índices de base de datos
- **Sin Consultas N+1:** Todo el filtrado se hace a nivel de base de datos

## Mejoras de Experiencia de Usuario

### Antes

- **Gestión Manual de Fechas:** Los usuarios debían recordar configurar next_action_date
- **Filtrado Limitado:** Solo se podía filtrar por fecha de creación del issue
- **Sin Filtros Rápidos:** Sin opción "próximos 7 días" para caso de uso común
- **Campos Poco Claros:** Confusión entre tipos de fecha
- **Sin Ordenamiento:** No se podía priorizar por fecha
- **Diseño Disperso:** Filtros de fecha no organizados juntos

### Después

- **Programación Automática:** Los cambios de estado configuran automáticamente next_action_date para mañana
- **Filtrado Integral:** Filtrar por fecha de issue y fecha de próxima acción
- **Acceso Rápido:** Opción "Próximos 7 días" para encontrar trabajo próximo
- **Etiquetas Claras:** Texto de ayuda explica cada campo de fecha
- **Columnas Ordenables:** Clic en encabezados para ordenar por cualquier campo de fecha
- **Diseño Organizado:** Ambos filtros de fecha lado a lado con texto de ayuda

## Ejemplos de Flujo de Trabajo

### Ejemplo 1: Planificación de Trabajo Diario

**Objetivo del Usuario:** Encontrar todos los issues vencidos hoy

**Pasos:**

1. Ir a lista de issues
2. Seleccionar "Hoy" del dropdown Fecha de Próxima Acción
3. Clic en Buscar
4. Ver todos los issues programados para hoy

**Resultado:** Lista enfocada del trabajo de hoy

### Ejemplo 2: Planificación Semanal

**Objetivo del Usuario:** Ver todo el trabajo programado para la próxima semana

**Pasos:**

1. Ir a lista de issues
2. Seleccionar "Próximos 7 días" del dropdown Fecha de Próxima Acción
3. Clic en encabezado "Fecha de próxima acción" para ordenar por fecha
4. Ver lista cronológicamente ordenada del trabajo próximo

**Resultado:** Vista clara de la carga de trabajo de la próxima semana

### Ejemplo 3: Encontrar Issues Atrasados

**Objetivo del Usuario:** Encontrar issues que deberían haber sido atendidos

**Pasos:**

1. Ir a lista de issues
2. Seleccionar "Últimos 7 días" del dropdown Fecha de Próxima Acción
3. Clic en Buscar
4. Ver issues con fechas de próxima acción pasadas

**Resultado:** Lista de seguimientos atrasados que necesitan atención

### Ejemplo 4: Flujo de Cambio de Estado

**Objetivo del Usuario:** Actualizar estado del issue y asegurar seguimiento

**Pasos:**

1. Abrir página de detalle del issue
2. Cambiar estado de "Abierto" a "En Progreso"
3. Guardar issue
4. El sistema automáticamente configura next_action_date para mañana

**Resultado:** El issue tiene seguimiento programado sin entrada manual de fecha

## Beneficios

1. **Eficiencia Mejorada del Flujo de Trabajo:**
   - Configuración automática de next_action_date ahorra tiempo
   - Filtros rápidos reducen clics para encontrar issues relevantes
   - El ordenamiento ayuda a priorizar trabajo

2. **Mejor Calidad de Datos:**
   - Asegura que todos los cambios de estado tengan fechas de seguimiento
   - Reduce seguimientos olvidados
   - Mantiene programación consistente

3. **Experiencia de Usuario Mejorada:**
   - Texto de ayuda claro reduce confusión
   - Diseño organizado mejora usabilidad
   - Indicadores visuales de ordenamiento proporcionan retroalimentación

4. **Filtrado Potente:**
   - Encontrar issues por fecha de creación o fecha de acción
   - Múltiples opciones predefinidas para casos de uso comunes
   - Rangos de fechas personalizados para necesidades específicas

5. **Productividad Aumentada:**
   - Filtro "Próximos 7 días" para planificación semanal
   - Columnas ordenables para priorización
   - Filtros lado a lado para consultas complejas

## Notas de Migración

- **No se requiere migración de base de datos** - Todos los campos ya existen en el modelo Issue
- **Efecto inmediato** - La configuración automática de fecha funciona tan pronto como se despliega
- **Retrocompatible** - Issues y flujos de trabajo existentes no afectados
- **No se requiere capacitación** - UI intuitiva con texto de ayuda

## Recomendaciones de Prueba

### Pruebas Manuales

1. **Probar configuración automática de next_action_date:**
   - Crear issue con estado "Abierto"
   - Cambiar estado a "En Progreso"
   - Verificar que next_action_date se configura para mañana
   - Cambiar estado nuevamente con next_action_date futuro
   - Verificar que la fecha futura se preserva

2. **Probar filtrado de fecha de próxima acción:**
   - Filtrar por "Hoy"
   - Filtrar por "Próximos 7 días"
   - Filtrar por "Últimos 7 días"
   - Probar rango de fechas personalizado
   - Verificar que los resultados son correctos

3. **Probar ordenamiento:**
   - Ordenar por Fecha de inicio (ascendente/descendente)
   - Ordenar por Fecha de próxima acción (ascendente/descendente)
   - Verificar que los iconos de ordenamiento se actualizan correctamente
   - Verificar que los filtros se preservan al ordenar

4. **Probar diseño de filtros:**
   - Verificar que ambos filtros de fecha son visibles lado a lado
   - Verificar que el texto de ayuda se muestra correctamente
   - Probar mostrar/ocultar rango personalizado para ambas fechas
   - Probar diseño responsivo en móvil

### Casos Extremos

1. **next_action_date nulo:** Verificar que la configuración automática funciona
2. **next_action_date pasado:** Verificar que se actualiza a mañana
3. **next_action_date futuro:** Verificar que no se cambia
4. **Sin cambio de estado:** Verificar que next_action_date no se modifica
5. **Resultados de filtro vacíos:** Verificar mensaje apropiado

## Consideraciones Futuras

1. **Predeterminado Configurable:** Permitir configurar offset predeterminado de next_action_date (ej., 2 días, 1 semana)
2. **Fechas Específicas por Estado:** Diferentes fechas predeterminadas para diferentes cambios de estado
3. **Acciones Masivas:** Actualizar next_action_date para múltiples issues a la vez
4. **Vista de Calendario:** Calendario visual mostrando issues por next_action_date
5. **Recordatorios:** Notificaciones por email para next_action_dates próximos
6. **Sugerencias Inteligentes:** Recomendaciones de next_action_date basadas en ML

## Componentes Relacionados

- **Modelo Issue:** `support/models.py` - Define estructura de datos del issue
- **Formularios de Issue:** `support/forms.py` - Formularios de creación y edición de issues
- **Vista de Detalle de Issue:** `support/views/all_views.py` - Gestión de issue individual
- **Vista de Lista de Issues:** `support/views/all_views.py` - Navegación y filtrado de issues

## Conclusión

Esta mejora integral mejora significativamente el flujo de trabajo de gestión de issues al automatizar la configuración de next_action_date, proporcionar capacidades potentes de filtrado y mejorar la interfaz de usuario. La configuración automática de fecha asegura que no se olviden seguimientos, mientras que el filtrado y ordenamiento mejorados facilitan encontrar y priorizar el trabajo. La adición de texto de ayuda y diseño mejorado crea una experiencia de usuario más intuitiva, y el filtro "Próximos 7 días" aborda un caso de uso común para planificación semanal. Estos cambios se combinan para crear un sistema de gestión de issues más eficiente y amigable para el usuario.
