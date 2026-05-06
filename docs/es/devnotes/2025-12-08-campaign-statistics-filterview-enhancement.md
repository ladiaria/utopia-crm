# Modernización de Vista de Estadísticas de Campaña y Mejora de Filtros

**Fecha:** 2025-12-08
**Tipo:** Mejora de Funcionalidad, Modernización de Código
**Componente:** Gestión de Campañas, Estadísticas
**Impacto:** Flujo de Trabajo de Gerentes, Análisis de Campañas
**Tarea:** t981

## Resumen

Se convirtió la vista basada en función `campaign_statistics_detail` a una vista moderna basada en clases `CampaignStatisticsDetailView` tipo FilterView con capacidades de filtrado mejoradas. Se agregaron filtros de rango de fechas para asignación de contactos y fechas de última acción, se mejoró el diseño de la interfaz de filtros y se implementó navegación con breadcrumbs y control de acceso apropiado.

## Motivación

La vista existente de detalle de estadísticas de campaña tenía varias limitaciones:

1. **Arquitectura basada en funciones:** Usaba patrones antiguos de Django en lugar de vistas modernas basadas en clases
2. **Filtrado limitado:** Solo soportaba filtrado por vendedor, faltaban capacidades de filtrado basadas en fechas
3. **UX de filtros pobre:** Formulario de filtro simple de un solo campo sin organización clara
4. **Sin breadcrumbs:** Faltaba contexto de navegación para los usuarios
5. **Patrones inconsistentes:** No seguía el patrón FilterView usado en otras vistas modernizadas

Los gerentes necesitaban mejores herramientas para analizar el rendimiento de campañas en períodos de tiempo específicos y rastrear cuándo se asignaron contactos y cuándo fueron contactados por última vez.

## Implementación

### 1. Filtro Mejorado: `ContactCampaignStatusFilter`

**Archivo:** `support/filters.py`

Se agregaron cuatro nuevos filtros de rango de fechas al filtro existente:

```python
class ContactCampaignStatusFilter(django_filters.FilterSet):
    seller = django_filters.ModelChoiceFilter(queryset=Seller.objects.filter(internal=True))
    date_assigned_min = django_filters.DateFilter(
        field_name='date_assigned',
        lookup_expr='gte',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    date_assigned_max = django_filters.DateFilter(
        field_name='date_assigned',
        lookup_expr='lte',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    last_action_date_min = django_filters.DateFilter(
        field_name='last_action_date',
        lookup_expr='gte',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    last_action_date_max = django_filters.DateFilter(
        field_name='last_action_date',
        lookup_expr='lte',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    class Meta:
        model = ContactCampaignStatus
        fields = ["seller", "status"]
```

**Características:**

- Tipo de entrada HTML5 date para selectores de fecha nativos
- Filtrado de rango min/max para ambos campos de fecha
- Estilo form-control apropiado para integración con Bootstrap

### 2. Conversión a FilterView: `CampaignStatisticsDetailView`

**Archivo:** `support/views/all_views.py`

Se convirtió de vista basada en función a FilterView moderna basada en clases:

```python
class CampaignStatisticsDetailView(BreadcrumbsMixin, UserPassesTestMixin, FilterView):
    """
    Muestra estadísticas detalladas para una campaña específica con capacidades de filtrado.

    Usa FilterView para filtrar registros de ContactCampaignStatus para la campaña,
    permitiendo filtrado por vendedor, estado, date_assigned y last_action_date.
    """
    model = ContactCampaignStatus
    filterset_class = ContactCampaignStatusFilter
    template_name = "campaign_statistics_detail.html"
    context_object_name = "contact_campaign_statuses"

    def breadcrumbs(self):
        return [
            {"label": _("Home"), "url": reverse("home")},
            {"label": _("Campaigns"), "url": reverse("campaign_statistics_list")},
            {"label": self.campaign.name, "url": "campaign_statistics_detail"},
        ]

    def test_func(self):
        """Solo usuarios en el grupo Managers pueden acceder a esta vista o superusuarios."""
        return self.request.user.groups.filter(name='Managers').exists() or self.request.user.is_superuser

    def get_queryset(self):
        """Obtiene registros de ContactCampaignStatus para esta campaña."""
        self.campaign = get_object_or_404(Campaign, pk=self.kwargs['campaign_id'])
        return self.campaign.contactcampaignstatus_set.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # ... todos los cálculos de estadísticas preservados ...
        return context
```

**Beneficios de Arquitectura:**

