# Cambio de Rutas de Suscripción con Automatización de Rutas Especiales

**Fecha:** 2026-01-26
**Tipo:** Mejora de Funcionalidad y Automatización
**Componente:** Sistema de Gestión Logística
**Impacto:** Eficiencia del Flujo de Trabajo, Seguimiento de Incidencias, Experiencia de Usuario

## Resumen

Implementación integral de una interfaz de cambio de rutas a nivel de suscripción con creación automática de incidencias para rutas especiales (50-55). Esta funcionalidad permite a los operadores de logística cambiar eficientemente las rutas de todos los productos en una sola suscripción mientras se generan automáticamente incidencias logísticas cuando los productos se asignan a rutas especiales que pueden no ser facturadas.

## Motivación

El equipo de logística necesitaba una forma más eficiente de gestionar los cambios de rutas para suscripciones:

1. **Gestión a Nivel de Suscripción:** La vista existente `change_route` solo funcionaba a nivel de ruta (todas las suscripciones en una ruta), no para suscripciones individuales
2. **Creación Manual de Incidencias:** Cuando los productos se movían a rutas especiales (50-55), los operadores tenían que crear manualmente incidencias logísticas para rastrear la no entrega
3. **Poca Visibilidad:** La funcionalidad de cambio de rutas no era fácilmente accesible desde la página de detalle del contacto
4. **Búsqueda Limitada:** Las listas largas de rutas dificultaban encontrar rápidamente rutas específicas
5. **Falta de Automatización:** No había seguimiento automático cuando los productos se asignaban a rutas especiales

## Funcionalidades Clave Implementadas

### 1. Función Utilitaria para Creación Automática de Incidencias

**Archivo:** `logistics/utils.py`

**Propósito:**
Crea automáticamente incidencias logísticas cuando los productos de suscripción se asignan a rutas especiales (50-55).

**Implementación:**

```python
def create_issue_for_special_route(subscription, route_number, user=None):
    """
    Crea una Incidencia cuando un producto de suscripción se cambia a una ruta especial (50-55).

    Args:
        subscription: El objeto Subscription
        route_number: El número de ruta que fue asignado
        user: El usuario que hizo el cambio (opcional, se establecerá como manager)

    Returns:
        Objeto Issue si se creó, None en caso contrario
    """
    # Solo crear incidencia para rutas especiales (50-55 inclusive)
    if route_number not in range(50, 56):
        return None

    # Obtener subcategoría y estado desde settings para flexibilidad
    subcategory_slug = getattr(settings, 'ISSUE_SUBCATEGORY_NOT_DELIVERED', 'not-delivered')
    status_slug = getattr(settings, 'ISSUE_STATUS_UNASSIGNED', 'unassigned')

    # Crear incidencia con categoría logística
    issue = Issue.objects.create(
        contact=subscription.contact,
        subscription=subscription,
        category="L",  # Categoría Logística
        sub_category=subcategory,
        status=status,
        manager=user,
        assigned_to=None,  # No asignado a nadie
        notes=_("Generado automáticamente por cambio de ruta a ruta especial (ruta {})").format(route_number),
    )

    return issue
```

**Características Clave:**

- Usa constantes de settings (`ISSUE_SUBCATEGORY_NOT_DELIVERED`, `ISSUE_STATUS_UNASSIGNED`) para flexibilidad entre instalaciones
- Crea incidencias logísticas sin asignar para seguimiento
- Registra el usuario que hizo el cambio como manager
- Auto-genera notas descriptivas con el número de ruta
- Retorna None si la ruta no es especial (50-55)

### 2. Vista de Cambio de Rutas de Suscripción

**Archivo:** `logistics/views.py`

**Vista:** `change_subscription_routes(request, subscription_id)`

**Propósito:**
Vista dedicada para cambiar rutas en todos los productos dentro de una sola suscripción.

**Funcionalidades:**

- Muestra todos los productos de suscripción con rutas actuales
- Permite cambios masivos de rutas para todos los productos en un solo envío de formulario
- Soporta mensajes de etiqueta e instrucciones especiales por producto
- Crea automáticamente incidencias para rutas especiales (50-55)
- Muestra mensajes de advertencia cuando se crean incidencias
- Redirige a la página de detalle del contacto después de guardar

**Aspectos Destacados de la Implementación:**

```python
@login_required
def change_subscription_routes(request, subscription_id):
    subscription = get_object_or_404(Subscription, pk=subscription_id)

    if request.POST:
        issues_created = []
        for name, value in list(request.POST.items()):
            if name.startswith("sp-") and value:
                sp = SubscriptionProduct.objects.get(pk=sp_id)
                new_route = Route.objects.get(number=int(value))

                if sp.route != new_route:
                    sp.route = new_route
                    sp.order = None
                    sp.save()

                    # Crear incidencia si es una ruta especial (50-55)
                    issue = create_issue_for_special_route(subscription, new_route.number, request.user)
                    if issue:
                        issues_created.append(new_route.number)

        # Mostrar advertencia si se crearon incidencias
        if issues_created:
            messages.warning(request, _("Rutas actualizadas. Incidencias creadas para rutas especiales: {}"))
```

