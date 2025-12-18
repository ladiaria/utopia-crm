# Funcionalidad de Reactivación de Suscripciones

**Fecha:** 2025-12-18
**Ticket:** t990
**Tipo:** Mejora de Funcionalidad
**Componente:** Suscripciones, Actividades, Modelos Core
**Impacto:** Gestión de Suscripciones, Seguimiento de Actividades, Preservación de Datos

## Resumen

Se implementó una funcionalidad completa de reactivación de suscripciones que permite al personal reactivar suscripciones que fueron previamente desuscritas usando el método `book_unsubscription`. La funcionalidad incluye una pantalla de confirmación, preservación completa de datos en metadatos de Activity, recuperación de datos a prueba de fallos, y una nueva vista de detalle de Activity para auditoría. Además, se mejoró el modelo Activity con un campo JSONField de metadata para almacenamiento de datos estructurados y se mejoró el manejo de tipos de actividad en todo el sistema.

## Funcionalidades Implementadas

### 1. Vista de Reactivación de Suscripciones

**Archivo:** `support/views/subscriptions.py`

Se creó la vista `reactivate_subscription` con las siguientes capacidades:

- **Validación**: Solo permite reactivación de desuscripciones completas (`unsubscription_type=1`)
- **Previene Reactivaciones Inválidas**: Bloquea reactivación de desuscripciones parciales y cambios de productos (que crean nuevas suscripciones)
- **Búsqueda Inteligente de Datos**: Busca datos de desuscripción en metadata de Activity primero, luego recurre al formato legacy en notes para compatibilidad hacia atrás
- **Recuperación de Datos a Prueba de Fallos**: Si no existe Activity de desuscripción, crea automáticamente una desde el estado actual de la suscripción antes de reactivar
- **Reversión Completa de Campos**: Limpia todos los campos relacionados con desuscripción:
  - `end_date`
  - `unsubscription_reason`
  - `unsubscription_channel`
  - `unsubscription_addendum`
  - `unsubscription_type`
  - `unsubscription_date`
  - `unsubscription_manager`
  - `unsubscription_products` (relación ManyToMany)
- **Registro de Actividad**: Crea Activity de reactivación con metadata vinculando a la desuscripción original

### 2. Plantilla de Confirmación de Reactivación

**Archivo:** `support/templates/reactivate_subscription.html`

Se creó una pantalla de confirmación completa que muestra:

- Detalles actuales de la suscripción (contacto, productos, fecha de fin, razón)
- Información original de desuscripción (fecha, gestor, razón, canal, adenda)
- Enlace a la Activity original de desuscripción para auditoría completa
- Advertencias claras sobre qué hará la reactivación
- Información sobre qué tipos de suscripción pueden ser reactivadas

### 3. Campo Metadata en Activity

**Archivo:** `core/models.py`

Se agregó campo JSONField `metadata` al modelo Activity:

```python
metadata = models.JSONField(
    blank=True,
    null=True,
    verbose_name=_("Metadata"),
    help_text=_("Datos estructurados para almacenar información adicional de actividad")
)
```

**Beneficios:**

- Almacenamiento apropiado de datos estructurados en lugar de strings JSON en campo notes
- Soporta cualquier tipo de metadata (desuscripción, reactivación, etc.)
- Permite consultas complejas usando lookups JSONField de Django
- Mantiene campo notes legible para humanos para propósitos de visualización

**Migración:** `core/migrations/0113_add_activity_metadata.py`

### 4. Almacenamiento Mejorado de Datos de Desuscripción

**Archivo:** `support/views/subscriptions.py`

Se actualizó `book_unsubscription` para almacenar datos completos de desuscripción:

**Metadata almacenada:**

- `type`: "unsubscription"
- `subscription_id`
- `end_date`
- `unsubscription_reason`
- `unsubscription_channel`
- `unsubscription_addendum`
- `unsubscription_type`
- `unsubscription_date`
- `unsubscription_manager_id`
- `unsubscription_manager_name`
- `unsubscription_products` (lista de IDs de productos)

**Notas legibles para humanos:**

```text
Desuscripción completa registrada para 2025-12-20.
Razón: Problemas económicos
Productos: Digital, Impreso
Gestor: Juan Pérez
```