- **FilterView:** Ajuste perfecto para filtrar registros de ContactCampaignStatus
- **BreadcrumbsMixin:** Proporciona contexto de navegación
- **UserPassesTestMixin:** Restringe acceso al grupo Managers y superusuarios
- **Separación limpia:** Lógica de estadísticas en `get_context_data()`, filtrado manejado por FilterView
- **Compatibilidad hacia atrás:** Mantenida vía `campaign_statistics_detail = CampaignStatisticsDetailView.as_view()`

**Funcionalidad Preservada:**

- Todos los cálculos de estadísticas existentes (conteos de estado, estadísticas de resolución, tasas de éxito)
- Filtrado específico por vendedor y seguimiento de ventas de productos
- Análisis de razones de rechazo
- Cálculos de porcentajes para todas las métricas

### 3. Interfaz de Template Mejorada

**Archivo:** `support/templates/campaign_statistics_detail.html`

Se rediseñó completamente el formulario de filtros con diseño mejorado y mejor experiencia de usuario:

**Antes:**

```html
<form method="GET" id="form">
  <div class="row">
    <div class="form-group col">
      <label for="status">{% trans "Filter by seller" %}</label>
      {% render_field filter.form.seller class="form-control" %}
    </div>
  </div>
  <div class="row">
    <div class="text-right">
      {{filtered_count}} {% trans "contacts" %}
      <input type="submit" class="btn bg-gradient-primary ml-3" value="Filtrar" />
    </div>
  </div>
</form>
```

**Después:**

```html
<form method="get" id="form">
  <!-- Fila 1: Filtros de Vendedor y Estado -->
  <div class="row">
    <div class="form-group col-md-6">
      <label for="seller">{% trans "Filter by seller" %}</label>
      {% render_field filter.form.seller class="form-control" %}
    </div>
    <div class="form-group col-md-6">
      <label for="status">{% trans "Filter by status" %}</label>
      {% render_field filter.form.status class="form-control" %}
    </div>
  </div>

  <!-- Fila 2: Rango de Fecha de Asignación -->
  <div class="row">
    <div class="form-group col-md-6">
      <label>{% trans "Date assigned (from)" %}</label>
      {% render_field filter.form.date_assigned_min class="form-control" placeholder="YYYY-MM-DD" %}
      <small class="form-text text-muted">{% trans "Filter contacts assigned from this date onwards" %}</small>
    </div>
    <div class="form-group col-md-6">
      <label>{% trans "Date assigned (to)" %}</label>
      {% render_field filter.form.date_assigned_max class="form-control" placeholder="YYYY-MM-DD" %}
      <small class="form-text text-muted">{% trans "Filter contacts assigned up to this date" %}</small>
    </div>
  </div>

  <!-- Fila 3: Rango de Fecha de Última Acción -->
  <div class="row">
    <div class="form-group col-md-6">
      <label>{% trans "Last action date (from)" %}</label>
      {% render_field filter.form.last_action_date_min class="form-control" placeholder="YYYY-MM-DD" %}
      <small class="form-text text-muted">{% trans "Filter contacts with last action from this date onwards" %}</small>
    </div>
    <div class="form-group col-md-6">
      <label>{% trans "Last action date (to)" %}</label>
      {% render_field filter.form.last_action_date_max class="form-control" placeholder="YYYY-MM-DD" %}
      <small class="form-text text-muted">{% trans "Filter contacts with last action up to this date" %}</small>
    </div>
  </div>

  <!-- Botones de acción -->
  <div class="row">
    <div class="col-md-12 text-right">
      <span class="mr-3"><strong>{{ filtered_count }}</strong> {% trans "contacts" %}</span>
      <button type="submit" class="btn bg-gradient-primary">
        <i class="fas fa-filter"></i> {% trans "Apply filters" %}
      </button>
      {% if request.GET %}
        <a href="{% url 'campaign_statistics_detail' campaign.id %}" class="btn btn-secondary">
          <i class="fas fa-times"></i> {% trans "Clear filters" %}
        </a>
      {% endif %}
    </div>
  </div>
</form>
```

**Mejoras de UI:**

- **Diseño organizado:** Cuadrícula de 2 columnas para mejor utilización del espacio
- **Texto de ayuda:** Explica qué hace cada filtro de fecha
- **Botón de limpiar filtros:** Aparece cuando los filtros están activos, resetea a vista predeterminada
- **Iconos:** Indicadores visuales para acciones de aplicar y limpiar
- **Conteo prominente:** Muestra el conteo de contactos filtrados antes de los botones de acción
- **Estilo consistente:** Sigue patrones de Bootstrap usados en toda la aplicación

