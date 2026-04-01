# Consola de Gestión de Comunidad (Consola GDC)

**Fecha:** 2026-02-10
**Tipo:** Nueva Funcionalidad
**Componente:** Sistema de Gestión de Incidencias
**Rama:** t1030
**Impacto:** Experiencia de Usuario, Eficiencia de Flujo de Trabajo

## Resumen

Nuevo panel interactivo para agentes de gestión de comunidad (GDC) que muestra las incidencias abiertas asignadas al usuario actual, agrupadas por Categoría y Subcategoría, con conteos divididos en tres columnas temporales basadas en el campo `next_action_date`: Vencidas, Hoy y Futuras. Cada conteo es un enlace clickeable que abre la lista de incidencias existente con los filtros de `next_action_date` correspondientes pre-aplicados. El acceso se controla mediante un permiso dedicado.

## Motivación

Los agentes de GDC necesitaban una vista rápida de su carga de trabajo asignada sin tener que filtrar manualmente la lista de incidencias cada vez. La consola proporciona una vista general de lo que necesita atención inmediata (vencidas), lo que vence hoy y lo que viene próximamente, organizado por las categorías de incidencias con las que trabajan.

## Funcionalidades Clave Implementadas

### 1. Vista de Consola de Comunidad

**Archivo:** `support/views/all_views.py`

Nueva `CommunityConsoleView` (hereda de `TemplateView`, `PermissionRequiredMixin`, `LoginRequiredMixin`, `BreadcrumbsMixin`) que:

- Consulta incidencias abiertas asignadas al usuario actual (`closing_date__isnull=True`)
- Excluye incidencias en estado terminal (`ISSUE_STATUS_FINISHED_LIST` de settings)
- Agrupa incidencias por Categoría → Subcategoría usando agregación de base de datos (`Count` con filtros `Q`)
- Cuenta Vencidas (`next_action_date < hoy`), Hoy (`next_action_date == hoy`) y Futuras (`next_action_date > hoy`) para cada grupo
- Las incidencias sin `next_action_date` cuentan en el total pero no aparecen en ninguna columna de fecha
- Pasa datos estructurados y referencias de fecha al template

### 2. Template de Panel Interactivo

**Archivo:** `support/templates/community_console.html`

- **Tarjetas resumen** en la parte superior mostrando totales generales para Vencidas (rojo), Hoy (amarillo), Futuras (verde) y Total (gris)
- **Tarjetas de categoría colapsables** (estilo acordeón) con botones expandir/colapsar todo
- **Tabla de subcategorías** dentro de cada tarjeta: Subcategoría | Vencidas | Hoy | Futuras | Total
- **Conteos clickeables** que enlazan a `IssueListView` con filtros pre-aplicados (categoría, subcategoría, rango de next_action_date, asignado a, excluir finalizadas)
- **Badges con colores**: rojo para vencidas, amarillo para hoy, verde para futuras
- **Barra de búsqueda en tiempo real** (JavaScript) para filtrar categorías/subcategorías por nombre
- **Tarjeta de instrucciones** al final explicando cómo se usa la fecha de próxima acción para la agrupación y cómo interactuar con la consola

### 3. Permiso Personalizado

**Archivo:** `support/models.py`

Se agregó el permiso `can_access_community_console` en `Issue.Meta.permissions`, controlando quién puede acceder a la consola.

### 4. Filtro de Template `has_perm`

**Archivo:** `core/templatetags/core_tags.py`

Nuevo filtro de template para verificaciones de permisos más limpias en templates, usado en lugar de `in_group` para un control de acceso más flexible:

```html
{% if request.user|has_perm:"support.can_access_community_console" %}
```

### 5. Item de Menú en Sidebar

**Archivo:** `templates/components/_sidebar.html`

Nuevo item de menú "Consola de comunidad" con icono `fas fa-users`, visible solo para usuarios con el permiso `can_access_community_console`.

### 6. Filtro `exclude_finished` para IssueListView

**Archivo:** `support/filters.py`

Nuevo `BooleanFilter` con widget checkbox agregado a `IssueFilter`. Cuando está marcado, excluye incidencias cuyo slug de estado está en `settings.ISSUE_STATUS_FINISHED_LIST`. Este filtro:

- Se pasa automáticamente (`&exclude_finished=true`) por todos los enlaces de la consola para mantener consistencia
- Está disponible como checkbox independiente en el formulario de filtros de la lista de incidencias para cualquier usuario

**Archivo:** `support/templates/list_issues.html`

Se agregó el checkbox "Excluir finalizadas" al formulario de filtros, junto al indicador de cantidad de incidencias.

## Correcciones de Bugs

### Fix: `None` Pasado como Parámetro de Query

**Causa raíz:** Cuando una incidencia no tiene subcategoría, `sub_category__id` es `None`. El template renderizaba `sub_category=None` literalmente en la URL. Django-filters v23.4 con `strict=True` invalida el formulario cuando encuentra un valor inválido para un `ModelChoiceFilter`, devolviendo un **queryset vacío**. Por esto los resultados solo aparecían después de presionar "Filtrar" manualmente (lo cual reenvía sin el parámetro inválido).

**Corrección:** Se cambiaron todos los enlaces del template para usar `{% if sub.id %}&sub_category={{ sub.id }}{% endif %}` — el parámetro solo se incluye cuando tiene un valor real.

## Detalles Técnicos

### Archivos Creados

- `support/templates/community_console.html` — Template del panel
- `support/migrations/0033_add_community_console_permission.py` — Migración para el nuevo permiso

### Archivos Modificados

- `support/models.py` — Agregado permiso `can_access_community_console` en `Issue.Meta`
- `support/views/all_views.py` — Agregada `CommunityConsoleView`
- `support/urls.py` — Agregado patrón de URL para la consola
- `support/filters.py` — Agregado filtro `exclude_finished` y método `filter_exclude_finished`
- `support/templates/list_issues.html` — Agregado checkbox "Excluir finalizadas"
- `templates/components/_sidebar.html` — Agregado item de menú con control de permisos
- `core/templatetags/core_tags.py` — Agregado filtro de template `has_perm`

### Impacto en Base de Datos

- **Una migración requerida:** Agrega el permiso `can_access_community_console` al modelo `Issue`
- Después de migrar, el permiso debe asignarse a los usuarios/grupos correspondientes vía Django admin

### Consideraciones de Rendimiento

- Usa agregación a nivel de base de datos (`Count` con filtros `Q`) — sin consultas N+1
- `select_related('sub_category', 'status')` para joins eficientes
- Una sola consulta con `.values().annotate()` para toda la agrupación y conteo

## Notas de Migración

1. Ejecutar `python manage.py migrate support` para crear el nuevo permiso
2. Asignar el permiso `support.can_access_community_console` a los usuarios o grupos que necesiten acceso a la consola GDC
3. El setting `ISSUE_STATUS_FINISHED_LIST` debe estar definido en la configuración para que la exclusión de estados terminales funcione

## Recomendaciones de Prueba

### Pruebas Manuales

1. **Verificación de permisos:** Verificar que la consola solo es accesible para usuarios con `can_access_community_console`
2. **Precisión de datos:** Verificar que los conteos de vencidas/hoy/futuras coinciden con las incidencias reales según `next_action_date`
3. **Exclusión de estado terminal:** Verificar que las incidencias finalizadas/resueltas no aparecen en la consola
4. **Navegación por enlaces:** Hacer clic en cada conteo y verificar que la lista de incidencias muestra los resultados filtrados correctos
5. **Sin subcategoría:** Verificar que las incidencias sin subcategoría no causan "None" en las URLs
6. **Filtro de búsqueda:** Escribir en la barra de búsqueda y verificar que las categorías/subcategorías se filtran en tiempo real
7. **Expandir/Colapsar:** Probar expandir todo, colapsar todo y el toggle individual de cada tarjeta
8. **Checkbox excluir finalizadas:** Verificar que el checkbox funciona en la lista de incidencias de forma independiente
9. **Visibilidad del sidebar:** Verificar que el item de menú solo aparece para usuarios con permiso

## Componentes Relacionados

- **Modelo Issue:** `support/models.py`
- **Vista de Lista de Issues:** `support/views/all_views.py` — `IssueListView`
- **Filtro de Issues:** `support/filters.py` — `IssueFilter`
- **Settings:** `ISSUE_STATUS_FINISHED_LIST` — Define estados terminales