**Experiencia de Usuario:**

- Visualización clara de información de suscripción (tipo, estado, fechas)
- Advertencia sobre el comportamiento de rutas especiales
- Tabla mostrando rutas actuales con selectores desplegables
- Secciones separadas para mensajes de etiqueta e instrucciones especiales
- Retroalimentación visual para selecciones de rutas especiales

### 3. Vista de Cambio de Ruta Existente Mejorada

**Archivo:** `logistics/views.py`

**Vista:** `change_route(request, route_id)`

**Mejora:**
Actualizada la vista existente de cambio a nivel de ruta para también usar la función utilitaria para creación automática de incidencias.

**Cambios:**

- Agregado seguimiento de creación de incidencias con lista `issues_created`
- Llama a `create_issue_for_special_route()` cuando se cambian rutas
- Muestra mensaje de advertencia listando qué rutas especiales crearon incidencias
- Mantiene toda la funcionalidad existente

### 4. Plantilla Moderna con Integración de Select2

**Archivo:** `logistics/templates/change_subscription_routes.html`

**Funcionalidades:**

**Diseño Visual:**

- Diseño limpio basado en tarjetas con advertencias prominentes
- Resumen de información de suscripción
- Tabla responsiva con encabezados de columna claros
- Indicadores de rutas especiales codificados por color

**Integración de Select2:**

- Usa el plugin Select2 local de admin-lte (no CDN)
- Funcionalidad de escribir para buscar para encontrar rutas rápidamente
- Formato personalizado para rutas especiales (50-55):
  - Icono de triángulo de advertencia (⚠️) en el desplegable
  - Texto en negrita con color de advertencia
  - Distinción visual de rutas regulares

**Retroalimentación en Tiempo Real:**

- JavaScript resalta filas cuando se seleccionan rutas especiales
- Alertas en línea: "Ruta especial - Se creará incidencia"
- La fila de la tabla se vuelve amarilla cuando se elige ruta especial
- Mantiene el resaltado en la carga de página para rutas pre-seleccionadas

**Implementación:**

```javascript
$('select[name^="sp-"]').select2({
  theme: 'bootstrap4',
  width: '100%',
  placeholder: "{% trans 'Seleccionar ruta' %}",
  allowClear: true,
  templateResult: formatRouteOption,
  templateSelection: formatRouteSelection
});

function formatRouteOption(route) {
  var routeNumber = parseInt($(route.element).val());
  var $route = $('<span>' + route.text + '</span>');

  if (routeNumber >= 50 && routeNumber <= 55) {
    $route.prepend('<i class="fas fa-exclamation-triangle text-warning mr-1"></i>');
    $route.addClass('font-weight-bold text-warning');
  }

  return $route;
}
```

### 5. Configuración de URL

**Archivo:** `logistics/urls.py`

**Ruta Agregada:**

```python
re_path(r'^change_subscription_routes/(\d+)/$', change_subscription_routes, name='change_subscription_routes'),
```

**Patrón:** `/logistics/change_subscription_routes/<subscription_id>/`

### 6. Integración de UI en Detalle de Contacto

**Archivo:** `support/templates/contact_detail/tabs/includes/_subscription_card.html`

**Mejora:**
Agregado botón "Cambiar Rutas" al pie de la tarjeta de suscripción.

**Funcionalidades:**

- Visible para grupos Support, Managers y Logistics
- Usa estilo outline-primary con icono de ruta
- Posicionado junto a otras acciones de suscripción
- Enlace directo a la interfaz de cambio de rutas

**Implementación:**

```html
{% if request.user|in_group:"Support" or request.user|in_group:"Managers" or request.user|in_group:"Logistics" %}
  <a href="{% url "change_subscription_routes" subscription.id %}"
     class="btn btn-sm btn-outline-primary mb-1">
    <i class="fas fa-route"></i> {% trans "Cambiar Rutas" %}
  </a>
{% endif %}
```

## Configuración de Settings

**Archivo:** `settings.py`

**Nuevas Constantes:**

```python
# Subcategoría de incidencia para automatización de rutas especiales
ISSUE_SUBCATEGORY_NOT_DELIVERED = "not-delivered"

# Estado de incidencia para incidencias sin asignar
ISSUE_STATUS_UNASSIGNED = "unassigned"
```

**Propósito:**

- Permite que los settings locales sobrescriban con versiones en español
- Proporciona flexibilidad para diferentes instalaciones
- Mantiene consistencia en toda la aplicación

