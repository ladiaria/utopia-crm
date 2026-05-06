# Mejoras en Filtros de Registro de Ventas

**Fecha:** 2025-12-16
**Tipo:** Mejora de Funcionalidad, Mejora de UI
**Componente:** Registros de Ventas, Filtrado, Consola de Vendedor
**Impacto:** Analítica de Ventas, Reportes, Experiencia de Usuario

## Resumen

Se mejoró la funcionalidad de filtrado de registros de ventas tanto para vendedores como para gerentes, agregando filtros de fecha de inicio de suscripción y filtros de productos. Se implementó Select2 para todos los campos de selección múltiple para proporcionar una mejor experiencia de usuario con menús desplegables buscables y capacidades de selección múltiple.

## Motivación

Las vistas de filtro de registros de ventas tenían capacidades de filtrado limitadas:

1. **Faltaban filtros de fecha de suscripción:** Los usuarios solo podían filtrar por fecha de transacción (cuando se registró la venta), pero no por fecha de inicio de suscripción (cuando la suscripción realmente comienza)
2. **Sin filtrado por producto:** Los usuarios no podían filtrar registros de ventas por productos específicos, dificultando el análisis del rendimiento de ventas para productos particulares
3. **Mala UX para selecciones múltiples:** Los menús desplegables HTML estándar de selección múltiple son difíciles de usar, especialmente con muchas opciones
4. **Distinción de fechas poco clara:** Los filtros de fecha existentes no estaban claramente etiquetados como "fecha de transacción" vs "fecha de inicio de suscripción"

Esto dificultaba que vendedores y gerentes pudieran:

- Encontrar registros de ventas para suscripciones que comienzan en un rango de fechas específico
- Analizar el rendimiento de ventas por producto
- Filtrar por múltiples vendedores, métodos de pago o productos eficientemente

## Implementación

### 1. Filtros de Fecha de Inicio de Suscripción Agregados

**Archivo:** `support/filters.py`

Se agregaron filtros de fecha de inicio de suscripción mínima/máxima a ambas clases de filtro:

**SalesRecordFilter (para gerentes):**

```python
start_date__gte = django_filters.DateFilter(
    field_name='subscription__start_date', lookup_expr='gte',
    widget=forms.TextInput(attrs={'autocomplete': 'off'}),
    label=_('Subscription start date (min)')
)
start_date__lte = django_filters.DateFilter(
    field_name='subscription__start_date', lookup_expr='lte',
    widget=forms.TextInput(attrs={'autocomplete': 'off'}),
    label=_('Subscription start date (max)')
)
```

**SalesRecordFilterForSeller (para vendedores):**

Los mismos filtros se agregaron para asegurar paridad de funcionalidades entre las vistas de vendedor y gerente.

**Beneficios:**

- Filtrar ventas por cuando las suscripciones realmente comienzan
- Encontrar suscripciones que comienzan en rangos de fechas específicos
- Separado de la fecha de transacción para análisis más claros

### 2. Filtro de Productos Agregado

**Archivo:** `support/filters.py`

Se agregó filtro de selección múltiple de productos a ambas clases de filtro:

```python
products = django_filters.ModelMultipleChoiceFilter(
    queryset=Product.objects.filter(
        type__in=['S', 'O'], active=True
    ).order_by('name'),
    field_name='products',
    label=_('Products')
)
```

**Criterios del Filtro:**

- Solo muestra productos activos
- Incluye productos de tipo Suscripción ('S') y Otros ('O')
- Ordenados alfabéticamente por nombre
- Soporta selección múltiple de productos

**Beneficios:**

- Analizar rendimiento de ventas por productos específicos
- Filtrar por múltiples productos simultáneamente
- Solo muestra productos relevantes y activos

### 3. Diseño de Plantilla Mejorado

**Archivo:** `support/templates/sales_record_filter.html`

Se reorganizó el formulario de filtro en dos filas para mejor organización:

**Primera Fila - Filtros de Fecha (4 columnas):**

- Fecha de transacción (mín) - *renombrado de "Fecha Mín." para claridad*
- Fecha de transacción (máx) - *renombrado de "Fecha Máx." para claridad*
- Fecha de inicio de suscripción (mín) - *NUEVO*
- Fecha de inicio de suscripción (máx) - *NUEVO*

**Segunda Fila - Otros Filtros:**

- Método de Pago
- Productos - *NUEVO*
- Vendedor (solo gerentes)
- Validado (solo gerentes)

**Mejoras:**

- Distinción clara entre fecha de transacción y fecha de inicio de suscripción
- Mejor organización visual con agrupación lógica
- Más espacio para cada campo de filtro
- El diseño responsivo mantiene la usabilidad en todos los tamaños de pantalla