**Mejoras Adicionales del Template:**

- Se corrigieron problemas de linting del template (uso apropiado de comillas, espacios en blanco)
- Se mejoró la estructura de encabezados con nombre de campaña en etiqueta `<small>`
- Mejor indentación y formato en todo el archivo

### 4. Configuración de URL Actualizada

**Archivo:** `support/urls.py`

Se actualizó para usar la nueva vista basada en clases con parámetro nombrado:

**Antes:**

```python
from support.views import campaign_statistics_detail

re_path(r"^campaign_statistics/(\d+)/$", campaign_statistics_detail, name="campaign_statistics_detail"),
```

**Después:**

```python
from support.views import CampaignStatisticsDetailView

re_path(
    r"^campaign_statistics/(?P<campaign_id>\d+)/$",
    CampaignStatisticsDetailView.as_view(),
    name="campaign_statistics_detail"
),
```

**Beneficios:**

- Parámetro nombrado `campaign_id` para claridad
- Uso apropiado de vista basada en clases con `.as_view()`
- Mantiene el mismo patrón de URL para compatibilidad hacia atrás

## Nuevas Capacidades de Filtrado

Los usuarios ahora pueden filtrar estadísticas de campaña por:

### 1. **Filtro de Vendedor** (existente, preservado)

- Filtrar estadísticas por vendedor específico
- Muestra conteos de asignación específicos del vendedor y ventas de productos

### 2. **Filtro de Estado** (nuevo)

- Filtrar por estado de campaña del contacto
- Opciones: No contactado aún, Contactado, Intentó contactar, etc.

### 3. **Rango de Fecha de Asignación** (nuevo)

- **Fecha mínima:** Mostrar contactos asignados desde esta fecha en adelante
- **Fecha máxima:** Mostrar contactos asignados hasta esta fecha
- **Casos de uso:**
  - Analizar contactos asignados en una semana/mes específico
  - Rastrear patrones de asignación a lo largo del tiempo
  - Comparar asignaciones tempranas vs. tardías de la campaña

### 4. **Rango de Fecha de Última Acción** (nuevo)

- **Fecha mínima:** Mostrar contactos con última acción desde esta fecha en adelante
- **Fecha máxima:** Mostrar contactos con última acción hasta esta fecha
- **Casos de uso:**
  - Encontrar contactos obsoletos (sin acción reciente)
  - Identificar contactos recientemente activos
  - Rastrear compromiso de contactos a lo largo del tiempo
  - Encontrar contactos que necesitan seguimiento

## Mejoras de Experiencia de Usuario

### Flujo de Trabajo de Filtros

**Antes:**

1. Menú desplegable único de vendedor
2. Clic en botón "Filtrar"
3. Capacidades de análisis limitadas

**Después:**

1. Seleccionar vendedor (opcional)
2. Seleccionar estado (opcional)
3. Establecer rango de fecha de asignación (opcional)
4. Establecer rango de fecha de última acción (opcional)
5. Clic en "Aplicar filtros" con icono
6. Ver conteo filtrado prominentemente
7. Clic en "Limpiar filtros" para resetear (cuando los filtros están activos)

### Ejemplos de Casos de Uso

**1. Encontrar Contactos Obsoletos:**

```text
Fecha de última acción (hasta): 2025-11-01
Resultado: Contactos sin acción desde el 1 de noviembre
```

**2. Analizar Asignaciones Recientes:**

```text
Fecha de asignación (desde): 2025-12-01
Fecha de asignación (hasta): 2025-12-07
Resultado: Contactos asignados en la primera semana de diciembre
```

**3. Rendimiento del Vendedor en Período de Tiempo:**

```text
Vendedor: Juan Pérez
Fecha de última acción (desde): 2025-12-01
Resultado: Actividad de Juan en diciembre
```

**4. Análisis Combinado:**

```text
Estado: Contactado
Fecha de asignación (desde): 2025-11-01
Fecha de última acción (desde): 2025-12-01
Resultado: Contactos asignados en noviembre que fueron contactados en diciembre
```

## Beneficios Técnicos

### 1. **Patrones Modernos de Django**

- Usa FilterView (mejor práctica de Django para listas filtradas)
- Arquitectura de vista basada en clases
- Uso apropiado de mixins (BreadcrumbsMixin, UserPassesTestMixin)

### 2. **Mantenibilidad**