## Detalles Técnicos de Implementación

### Optimización de Consultas de Base de Datos

**Consulta de Productos de Suscripción:**

```python
subscription_products = (
    SubscriptionProduct.objects.filter(subscription=subscription)
    .exclude(product__digital=True)
    .select_related("product", "address", "route")
    .order_by("product__name")
)
```

**Beneficios:**

- Usa `select_related()` para evitar consultas N+1
- Excluye productos digitales (sin entrega física)
- Ordena por nombre de producto para visualización consistente

### Procesamiento de Formulario

**Lógica de Cambio de Ruta:**

```python
if sp.route != new_route:  # Solo actualizar si la ruta realmente cambió
    sp.route = new_route
    sp.order = None  # Resetear orden cuando cambia la ruta
    sp.special_instructions = request.POST.get("instructions-{}".format(sp_id), None)
    sp.label_message = request.POST.get("message-{}".format(sp_id), None)
    sp.save()
```

**Beneficios:**

- Verifica cambios reales antes de guardar
- Resetea orden a None cuando cambia la ruta (se reordenará después)
- Preserva instrucciones especiales y mensajes de etiqueta
- Actualizaciones eficientes de base de datos

### Manejo de Errores

**Degradación Elegante:**

- Retorna None si la subcategoría no existe (no rompe el cambio de ruta)
- Retorna None si el estado no existe (no rompe el cambio de ruta)
- Muestra mensajes de error para rutas inválidas
- Continúa procesando otros productos si uno falla

## Mejoras en la Experiencia de Usuario

### Antes de Este Cambio

**Cambios de Ruta:**

- Tenía que usar vista a nivel de ruta (cambiar todas las suscripciones en una ruta)
- Sin acceso fácil desde la página de detalle del contacto
- Creación manual de incidencias para rutas especiales
- Difícil encontrar rutas específicas en listas largas

**Seguimiento de Incidencias:**

- Creación manual de incidencias logísticas
- Creación inconsistente de incidencias (a menudo olvidada)
- Sin vinculación automática a suscripción

### Después de Este Cambio

**Cambios de Ruta:**

- ✅ Cambios de ruta a nivel de suscripción desde detalle de contacto
- ✅ Acceso con un clic vía botón "Cambiar Rutas"
- ✅ Creación automática de incidencias para rutas especiales
- ✅ Selección de ruta con escritura para buscar con Select2
- ✅ Advertencias visuales para rutas especiales
- ✅ Retroalimentación en tiempo real durante la selección

**Seguimiento de Incidencias:**

- ✅ Creación automática de incidencias para rutas especiales (50-55)
- ✅ Seguimiento consistente con categorización adecuada
- ✅ Vinculación automática a suscripción y contacto
- ✅ Pista de auditoría clara (usuario registrado como manager)

## Ejemplo de Flujo de Trabajo

### Caso de Uso Típico

1. **Operador accede a página de detalle de contacto**
   - Ve suscripción con productos en varias rutas

2. **Hace clic en botón "Cambiar Rutas"**
   - Abre interfaz dedicada de cambio de rutas
   - Ve todos los productos de suscripción con rutas actuales

3. **Cambia ruta para un producto**
   - Escribe número de ruta en desplegable Select2 (ej., "51")
   - Ve icono de advertencia y resaltado amarillo
   - Aparece alerta: "Ruta especial - Se creará incidencia"

4. **Envía formulario**
   - Las rutas se actualizan
   - Incidencia creada automáticamente para ruta 51
   - Mensaje de advertencia: "Rutas actualizadas. Incidencias creadas para rutas especiales: 51"
   - Redirigido a página de detalle de contacto

5. **La incidencia se rastrea**
   - Incidencia logística aparece en lista de incidencias
   - Categoría: Logística
   - Subcategoría: no-entregado
   - Estado: sin-asignar
   - Notas: "Generado automáticamente por cambio de ruta a ruta especial (ruta 51)"

## Beneficios

### Eficiencia Operacional

1. **Ahorro de Tiempo:**
   - Sin creación manual de incidencias para rutas especiales
   - Búsqueda rápida de rutas con escritura para buscar
   - Cambios masivos para todos los productos en suscripción

2. **Reducción de Errores:**
   - Creación automática de incidencias previene olvidos de seguimiento
   - Advertencias visuales previenen asignaciones accidentales de rutas especiales
   - Categorización consistente de incidencias

3. **Mejor Seguimiento:**
   - Todos los cambios de rutas especiales rastreados automáticamente
   - Pista de auditoría clara con atribución de usuario
   - Vinculado a suscripción para contexto

### Experiencia de Usuario

1. **Descubribilidad:**
   - Botón prominente en tarjeta de suscripción
   - Ruta de navegación clara
   - Interfaz intuitiva

