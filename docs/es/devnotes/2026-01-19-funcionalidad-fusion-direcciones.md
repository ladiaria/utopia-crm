# Funcionalidad de Fusión de Direcciones

**Fecha:** 2026-01-19
**Tipo:** Implementación de Funcionalidad
**Componente:** Logística, Gestión de Direcciones
**Impacto:** Calidad de Datos, Experiencia de Usuario, Gestión de Contactos

## Resumen

Se implementó un sistema completo de fusión de direcciones que permite a los usuarios con los permisos adecuados identificar y fusionar direcciones duplicadas. La funcionalidad incluye detección inteligente de similitud, selección amigable mediante menús desplegables, comparación campo por campo, y transferencia automática de objetos relacionados (productos de suscripción, incidencias y tareas programadas).

## Motivación

Las direcciones duplicadas en el sistema crean varios problemas:

1. **Inconsistencia de datos:** Múltiples direcciones para la misma ubicación física
2. **Inexactitud en reportes:** Productos de suscripción, incidencias y tareas dispersos entre direcciones duplicadas
3. **Confusión del usuario:** Personal inseguro sobre qué dirección usar para entregas o comunicaciones
4. **Dificultad de limpieza manual:** Sin herramienta integrada para fusionar direcciones duplicadas de forma segura

Anteriormente, los usuarios tenían que:

- Actualizar manualmente todos los objetos relacionados (productos de suscripción, incidencias, tareas) para que apunten a una dirección
- Eliminar la dirección duplicada a través de la interfaz de administración
- Arriesgar pérdida de datos si las relaciones no se transferían correctamente
- Invertir tiempo significativo en limpieza manual de datos

Este flujo de trabajo era propenso a errores, consumía mucho tiempo y requería conocimiento a nivel de base de datos.

## Implementación

### 1. Mejora del Modelo Address

**Archivo:** `core/models.py`

Se agregó el método `merge_other_address_into_this()` al modelo Address:

```python
def merge_other_address_into_this(
    self,
    source: "Address",
    address_1: str = None,
    address_2: str = None,
    city: str = None,
    email: str = None,
    address_type: str = None,
    notes: str = None,
    default: bool = None,
    name: str = None,
    state_id: int = None,
    country_id: int = None,
    city_fk_id: int = None,
    latitude: float = None,
    longitude: float = None,
    google_maps_url: str = None,
) -> list:
```

**Características Clave:**

- **Anulación campo por campo:** Permite selección manual de qué valores de campo conservar
- **Transferencia de objetos relacionados:** Mueve automáticamente todos los productos de suscripción, incidencias y tareas programadas
- **Fusión de notas:** Combina notas de ambas direcciones con registro de auditoría
- **Eliminación de origen:** Elimina de forma segura la dirección de origen después de una fusión exitosa
- **Manejo de errores:** Devuelve lista de errores si la fusión falla

**Objetos Relacionados Transferidos:**

1. **SubscriptionProducts:** `source.subscriptionproduct_set.update(address=self)`
2. **Issues:** `source.issue_set.update(address=self)`
3. **ScheduledTasks:** `source.scheduledtask_set.update(address=self)`

### 2. Sistema de Permisos

**Archivo:** `core/models.py`

Se agregó permiso personalizado al modelo Address:

```python
class Meta:
    verbose_name = _("address")
    verbose_name_plural = _("addresses")
    permissions = [
        ("can_merge_addresses", _("Can merge addresses")),
    ]
```

**Control de Acceso:**

- Solo usuarios con permiso `core.can_merge_addresses` pueden acceder a la funcionalidad de fusión
- Verificación de permiso aplicada a nivel de vista con decorador `@permission_required`
- Previene que usuarios no autorizados fusionen direcciones

### 3. Vistas Basadas en Clases

**Archivo:** `logistics/views.py`

Se implementaron dos CBVs con BreadcrumbsMixin para navegación adecuada:

#### MergeCompareAddressesView (TemplateView)

**Operación de modo dual:**

**Modo 1 - Selección basada en contacto (con contact_id):**

- Muestra menús desplegables con todas las direcciones de un contacto específico
- Muestra información descriptiva de direcciones (ID, calle, ciudad, estado, país)
- Validación JavaScript previene seleccionar la misma dirección dos veces