- Clara separación de responsabilidades
- Clase de filtro reutilizable
- Código bien documentado con docstrings
- Sigue patrones establecidos en otras vistas modernizadas

### 3. **Rendimiento**

- Todos los cálculos de estadísticas preservados y optimizados
- Filtrado eficiente de queryset
- No se introdujeron consultas adicionales a la base de datos

### 4. **Calidad de Código**

- Cumple con PEP8 (se corrigieron problemas de longitud de línea)
- Manejo apropiado de errores
- Definiciones de filtros con seguridad de tipos

### 5. **Compatibilidad Hacia Atrás**

- Se mantuvo el nombre de función para referencias de URL existentes
- Mismo patrón de URL
- Toda la funcionalidad existente preservada

## Recomendaciones de Pruebas

### 1. **Funcionalidad de Filtros**

```python
# Probar filtrado de rango de fechas
- Asignar contactos en diferentes fechas
- Filtrar por date_assigned_min y verificar resultados
- Filtrar por date_assigned_max y verificar resultados
- Probar rangos de fechas combinados

# Probar filtrado de última acción
- Crear actividades en diferentes fechas
- Filtrar por last_action_date_min y verificar resultados
- Filtrar por last_action_date_max y verificar resultados
```

### 2. **Precisión de Estadísticas**

```python
# Verificar que todas las estadísticas aún se calculan correctamente
- Verificar conteos de estado con filtros
- Verificar estadísticas de resolución
- Confirmar tasas de éxito
- Probar análisis de razones de rechazo
- Validar seguimiento de ventas de productos
```

### 3. **Control de Acceso**

```python
# Probar UserPassesTestMixin
- Verificar que el grupo Managers puede acceder
- Verificar que los superusuarios pueden acceder
- Verificar que los no gerentes no pueden acceder
```

### 4. **Pruebas de UI/UX**

```text
- Verificar que los selectores de fecha funcionen en todos los navegadores
- Probar funcionalidad del botón "Limpiar filtros"
- Confirmar navegación de breadcrumbs
- Verificar diseño responsivo en móvil
- Validar que el texto de ayuda se muestre correctamente
```

## Notas de Migración

### Para Desarrolladores

**No se requieren migraciones de base de datos** - todos los cambios son a nivel de vista/template.

**Cambios de importación:**

```python
# Antiguo
from support.views import campaign_statistics_detail

# Nuevo (ambos funcionan)
from support.views import CampaignStatisticsDetailView
from support.views import campaign_statistics_detail  # Aún disponible
```

### Para Usuarios

**No se requiere acción** - la vista funciona exactamente como antes con opciones de filtrado adicionales.

**Nuevas características disponibles inmediatamente:**

- Menú desplegable de filtro de estado
- Filtros de rango de fecha de asignación
- Filtros de rango de fecha de última acción
- Botón de limpiar filtros
- Navegación de breadcrumbs

## Mejoras Futuras

Mejoras potenciales para iteraciones futuras:

1. **Exportar resultados filtrados:** Agregar exportación CSV para estadísticas filtradas
2. **Guardar presets de filtros:** Permitir a los gerentes guardar combinaciones de filtros comúnmente usadas
3. **Selector visual de rango de fechas:** Implementar widget de calendario para selección más fácil de fechas
4. **Análisis basado en tiempo:** Agregar gráficos mostrando tendencias a lo largo del tiempo
5. **Modo de comparación:** Comparar estadísticas entre diferentes períodos de tiempo
6. **Filtros avanzados:** Agregar filtros para tipo de resolución, veces contactado, etc.

## Cambios Relacionados

Esta modernización sigue el mismo patrón que:

- `IssueListView` (convertida 2025-11-10)
- `IssueDetailView` (convertida a UpdateView 2025-11-10)
- `ContactListView` (optimizada 2025-11-10)

## Archivos Modificados

```text
support/filters.py                                    # Filtro mejorado con rangos de fechas
support/views/all_views.py                           # Convertido a FilterView
support/templates/campaign_statistics_detail.html    # UI de filtros mejorada
support/urls.py                                      # Configuración de URL actualizada
```

## Conclusión

Esta modernización alinea la vista de detalle de estadísticas de campaña con las mejores prácticas actuales de Django mientras mejora significativamente sus capacidades analíticas. La adición de filtros de rango de fechas permite a los gerentes realizar análisis de campaña más sofisticados, rastrear el compromiso de contactos a lo largo del tiempo e identificar contactos que necesitan atención. La UI mejorada hace que el proceso de filtrado sea más intuitivo y amigable para el usuario.