2. **Retroalimentación Visual:**
   - Iconos de advertencia para rutas especiales
   - Selecciones codificadas por color
   - Alertas en tiempo real

3. **Eficiencia:**
   - Escritura para buscar para encontrar rutas rápidamente
   - Actualizaciones masivas en un solo formulario
   - Acceso directo desde detalle de contacto

## Archivos modificados y nuevos

### Archivos Nuevos

- `logistics/utils.py` - Función utilitaria para creación de incidencias
- `logistics/templates/change_subscription_routes.html` - Interfaz de cambio de rutas

### Archivos Modificados

- `logistics/views.py` - Agregada vista `change_subscription_routes`, mejorada `change_route`
- `logistics/urls.py` - Agregado patrón de URL para nueva vista
- `support/templates/contact_detail/tabs/includes/_subscription_card.html` - Agregado botón
- `settings.py` - Agregadas constantes de configuración

## Recomendaciones de Pruebas

### Pruebas Manuales

1. **Funcionalidad de Cambio de Ruta:**
   - Cambiar rutas para productos de suscripción
   - Verificar que las rutas se actualicen correctamente
   - Verificar que el orden se resetee a None

2. **Automatización de Rutas Especiales:**
   - Cambiar ruta al rango 50-55
   - Verificar que la incidencia se cree automáticamente
   - Verificar que la incidencia tenga categoría, subcategoría, estado correctos
   - Verificar que las notas contengan el número de ruta

3. **Integración de Select2:**
   - Escribir números de ruta para buscar
   - Verificar que el desplegable filtre correctamente
   - Verificar que las rutas especiales muestren iconos de advertencia
   - Probar selección y limpieza

4. **Retroalimentación Visual:**
   - Seleccionar ruta especial (50-55)
   - Verificar que la fila se resalte en amarillo
   - Verificar que aparezca mensaje de alerta
   - Verificar que la advertencia persista en carga de página

5. **Permisos:**
   - Probar con grupos Support, Managers, Logistics
   - Verificar que el botón aparezca para usuarios autorizados
   - Probar con usuarios no autorizados (el botón no debería aparecer)

### Casos Límite

1. **Sin Cambio de Ruta:**
   - Seleccionar la misma ruta que la actual
   - Verificar que no haya actualizaciones innecesarias

2. **Subcategoría/Estado Faltante:**
   - Probar con registros de base de datos faltantes
   - Verificar degradación elegante (sin error)

3. **Múltiples Rutas Especiales:**
   - Cambiar múltiples productos a diferentes rutas especiales
   - Verificar que se creen todas las incidencias
   - Verificar que el mensaje de advertencia liste todas las rutas

4. **Productos Digitales:**
   - Verificar que los productos digitales se excluyan de la interfaz

## Mejoras Futuras

### Mejoras Potenciales

1. **Asignación Masiva de Rutas:**
   - Botón "Aplicar a todos" para establecer la misma ruta para todos los productos
   - Plantillas de rutas para configuraciones comunes

2. **Historial de Rutas:**
   - Rastrear historial de cambios de ruta
   - Mostrar rutas anteriores en interfaz

3. **Filtrado Avanzado:**
   - Filtrar productos por ruta actual
   - Mostrar solo productos que necesitan cambios de ruta

4. **Vista Previa de Incidencia:**
   - Mostrar vista previa de incidencia que se creará
   - Permitir personalización antes de creación

5. **Recomendaciones de Rutas:**
   - Sugerir rutas basadas en dirección
   - Mostrar rutas cercanas para consideración

## Notas de Migración

### Para Instalaciones Existentes

1. **Configuración de Settings:**
   - Agregar `ISSUE_SUBCATEGORY_NOT_DELIVERED` a local_settings.py
   - Agregar `ISSUE_STATUS_UNASSIGNED` a local_settings.py
   - Sobrescribir con versiones en español si es necesario

2. **Requisitos de Base de Datos:**
   - Asegurar que exista subcategoría "not-delivered" (o localizada)
   - Asegurar que exista estado "unassigned" (o localizado)
   - No se requieren migraciones

3. **Permisos:**
   - Verificar que existan grupos Support, Managers, Logistics
   - Ajustar verificaciones de grupo en plantilla si es necesario

## Conclusión

Esta implementación proporciona una solución integral para la gestión de rutas a nivel de suscripción con automatización inteligente para el seguimiento de rutas especiales. La combinación de UI eficiente, creación automática de incidencias y retroalimentación visual clara mejora significativamente el flujo de trabajo logístico mientras reduce el trabajo manual y los errores potenciales.

El uso de constantes de settings asegura flexibilidad entre diferentes instalaciones, y la integración de Select2 proporciona una interfaz moderna y amigable para la selección rápida de rutas. La creación automática de incidencias asegura que todas las asignaciones de rutas especiales se rastreen adecuadamente sin requerir intervención manual de los operadores.
