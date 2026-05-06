# Panel de Gerente de Comunidad, Asignación de Incidencias y Vista General del Equipo

**Fecha:** 2026-02-23
**Tipo:** Nueva Funcionalidad
**Componente:** Sistema de Gestión de Incidencias (GDC)
**Rama:** t1034
**Impacto:** Eficiencia de Flujo de Trabajo, Gestión de Equipo, Distribución de Incidencias

## Resumen

Nuevo conjunto de vistas para gerentes de GDC (Gestión de Comunidad) que les permite:

1. **Panel** — Ver todas las subcategorías con conteos de incidencias sin asignar, desglosadas por vencidas/hoy/futuras.
2. **Asignación** — Asignar incidencias sin asignar de una subcategoría a miembros del equipo GDC usando un algoritmo round-robin.
3. **Vista general del equipo** — Monitorear la carga de trabajo de todos los usuarios GDC con desglose colapsable por categoría/subcategoría.

El acceso se controla mediante un nuevo permiso dedicado `can_manage_community_console`.

## Motivación

Los gerentes de GDC necesitaban una forma centralizada para:

- Ver qué subcategorías tienen incidencias sin asignar acumulándose
- Distribuir esas incidencias equitativamente entre los miembros del equipo
- Monitorear la carga de trabajo de cada miembro del equipo de un vistazo
- Profundizar en el detalle por categoría/subcategoría por usuario

Anteriormente, los gerentes tenían que consultar manualmente la lista de incidencias y asignarlas una por una, sin visibilidad sobre la distribución de carga de trabajo del equipo.

## Funcionalidades Clave Implementadas

### 1. Nuevo Permiso: `can_manage_community_console`

**Archivos:** `support/models.py`, `support/migrations/0034_add_community_manager_permission.py`

Se agregó un nuevo permiso en `Issue.Meta.permissions` que controla el acceso a las tres vistas de gerente. Una migración crea este permiso en la base de datos.

### 2. Vista del Panel del Gerente de Comunidad

**Archivos:** `support/views/all_views.py`, `support/templates/community_manager_dashboard.html`

`CommunityManagerDashboardView` (hereda de `TemplateView`, `PermissionRequiredMixin`, `LoginRequiredMixin`, `BreadcrumbsMixin`):

- Consulta incidencias abiertas **sin asignar** (`assigned_to__isnull=True`, `closing_date__isnull=True`)
- Excluye incidencias en estados terminales (`ISSUE_STATUS_FINISHED_LIST`)
- Agrupa por Categoría → Subcategoría usando agregación de base de datos (`Count` con filtros `Q`)
- Cuenta Vencidas, Hoy, Futuras y Total para cada grupo
- **Tarjetas resumen** en la parte superior con totales generales, claramente etiquetadas como *"(sin asignar)"*
- **Tarjeta de total** incluye nota: *"(incluye incidencias sin fecha de próxima acción)"*
- **Tarjetas de categoría colapsables** con funcionalidad expandir/colapsar todo
- **Tabla de subcategorías** con conteos clickeables que enlazan a la lista de incidencias filtrada
- **Enlace "Asignar"** por subcategoría que navega a la vista de asignación
- **Barra de búsqueda en tiempo real** (JavaScript) para filtrar categorías/subcategorías por nombre
- Enlace a la **Vista general del equipo** en el encabezado

### 3. Vista de Asignación del Gerente de Comunidad

**Archivos:** `support/views/all_views.py`, `support/templates/community_manager_assign.html`

`CommunityManagerAssignView` (hereda de `TemplateView`, `PermissionRequiredMixin`, `LoginRequiredMixin`, `BreadcrumbsMixin`):

- Muestra incidencias sin asignar para una subcategoría específica
- **Tarjetas resumen** mostrando vencidas/hoy/futuras/total sin asignar, todas etiquetadas *"(Sin asignar)"*
- **Alerta informativa** cuando hay incidencias sin fecha de próxima acción, explicando que recibirán la fecha de mañana al ser asignadas
- **Tabla de miembros del equipo** mostrando cada usuario GDC con:
  - Total actual de incidencias abiertas (con nota: *"incluye sin fecha"*)
  - Desglose Vencidas / Hoy / Futuras de su carga de trabajo actual
  - Campo de entrada para especificar cuántas incidencias asignar
- **Algoritmo de asignación round-robin** que distribuye las incidencias sin asignar más antiguas equitativamente entre los usuarios seleccionados
- Al asignar:
  - Establece `assigned_to` al usuario seleccionado
  - Mantiene el estado actual de la incidencia sin cambios
  - Establece `next_action_date` a mañana si es nulo o está en el pasado
- **Validación del lado del cliente** asegura que el total asignado no exceda las incidencias disponibles
- Mensaje de éxito después de la asignación con redirección al panel

### 4. Vista General del Equipo del Gerente de Comunidad

**Archivos:** `support/views/all_views.py`, `support/templates/community_manager_overview.html`

`CommunityManagerOverviewView` (hereda de `TemplateView`, `PermissionRequiredMixin`, `LoginRequiredMixin`, `BreadcrumbsMixin`):