**Modo 2 - Comparación directa (con address_1 y address_2):**

- Muestra comparación lado a lado de dos direcciones
- Filas codificadas por color (verde = coincide, amarillo = diferente)
- Muestra conteos de objetos relacionados para cada dirección
- Calcula puntuación de similitud usando difflib.SequenceMatcher

**Detección de Similitud:**

```python
# Normalizar cadenas para comparación
addr1_normalized = address1.address_1.lower().strip()
addr2_normalized = address2.address_1.lower().strip()

# Calcular ratio de similitud (0.0 a 1.0)
similarity_ratio = SequenceMatcher(None, addr1_normalized, addr2_normalized).ratio()

# Mostrar advertencia si similitud es menor a 40%
if similarity_ratio < 0.4:
    show_similarity_warning = True
```

**Ejemplos:**

- "Liber Arce 3177" vs "liber arse 3177" → ~90% similar (sin advertencia)
- "Jujuy 1236" vs "Rivera 1246" → ~30% similar (advertencia mostrada)

**Migas de Pan:**

- Paso 1 (con contacto): Inicio → Lista de contactos → [Nombre Contacto] → Fusionar direcciones
- Paso 2 (comparando): Inicio → Lista de contactos → [Nombre Contacto] → Fusionar direcciones (si las direcciones tienen contacto)
- Acceso directo: Inicio → Fusionar direcciones

#### ProcessMergeAddressesView (View)

**Manejador POST para ejecutar la fusión:**

- Valida IDs de direcciones del envío del formulario
- Extrae selecciones de campos de datos POST
- Maneja conversión de formato de coordenadas (coma a punto como separador decimal)
- Ejecuta fusión mediante método del modelo
- Proporciona retroalimentación de éxito/error mediante mensajes de Django
- Redirige a página de detalle de contacto o página de fusión

**Manejo de Coordenadas:**

```python
# Convertir latitud/longitud, manejando tanto coma como punto como separador decimal
if new_latitude and new_latitude != "":
    new_latitude = float(new_latitude.replace(',', '.'))
```

### 4. Plantilla Mejorada

**Archivo:** `logistics/templates/merge_compare_addresses.html`

**Paso 1 - Selección de Direcciones:**

**Flujo basado en contacto:**

- Banner informativo mostrando nombre e ID del contacto
- Dos menús desplegables con opciones descriptivas de direcciones
- Detección de duplicados JavaScript con mensaje de advertencia
- Botón cancelar (regresa a detalle de contacto)
- Botón comparar (procede al paso 2)

**Flujo de ID manual:**

- Entradas numéricas para IDs de direcciones
- Botón cancelar (regresa a inicio)
- Botón comparar (procede al paso 2)

**Paso 2 - Comparación y Fusión:**

**Advertencia de Similitud:**

```html
{% if show_similarity_warning %}
  <div class="alert alert-warning alert-dismissible fade show" role="alert">
    <h5><i class="fas fa-exclamation-triangle"></i> {% trans "Advertencia: Las direcciones parecen ser muy diferentes" %}</h5>
    <p class="mb-0">
      {% trans "Las direcciones que está fusionando parecen ser significativamente diferentes" %} ({{ similarity_percentage }}% {% trans "similar" %}).
      {% trans "Por favor verifique que ha seleccionado las direcciones correctas antes de proceder. La fusión de direcciones no relacionadas no se puede deshacer." %}
    </p>
  </div>
{% endif %}
```

**Tabla de Comparación:**

- **Filas codificadas por color:** Verde para valores coincidentes, amarillo para diferencias
- **Etiquetas de campo con texto de ayuda:** Explicaciones descriptivas para cada campo
- **Selectores desplegables:** Elija qué valor conservar para cada campo
- **Conteos de objetos relacionados:** Muestra productos de suscripción, incidencias y tareas para cada dirección
- **Manejo especial:** Coordenadas, notas, campos booleanos tienen UI personalizada

**Ejemplos de Texto de Ayuda:**