### 5. Vista de Detalle de Activity

**Archivos:**

- `support/views/activities.py` - `ActivityDetailView`
- `support/templates/activities/activity_detail.html`
- `support/urls.py` - Patrón URL: `/activity/<id>/`

Se creó una vista dedicada para ver detalles de actividades con:

- Visualización completa de información de actividad
- **Manejo especial de metadata:**
  - **Metadata de desuscripción**: Tabla formateada mostrando detalles de suscripción, fechas, gestor, razón, canal, adenda
  - **Metadata de reactivación**: Muestra información de reactivación con enlace a actividad de desuscripción original
  - **Metadata genérica**: JSON formateado para otros tipos de metadata
- Indicador de advertencia para actividades de respaldo creadas durante reactivación
- Navegación con breadcrumbs
- Enlaces a contactos, issues y actividades relacionadas

### 6. Mejoras en Sistema de Tipos de Actividad

**Archivo:** `core/choices.py`

Se mejoró el sistema de tipos de actividad para hacer "Internal" (N) un tipo de sistema requerido:

```python
def get_activity_types():
    """
    Retorna tipos de actividad con 'Internal' (N) siempre incluido como tipo de sistema requerido.

    El tipo 'Internal' se usa para actividades generadas por el sistema (desuscripciones,
    reactivaciones, etc.) y debe estar siempre disponible independientemente de tipos de actividad personalizados.
    """
    internal_type = ("N", _("Internal"))
    custom_types = getattr(settings, "CUSTOM_ACTIVITY_TYPES", DEFAULT_ACTIVITY_TYPES)

    if internal_type not in custom_types:
        return custom_types + (internal_type,)
    return custom_types
```

**Cambios:**

- Se removió "Internal" de `DEFAULT_ACTIVITY_TYPES`
- Se hizo que `get_activity_types()` siempre incluya el tipo Internal
- Se actualizaron todas las actividades generadas por el sistema para usar `activity_type="N"` en lugar de `"C"`
- Se agregó documentación completa explicando por qué Internal es requerido

### 7. Corrección de Visualización de Tipo de Actividad

**Archivo:** `core/models.py`

Se agregó método `get_activity_type_display()` al modelo Activity:

```python
def get_activity_type_display(self):
    """
    Retorna el nombre de visualización para el tipo de actividad.
    Este método es necesario porque activity_type usa una función dinámica get_activity_types()
    en lugar de choices estáticas, por lo que el get_FOO_display automático de Django no funciona.
    """
    activity_types = dict(get_activity_types())
    return activity_types.get(self.activity_type, "N/A")
```

**Plantillas corregidas:**

- `support/templates/contact_detail/tabs/_activities.html`
- `support/templates/contact_detail/tabs/includes/_activity_modal.html`

### 8. Integración de UI

**Archivos:**

- `support/templates/contact_detail/tabs/includes/_subscription_card.html`
- `support/templates/contact_detail/tabs/includes/_overview_subscription_list_item.html`

Se agregaron botones "Reactivar" que:

- Solo aparecen para desuscripciones completas (`end_date` existe y `unsubscription_type == 1`)
- Reemplazan el botón "Desuscribir" cuando aplica
- Usan esquema de color verde con ícono de rehacer
- Enlazan a la pantalla de confirmación de reactivación

### 9. Enrutamiento de URLs

**Archivo:** `support/urls.py`

Se agregaron nuevos patrones de URL:

- `/reactivate_subscription/<subscription_id>/` - Confirmación y procesamiento de reactivación
- `/activity/<pk>/` - Vista de detalle de actividad

## Detalles Técnicos

### Flujo de Datos

1. **Desuscripción:**
   - Usuario registra desuscripción vía `book_unsubscription`
   - Sistema crea Activity con tipo "N" (Internal)
   - Metadata almacena todos los detalles de desuscripción
   - Campo notes contiene resumen legible para humanos

2. **Reactivación:**
   - Usuario hace clic en botón "Reactivar" en suscripción
   - Sistema valida que la suscripción puede ser reactivada
   - Sistema busca Activity de desuscripción (metadata primero, luego formato legacy)
   - Si no se encuentra Activity, crea Activity de respaldo desde estado actual de suscripción
   - Pantalla de confirmación muestra todos los datos almacenados
   - Al confirmar:
     - Todos los campos de desuscripción se limpian
     - Se crea nueva Activity con metadata de reactivación
     - Se muestra mensaje de éxito