- Muestra todos los usuarios activos con el permiso `can_access_community_console`
- **Tarjetas resumen** mostrando totales del equipo, etiquetadas *"(asignadas)"*
- **Tarjeta de total** incluye nota: *"(incluye incidencias sin fecha de próxima acción)"*
- **Tabla de miembros del equipo** con:
  - Columnas Vencidas / Hoy / Futuras / Total con conteos clickeables que enlazan a la lista de incidencias filtrada
  - **Barra de progreso de distribución** mostrando proporción visual de vencidas (rojo), hoy (amarillo), futuras (verde)
  - **Desglose colapsable por usuario** — clic en la fila de un usuario para expandir/colapsar su detalle por categoría y subcategoría
    - Filas de categoría con icono de carpeta y subtotales
    - Filas de subcategoría indentadas con icono de etiqueta
    - Todas las filas de desglose muestran vencidas/hoy/futuras/total alineadas con las columnas del encabezado
- **Fila de totales generales** en el pie de tabla
- **Tarjeta de leyenda** explicando columnas e interacciones, incluyendo nota sobre incidencias sin fecha de próxima acción

### 5. Integración en Barra Lateral

**Archivo:** `templates/components/_sidebar.html`

Se agregó una nueva entrada en el menú lateral "Community manager" visible solo para usuarios con el permiso `can_manage_community_console`, enlazando al panel.

### 6. Rutas URL

**Archivo:** `support/urls.py`

Tres nuevos patrones de URL:

- `community-manager/` → `CommunityManagerDashboardView` (nombre: `community_manager_dashboard`)
- `community-manager/assign/<int:subcategory_id>/` → `CommunityManagerAssignView` (nombre: `community_manager_assign`)
- `community-manager/overview/` → `CommunityManagerOverviewView` (nombre: `community_manager_overview`)

## Mejoras de Claridad en UX

En todas las vistas se prestó especial atención a que los números sean inequívocos:

- **Tarjetas del panel**: Etiquetadas "Vencidas (sin asignar)", "Hoy (sin asignar)", "Futuras (sin asignar)", "Total sin asignar"
- **Tarjetas de asignación**: Etiquetadas con sufijo "(Sin asignar)"
- **Tarjetas de vista general**: Etiquetadas "Vencidas (asignadas)", "Hoy (asignadas)", "Futuras (asignadas)", "Total asignadas al equipo"
- **Todas las tarjetas de total**: Incluyen texto pequeño "(incluye incidencias sin fecha de próxima acción)"
- **Encabezado de tabla de asignación**: "Total actual de incidencias abiertas" con subtítulo "(incluye sin fecha)"
- **Leyenda de vista general**: Explica que el Total puede ser mayor que Vencidas + Hoy + Futuras porque algunas incidencias no tienen fecha de próxima acción

## Detalles Técnicos

### Archivos Modificados

1. **`support/models.py`** — Agregado permiso `can_manage_community_console` en `Issue.Meta.permissions`
2. **`support/views/all_views.py`** — Agregadas tres nuevas vistas basadas en clases (~370 líneas)
3. **`support/urls.py`** — Agregadas importaciones y tres patrones de URL
4. **`templates/components/_sidebar.html`** — Agregada entrada en barra lateral con verificación de permiso

### Archivos Creados

1. **`support/migrations/0034_add_community_manager_permission.py`** — Migración para nuevo permiso
2. **`support/templates/community_manager_dashboard.html`** — Template del panel
3. **`support/templates/community_manager_assign.html`** — Template del formulario de asignación
4. **`support/templates/community_manager_overview.html`** — Template de vista general del equipo

### Impacto en Base de Datos

- **Una migración requerida** — Agrega el permiso `can_manage_community_console`
- **Sin cambios de esquema** — Usa campos existentes del modelo Issue
- **Actualizaciones de asignación** — Establece `assigned_to`, `status` y `next_action_date` en las incidencias

### Dependencias de Configuración

- `ISSUE_STATUS_FINISHED_LIST` — Lista de slugs de estados considerados terminales/finalizados

## Recomendaciones de Pruebas

### Pruebas Manuales

1. **Verificación de permiso**: Verificar que solo usuarios con `can_manage_community_console` pueden acceder a las vistas
2. **Panel**: Verificar que los conteos de incidencias sin asignar coinciden con la realidad por subcategoría
3. **Asignación**: Asignar incidencias a múltiples usuarios, verificar distribución round-robin
4. **Fecha de próxima acción**: Verificar que incidencias sin fecha reciben la fecha de mañana después de la asignación
5. **Vista general del equipo**: Verificar conteos por usuario, expandir/colapsar desglose, enlaces clickeables
6. **Barra lateral**: Verificar que la entrada del menú aparece solo para usuarios autorizados

### Casos Límite

1. Sin incidencias sin asignar para una subcategoría
2. Sin usuarios GDC configurados
3. Asignar más incidencias de las disponibles (debe ser prevenido por validación)
4. Incidencias con next_action_date nulo
5. Todas las incidencias ya asignadas

## Componentes Relacionados

- **CommunityConsoleView** (`support/views/all_views.py`) — Consola individual del usuario (existente)
- **IssueListView** (`support/views/all_views.py`) — Lista de incidencias con filtrado (enlazada desde todas las vistas)
- **AssignSellerView** (`support/views/all_views.py`) — Referencia del algoritmo round-robin