### 4. Select2 Implementado para Selecciones Múltiples

**Archivo:** `support/templates/sales_record_filter.html`

Se agregó la librería Select2 e inicialización para todos los campos de selección múltiple:

**CSS Agregado:**

```html
<link href="{% static 'admin-lte/plugins/select2/css/select2.min.css' %}" rel="stylesheet" />
<link href="{% static 'admin-lte/plugins/select2-bootstrap4-theme/select2-bootstrap4.min.css' %}" rel="stylesheet" />
```

**Inicialización JavaScript:**

```javascript
// Filtro de vendedor (solo gerentes)
$('#id_seller').select2({
  theme: 'bootstrap4',
  width: '100%',
  placeholder: '{% trans "Select sellers" %}',
  allowClear: true
});

// Filtro de método de pago
$('#id_payment_method').select2({
  theme: 'bootstrap4',
  width: '100%',
  placeholder: '{% trans "Select payment methods" %}',
  allowClear: true
});

// Filtro de productos
$('#id_products').select2({
  theme: 'bootstrap4',
  width: '100%',
  placeholder: '{% trans "Select products" %}',
  allowClear: true
});
```

**Características de Select2:**

- **Menús desplegables buscables:** Escribir para filtrar opciones
- **Chips de selección múltiple:** Representación visual de elementos seleccionados
- **Botón de limpiar:** Limpiar rápidamente todas las selecciones con botón X
- **Tema Bootstrap 4:** Estilo consistente con AdminLTE
- **Responsivo:** Ancho completo, se adapta al tamaño de pantalla
- **Placeholders traducibles:** Sugerencias amigables para el usuario

## Detalles Técnicos

### Configuración de Campos de Filtro

**Filtros de Fecha de Transacción:**

- Campo: `date_time__date` (SalesRecord.date_time)
- Propósito: Cuando la venta fue registrada en el sistema
- Caso de uso: Encontrar ventas realizadas en fechas específicas

**Filtros de Fecha de Inicio de Suscripción:**

- Campo: `subscription__start_date` (Subscription.start_date)
- Propósito: Cuando la suscripción realmente comienza
- Caso de uso: Encontrar suscripciones que comienzan en rangos de fechas futuras/pasadas

**Filtro de Productos:**

- Campo: `products` (relación ManyToMany)
- Queryset: Productos activos de tipo 'S' u 'O'
- Soporta selección múltiple
- Caso de uso: Analizar ventas por productos específicos

### Implementación de Select2

Se usaron recursos del plugin AdminLTE local en lugar de CDN:

- `admin-lte/plugins/select2/css/select2.min.css`
- `admin-lte/plugins/select2-bootstrap4-theme/select2-bootstrap4.min.css`
- `admin-lte/plugins/select2/js/select2.full.min.js`

**Configuración:**

- `theme: 'bootstrap4'` - Coincide con el estilo de AdminLTE
- `width: '100%'` - Ancho completo responsivo
- `allowClear: true` - Habilita botón X para limpiar selecciones
- Placeholders traducibles para internacionalización

## Beneficios

### 1. Capacidades de Filtrado Mejoradas

- **Filtrado por fecha de inicio de suscripción:** Encontrar suscripciones que comienzan en rangos de fechas específicos
- **Filtrado basado en productos:** Analizar rendimiento de ventas por producto
- **Múltiples criterios:** Combinar filtros para resultados precisos

### 2. Experiencia de Usuario Mejorada

- **Menús desplegables buscables:** Escribir para encontrar opciones rápidamente
- **Selección múltiple visual:** Ver elementos seleccionados como chips
- **Limpiar selecciones fácilmente:** Botón X para eliminar todas las selecciones
- **Mejor organización:** Agrupación lógica de filtros

### 3. Mejor Analítica

- **Tipos de fecha separados:** Distinguir entre fechas de transacción y suscripción
- **Análisis de productos:** Rastrear qué productos se venden mejor
- **Filtrado flexible:** Combinar múltiples filtros para reportes detallados

### 4. Interfaz Consistente

- **Mismas características para vendedores y gerentes:** Paridad de funcionalidades entre vistas
- **Tema Bootstrap 4:** Consistente con el resto de la aplicación
- **Diseño responsivo:** Funciona en todos los tamaños de pantalla

## Uso

### Para Vendedores

Acceso vía: **Consola de Vendedor > Mis Ventas**

**Nuevas Opciones de Filtrado:**