- Address 1: "Dirección de calle"
- Address 2: "Apartamento, suite, etc."
- Name: "Nombre de referencia para esta dirección. Puede hacer referencia a la persona o a la dirección misma."
- State: "Estado/Provincia/Departamento"
- Coordinates: "Coordenadas GPS (lat, long)"

**Botones de Acción:**

- Botón cancelar (regresa a detalle de contacto o página de fusión)
- Botón ejecutar fusión (rojo, estilo de peligro)

**Sección de Información:**

- Alerta de información importante en la parte inferior
- Explica comportamiento y consecuencias de la fusión
- Advierte que la acción no se puede deshacer

### 5. Configuración de URL

**Archivo:** `logistics/urls.py`

Se agregaron dos patrones de URL:

```python
path("merge_addresses/", MergeCompareAddressesView.as_view(), name="merge_compare_addresses"),
path("process_merge_addresses/", ProcessMergeAddressesView.as_view(), name="process_merge_addresses"),
```

### 6. Integración en Vista General de Contacto

**Archivo:** `support/templates/contact_detail/tabs/_overview.html`

Se agregó botón de fusión en sección de direcciones:

```html
<div class="d-flex justify-content-between align-items-center mb-2">
  <h6 class="text-muted mb-0"><i class="fas fa-map-marker-alt"></i> {% trans "Direcciones" %}</h6>
  {% if addresses|length > 1 and perms.core.can_merge_addresses %}
    <a href="{% url 'merge_compare_addresses' %}?contact_id={{ contact.id }}" class="btn btn-xs btn-warning" title="{% trans "Fusionar direcciones duplicadas" %}">
      <i class="fas fa-compress-arrows-alt"></i> {% trans "Fusionar" %}
    </a>
  {% endif %}
</div>
```

**Comportamiento del Botón:**

- Solo aparece cuando el contacto tiene 2+ direcciones
- Solo visible para usuarios con permiso `can_merge_addresses`
- Pasa contact_id para activar modo de selección desplegable
- Color de advertencia (amarillo) indica acción potencialmente destructiva

## Detalles Técnicos

### Algoritmo de Similitud

Usa `difflib.SequenceMatcher` integrado en Python:

```python
from difflib import SequenceMatcher

similarity_ratio = SequenceMatcher(None, addr1_normalized, addr2_normalized).ratio()
```

**Umbral:** 40% de similitud

- Debajo de 40%: Advertencia mostrada
- Encima de 40%: Sin advertencia (probablemente errores tipográficos o diferencias menores)

**Normalización:**

- Convertir a minúsculas
- Eliminar espacios en blanco
- Comparar secuencias de caracteres

### Lógica de Anulación de Campos

Todos los campos de dirección pueden seleccionarse individualmente:

- **Campos de texto:** address_1, address_2, city, email, name, google_maps_url
- **Claves foráneas:** state_id, country_id, city_fk_id
- **Coordenadas:** latitude, longitude (con manejo de coma/punto)
- **Booleano:** default
- **Campo de elección:** address_type
- **Área de texto:** notes (con opción de fusión)

### Fusión de Notas

Tres opciones para notas:

1. **Fusión automática:** Combina ambos conjuntos de notas con registro de auditoría
2. **Conservar notas de dirección 1:** Usa solo notas de primera dirección
3. **Conservar notas de dirección 2:** Usa solo notas de segunda dirección

**Formato de fusión automática:**

```text
Combinado de [source_id] en [fecha]
[notas objetivo]

Notas importadas de [source_id]
[notas origen]
```

### Transferencia de Objetos Relacionados

**Operaciones de base de datos:**

```python
# Transferir productos de suscripción
source.subscriptionproduct_set.update(address=self)

# Transferir incidencias
source.issue_set.update(address=self)

# Transferir tareas programadas
source.scheduledtask_set.update(address=self)
```

**Operación atómica:**

- Todas las transferencias ocurren en una sola transacción
- Si alguna falla, toda la fusión se revierte
- Dirección de origen solo se elimina después de transferencia exitosa

## Beneficios

### 1. Mejora de Calidad de Datos

- **Eliminar duplicados:** Limpiar registros de direcciones duplicadas
- **Consolidar relaciones:** Todos los objetos relacionados en un solo lugar
- **Reportes precisos:** Conteos correctos para productos de suscripción, incidencias y tareas
- **Datos consistentes:** Única fuente de verdad para cada dirección física