### Compatibilidad Hacia Atrás

- **Soporte de Formato Legacy**: Sistema puede leer actividades antiguas que almacenaban JSON en campo notes
- **Degradación Elegante**: Si no existe actividad de desuscripción, sistema crea una antes de reactivar
- **Actividades Existentes**: Todas las actividades existentes continúan funcionando normalmente

### Seguridad y Validación

- **Acceso solo para staff**: Decorador `@staff_member_required` en todas las vistas
- **Validación de tipo**: Solo desuscripciones completas pueden ser reactivadas
- **Validación de estado**: Suscripción debe tener `end_date` para ser reactivada
- **Confirmación requerida**: Proceso de dos pasos previene reactivaciones accidentales

## Cambios en Base de Datos

### Migración: `core/migrations/0113_add_activity_metadata.py`

- Se agregó campo JSONField `metadata` al modelo `Activity`
- Se agregó campo JSONField `metadata` al modelo `HistoricalActivity`
- Se actualizaron choices de `inactivity_reason` en `Subscription` y `HistoricalSubscription`
- Se actualizaron choices de `unsubscription_type` en `Subscription` y `HistoricalSubscription`

## Beneficios

### Para Usuarios

- **Reactivación Fácil**: Proceso simple de clic de botón para reactivar suscripciones
- **Información Clara**: Todos los detalles de desuscripción visibles antes de reactivar
- **Rastro de Auditoría**: Historial completo preservado en registros de Activity
- **Previene Errores**: Validación asegura que solo suscripciones apropiadas puedan ser reactivadas

### Para Administradores

- **Preservación de Datos**: Todos los datos de desuscripción almacenados en formato estructurado
- **Vista de Detalle de Activity**: Puede inspeccionar metadata y detalles de cualquier actividad
- **A Prueba de Fallos**: Sistema maneja datos faltantes elegantemente
- **Compatible Hacia Atrás**: Funciona con datos existentes

### Para Desarrolladores

- **Metadata Estructurada**: JSONField permite consultas complejas y tipos de datos apropiados
- **Extensible**: Patrón de metadata puede usarse para otras funcionalidades
- **Seguridad de Tipos**: Sistema de tipos de actividad asegura que tipo Internal siempre esté disponible
- **Código Limpio**: Separación de datos estructurados (metadata) y texto de visualización (notes)

## Recomendaciones de Pruebas

1. **Desuscribir y Reactivar:**
   - Crear una suscripción
   - Desuscribirla completamente con razón, canal y adenda
   - Verificar que se crea Activity con metadata
   - Reactivar la suscripción
   - Verificar que todos los campos se limpian y se crea Activity de reactivación

2. **Pruebas de Validación:**
   - Intentar reactivar una suscripción activa (debe fallar)
   - Intentar reactivar una desuscripción parcial (debe fallar)
   - Intentar reactivar un cambio de producto (debe fallar)

3. **Prueba A Prueba de Fallos:**
   - Crear una suscripción desuscrita sin Activity
   - Intentar reactivación
   - Verificar que sistema crea Activity de respaldo antes de reactivar

4. **Vista de Detalle de Activity:**
   - Ver Activity de desuscripción - verificar que metadata se muestra correctamente
   - Ver Activity de reactivación - verificar que enlace a desuscripción original funciona
   - Ver Activity regular - verificar que se muestra normalmente

5. **Visualización de Tipo de Actividad:**
   - Revisar pestaña de actividades en detalle de contacto
   - Abrir modal de actividad
   - Verificar que tipos de actividad se muestran correctamente (especialmente "Internal")

## Mejoras Futuras

### Mejoras a Corto Plazo

1. **Campo de Razón de Reactivación:**
   - Agregar campo opcional de razón por la cual se reactiva la suscripción
   - Almacenar en metadata de Activity de reactivación
   - Mostrar en vista de detalle de Activity