1. **Fecha de inicio de suscripción:** Filtrar por cuando comienzan las suscripciones
2. **Productos:** Filtrar por productos específicos vendidos
3. **Selects mejorados:** Usar menús desplegables buscables para métodos de pago y productos

**Casos de Uso de Ejemplo:**

- Encontrar todas las ventas con suscripciones que comienzan el próximo mes
- Ver ventas de un producto específico
- Filtrar por múltiples métodos de pago

### Para Gerentes

Acceso vía: **Gestión de Campañas > Registro de Ventas**

**Nuevas Opciones de Filtrado:**

1. **Fecha de inicio de suscripción:** Filtrar por cuando comienzan las suscripciones
2. **Productos:** Filtrar por productos específicos vendidos
3. **Selects mejorados:** Usar menús desplegables buscables para vendedores, métodos de pago y productos

**Casos de Uso de Ejemplo:**

- Analizar ventas por producto entre todos los vendedores
- Encontrar suscripciones que comienzan en Q1 2026
- Filtrar por múltiples vendedores y productos simultáneamente
- Generar reportes para combinaciones específicas de productos

## Pruebas

### Pasos de Verificación

1. **Probar filtros de fecha de inicio de suscripción:**
   - Ir a la página de Registros de Ventas
   - Establecer "Fecha de inicio de suscripción (mín)" a una fecha futura
   - Verificar que solo aparezcan ventas con suscripciones que comienzan en/después de esa fecha
   - Establecer "Fecha de inicio de suscripción (máx)" a una fecha pasada
   - Verificar que solo aparezcan ventas con suscripciones que comienzan en/antes de esa fecha

2. **Probar filtro de productos:**
   - Seleccionar uno o más productos del menú desplegable de Productos
   - Verificar que solo aparezcan ventas que contienen esos productos
   - Limpiar selección y verificar que aparezcan todas las ventas nuevamente

3. **Probar funcionalidad de Select2:**
   - Hacer clic en cualquier campo de selección múltiple (vendedor, método de pago, productos)
   - Escribir para buscar opciones
   - Seleccionar múltiples elementos
   - Verificar que los elementos seleccionados aparezcan como chips
   - Hacer clic en el botón X para limpiar todas las selecciones

4. **Probar filtros combinados:**
   - Establecer rango de fecha de transacción
   - Establecer rango de fecha de inicio de suscripción
   - Seleccionar productos específicos
   - Verificar que los resultados coincidan con todos los criterios

5. **Probar diseño responsivo:**
   - Ver en diferentes tamaños de pantalla
   - Verificar que el diseño permanezca usable
   - Verificar que los menús desplegables de Select2 funcionen en móvil

## Archivos Modificados

- `support/filters.py` - Agregados filtros start_date y products a SalesRecordFilter y SalesRecordFilterForSeller
- `support/templates/sales_record_filter.html` - Reorganizado diseño, agregados nuevos campos de filtro, implementado Select2

## Impacto en Base de Datos

**No se requieren cambios en la base de datos** - todos los filtros usan campos y relaciones existentes:

- `subscription__start_date` - campo existente
- `products` - relación ManyToMany existente

## Compatibilidad Hacia Atrás

- Todos los filtros existentes continúan funcionando
- Sin cambios que rompan URLs o vistas
- Los marcadores y filtros guardados existentes permanecen válidos
- Los nuevos filtros son opcionales - los usuarios pueden ignorarlos

## Mejoras Futuras

Posibles mejoras para futuras iteraciones:

1. **Presets de rango de fechas:** Filtros rápidos como "Próximos 30 días", "Este mes", "Próximo trimestre"
2. **Categorías de productos:** Filtrar por tipo o categoría de producto
3. **Guardar presets de filtros:** Permitir a los usuarios guardar combinaciones de filtros comúnmente usadas
4. **Exportar resultados filtrados:** Exportación CSV respetando los filtros actuales
5. **Filtros avanzados de productos:** Filtrar por rango de precio de producto, frecuencia, etc.

## Notas

- Select2 usa recursos del plugin AdminLTE local para mejor rendimiento y soporte offline
- La fecha de transacción y la fecha de inicio de suscripción ahora están claramente distinguidas en la UI
- El filtro de productos solo muestra productos activos para evitar confusión con artículos descontinuados
- Tanto las vistas de vendedor como de gerente tienen las mismas capacidades de filtrado para consistencia
- Todos los placeholders y etiquetas son traducibles para soporte de internacionalización

## Características Relacionadas

- Vistas de registro de ventas (SalesRecordFilterSellersView, SalesRecordFilterManagersView)
- Funcionalidad de consola de vendedor
- Gestión de campañas y reportes
- Gestión de productos