### 2. Experiencia de Usuario

- **Interfaz intuitiva:** Selección desplegable con opciones descriptivas
- **Retroalimentación visual:** Tabla de comparación codificada por colores
- **Características de seguridad:** Advertencias de similitud, prevención de duplicados
- **Navegación clara:** Migas de pan y botones de cancelar en cada paso
- **Orientación útil:** Descripciones de campos e instrucciones

### 3. Eficiencia de Flujo de Trabajo

- **Acceso con un clic:** Botón de fusión en vista general de contacto
- **Proceso guiado:** Flujo de trabajo de dos pasos con progresión clara
- **Operaciones por lotes:** Seleccionar campos a conservar en una sola acción
- **Limpieza automática:** Objetos relacionados transferidos automáticamente

### 4. Seguridad y Confiabilidad

- **Basado en permisos:** Solo usuarios autorizados pueden fusionar
- **Detección de similitud:** Advierte sobre direcciones muy diferentes
- **Prevención de duplicados:** Validación JavaScript en selección
- **Registro de auditoría:** Notas incluyen historial de fusión
- **Manejo de errores:** Reporte completo de errores

## Uso

### Para Usuarios con Permiso

**Acceso vía Vista General de Contacto:**

1. Navegar a página de detalle de contacto
2. Desplazarse a sección de Direcciones
3. Hacer clic en botón "Fusionar" (aparece cuando contacto tiene 2+ direcciones)
4. Seleccionar dos direcciones de menús desplegables
5. Hacer clic en "Comparar direcciones"
6. Revisar comparación lado a lado
7. Seleccionar qué valores conservar para cada campo
8. Elegir qué dirección conservar
9. Hacer clic en "Ejecutar fusión"

**Acceso Directo:**

1. Navegar a `/logistics/merge_addresses/`
2. Ingresar dos IDs de direcciones manualmente
3. Hacer clic en "Comparar direcciones"
4. Seguir pasos 6-9 anteriores

### Interpretación de Advertencia de Similitud

**Alta similitud (>60%):** Probablemente errores tipográficos o diferencias menores

- Ejemplo: "Liber Arce 3177" vs "liber arse 3177"
- Seguro proceder con fusión

**Similitud media (40-60%):** Revisar cuidadosamente

- Puede ser misma ubicación con formato diferente
- Verificar antes de proceder

**Baja similitud (<40%):** Advertencia mostrada

- Ejemplo: "Jujuy 1236" vs "Rivera 1246"
- Probablemente direcciones diferentes
- Verificar dos veces antes de fusionar

### Estrategia de Selección de Campos

**Enfoque recomendado:**

1. **Revisar codificación de colores:** Verde = igual, amarillo = diferente
2. **Verificar conteos de objetos relacionados:** Considerar qué dirección tiene más datos
3. **Verificar coordenadas:** Asegurar que se conserve geolocalización correcta
4. **Fusionar notas:** Usar fusión automática para preservar toda la información
5. **Seleccionar dirección principal:** Elegir dirección con datos más completos

## Pruebas

### Pasos de Verificación

1. **Probar sistema de permisos:**
   - Iniciar sesión como usuario sin permiso
   - Verificar que botón de fusión no aparece
   - Verificar que acceso directo a URL es denegado

2. **Probar flujo basado en contacto:**
   - Navegar a contacto con 2+ direcciones
   - Hacer clic en botón fusionar
   - Verificar que desplegables muestran todas las direcciones
   - Intentar seleccionar misma dirección dos veces
   - Verificar que aparece advertencia y botón se deshabilita

3. **Probar detección de similitud:**
   - Comparar direcciones muy similares
   - Verificar que no aparece advertencia
   - Comparar direcciones muy diferentes
   - Verificar que aparece advertencia con porcentaje

4. **Probar selección de campos:**
   - Seleccionar diferentes valores para cada campo
   - Ejecutar fusión
   - Verificar que se conservaron valores correctos

5. **Probar transferencia de objetos relacionados:**
   - Anotar conteos de productos de suscripción antes de fusión
   - Ejecutar fusión
   - Verificar que todos los productos se transfirieron a dirección objetivo
   - Repetir para incidencias y tareas programadas