2. **Reactivación Masiva:**
   - Permitir seleccionar múltiples suscripciones para reactivación
   - Útil para campañas o promociones especiales
   - Incluir pantalla de confirmación con lista de suscripciones

3. **Notificaciones de Reactivación:**
   - Notificación por email al cliente cuando se reactiva suscripción
   - Plantilla de email configurable
   - Opción de incluir mensaje de bienvenida o oferta especial

4. **Estadísticas de Reactivación:**
   - Dashboard mostrando tasas de reactivación
   - Filtrar por razón, período de tiempo, producto
   - Comparar con estadísticas de desuscripción

### Mejoras a Mediano Plazo

1. **Flujos de Trabajo de Reactivación Automatizada:**
   - Permitir a clientes auto-reactivar a través de portal de cliente
   - Reglas configurables para qué suscripciones pueden ser auto-reactivadas
   - Flujo de aprobación para ciertos casos

2. **Campañas de Reactivación:**
   - Dirigirse a contactos con suscripciones desuscritas
   - Rastrear efectividad de campaña
   - Precios especiales u ofertas para reactivaciones

3. **Metadata de Activity Mejorada:**
   - Agregar metadata a más tipos de actividad (llamadas, emails, etc.)
   - Crear plantillas de metadata para tipos comunes de actividad
   - Permitir campos de metadata personalizados por tipo de actividad

4. **Vista de Línea de Tiempo de Activity:**
   - Línea de tiempo visual de todas las actividades para un contacto
   - Filtrar por tipo de actividad, tipo de metadata, rango de fechas
   - Exportar línea de tiempo a PDF o CSV

### Mejoras a Largo Plazo

1. **Analítica de Ciclo de Vida de Suscripción:**
   - Rastrear ciclo completo: creación → activa → desuscrita → reactivada
   - Identificar patrones en comportamiento de suscripción
   - Predecir probabilidad de reactivación
   - Recomendaciones basadas en ML para estrategias de retención

2. **Consultas Avanzadas de Metadata:**
   - Construir interfaz de consulta para buscar actividades por metadata
   - Crear búsquedas guardadas y reportes
   - Endpoints de API para consultas de metadata

3. **Versionado de Metadata:**
   - Rastrear cambios a metadata de actividad a lo largo del tiempo
   - Mostrar historial de actualizaciones de metadata
   - Útil para auditoría y cumplimiento

4. **Integración con Sistemas Externos:**
   - Sincronizar eventos de reactivación con sistemas CRM
   - Disparar webhooks en reactivación
   - Exportar datos de reactivación a plataformas de analítica

## Archivos Modificados

### Aplicación Core

- `core/models.py` - Agregado campo metadata, método get_activity_type_display
- `core/choices.py` - Mejorado get_activity_types para siempre incluir tipo Internal
- `core/migrations/0113_add_activity_metadata.py` - Migración de base de datos

### Aplicación Support - Vistas

- `support/views/subscriptions.py` - Agregado reactivate_subscription, mejorado book_unsubscription
- `support/views/activities.py` - Agregado ActivityDetailView
- `support/views/__init__.py` - Agregados imports para nuevas vistas

### Aplicación Support - Plantillas

- `support/templates/reactivate_subscription.html` - Nueva plantilla de confirmación de reactivación
- `support/templates/activities/activity_detail.html` - Nueva plantilla de detalle de actividad
- `support/templates/contact_detail/tabs/includes/_subscription_card.html` - Agregado botón reactivar
- `support/templates/contact_detail/tabs/includes/_overview_subscription_list_item.html` - Agregado botón reactivar
- `support/templates/contact_detail/tabs/includes/_activity_modal.html` - Corregida visualización de tipo de actividad

### Aplicación Support - URLs

- `support/urls.py` - Agregados patrones de URL para reactivación y detalle de actividad

## Notas

- Todas las actividades generadas por el sistema ahora usan activity_type="N" (Internal) para corrección semántica
- El patrón de campo metadata puede extenderse a otras funcionalidades que requieran almacenamiento de datos estructurados
- La vista de detalle de Activity proporciona un lugar centralizado para inspeccionar información completa de cualquier actividad
- El mecanismo a prueba de fallos asegura que los datos nunca se pierdan incluso si falta la actividad de desuscripción original