6. **Probar manejo de coordenadas:**
   - Fusionar direcciones con separadores decimales de coma
   - Verificar que coordenadas se guardaron correctamente
   - Verificar que georef_point se actualiza

7. **Probar migas de pan:**
   - Verificar que migas de pan muestran contexto de contacto
   - Probar navegación mediante enlaces de migas de pan
   - Verificar que migas de pan se actualizan entre pasos

8. **Probar botones de cancelar:**
   - Hacer clic en cancelar en paso 1
   - Verificar que regresa a detalle de contacto
   - Hacer clic en cancelar en paso 2
   - Verificar que regresa a página apropiada

## Archivos Modificados

### Modelos Core

- `core/models.py` - Agregado método merge_other_address_into_this() y permiso can_merge_addresses

### Vistas Logistics

- `logistics/views.py` - Agregadas MergeCompareAddressesView y ProcessMergeAddressesView con BreadcrumbsMixin

### Plantillas Logistics

- `logistics/templates/merge_compare_addresses.html` - Nueva plantilla para UI de fusión de direcciones

### URLs Logistics

- `logistics/urls.py` - Agregados patrones de URL para vistas de fusión

### Plantillas Support

- `support/templates/contact_detail/tabs/_overview.html` - Agregado botón de fusión a sección de direcciones

## Impacto en Base de Datos

**No se requieren cambios de esquema** - usa campos y relaciones existentes del modelo Address:

- Modelo Address ya tiene todos los campos necesarios
- Modelos relacionados (SubscriptionProduct, Issue, ScheduledTask) ya tienen ForeignKey a Address
- Permiso agregado vía Meta.permissions (crea entrada en base de datos en migración)

**Migración necesaria:**

```bash
python manage.py makemigrations
python manage.py migrate
```

Esto crea el permiso `can_merge_addresses` en la base de datos.

## Compatibilidad Hacia Atrás

- Toda funcionalidad existente de direcciones preservada
- Sin cambios disruptivos en API del modelo Address
- Funcionalidad de fusión es opcional (requiere permiso)
- Direcciones existentes no afectadas
- Relaciones de objetos relacionados sin cambios

## Consideraciones de Seguridad

1. **Acceso basado en permisos:** Solo usuarios con `can_merge_addresses` pueden acceder
2. **Protección CSRF:** Todos los formularios incluyen tokens CSRF
3. **Validación de entrada:** IDs de direcciones validados antes de procesamiento
4. **Manejo de errores:** Fallo elegante con mensajes amigables para usuario
5. **Registro de auditoría:** Historial de fusión registrado en notas

## Mejoras Futuras

Mejoras potenciales para iteraciones futuras:

1. **Fusión masiva:** Fusionar múltiples pares de direcciones en una sola operación
2. **Auto-detección:** Sugerir duplicados potenciales basados en similitud
3. **Historial de fusión:** Tabla dedicada para rastrear todas las fusiones
4. **Funcionalidad de deshacer:** Capacidad de revertir fusión dentro de ventana de tiempo
5. **Similitud avanzada:** Usar bibliotecas de análisis de direcciones para mejor detección
6. **Vista previa de fusión:** Mostrar qué sucederá antes de ejecutar
7. **Limpieza por lotes:** Encontrar y fusionar todos los duplicados de un contacto
8. **Endpoint API:** Acceso programático a funcionalidad de fusión

## Notas

- Detección de similitud usa difflib.SequenceMatcher (biblioteca integrada de Python)
- Conversión de coordenadas maneja tanto coma como punto como separadores decimales
- Plantilla usa Bootstrap 4 para diseño responsivo
- Todo el texto es traducible usando sistema i18n de Django
- BreadcrumbsMixin proporciona navegación consistente en toda la aplicación
- Botones de cancelar redirigen inteligentemente basándose en contexto

## Características Relacionadas

- Gestión de contactos y vistas de detalle
- Sistema de georreferenciación de direcciones
- Gestión de productos de suscripción
- Sistema de seguimiento de incidencias
- Gestión de tareas programadas
- Sistema de permisos y roles de usuario
