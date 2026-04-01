# Edición de Campaña en Validación de Ventas

**Fecha:** 2025-12-29
**Tipo:** Mejora de Funcionalidad, Mejora de UI
**Componente:** Registros de Ventas, Validación de Suscripciones
**Impacto:** Gestión de Ventas, Precisión de Datos, Experiencia de Usuario

## Resumen

Se mejoró la vista de validación de suscripciones para permitir a los gerentes editar la campaña asociada con un registro de ventas durante el proceso de validación. Se implementó Select2 para los menús desplegables de vendedor y campaña para proporcionar una interfaz moderna y con búsqueda que mejora la usabilidad.

## Motivación

Anteriormente, al validar una suscripción y su registro de ventas, los gerentes solo podían modificar:

1. El vendedor asignado a la venta
2. El valor de la comisión
3. Si la venta puede ser comisionada

Sin embargo, no había forma de editar la **campaña** asociada con el registro de ventas durante la validación. Esto creaba problemas cuando:

- Una venta se atribuía incorrectamente a la campaña equivocada
- La campaña necesitaba actualizarse después de que se registró la venta inicial
- Se necesitaban correcciones de datos para la precisión de los reportes

Los gerentes tenían que:

- Aceptar datos de campaña incorrectos
- Editar el registro de ventas por separado en la interfaz de administración
- Dejar la validación incompleta

Este flujo de trabajo era ineficiente y propenso a errores, especialmente para reportes y análisis basados en campañas.

## Implementación

### 1. Mejora del ValidateSubscriptionForm

**Archivo:** `support/forms.py`

Se agregó un campo de campaña al formulario con filtrado apropiado del queryset:

```python
class ValidateSubscriptionForm(forms.ModelForm):
    override_commission_value = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": _("Override amount"), "min": 0}),
    )
    seller = forms.ModelChoiceField(
        queryset=Seller.objects.filter(internal=True),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    campaign = forms.ModelChoiceField(
        queryset=Campaign.objects.filter(active=True),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    class Meta:
        model = SalesRecord
        fields = ("can_be_commissioned", "override_commission_value", "seller", "campaign")
        widgets = {
            "can_be_commissioned": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
```

**Características Clave:**

- **Solo campañas activas:** Filtra para mostrar solo campañas activas y evitar seleccionar inactivas
- **Campo opcional:** La campaña puede dejarse en blanco si no aplica
- **Estilo de control de formulario:** Consistente con otros campos del formulario

### 2. Implementación de Select2 para Mejor UX

**Archivo:** `support/templates/validate_subscription_sales_record.html`

Se agregó la librería Select2 e inicialización para los campos de vendedor y campaña:

**CSS Agregado:**

```html
{% block stylesheets %}
  {{ block.super }}
  <link href="{% static 'admin-lte/plugins/select2/css/select2.min.css' %}" rel="stylesheet" />
  <link href="{% static 'admin-lte/plugins/select2-bootstrap4-theme/select2-bootstrap4.min.css' %}" rel="stylesheet" />
{% endblock stylesheets %}
```

**Inicialización JavaScript:**

```javascript
{% block extra_js %}
  <script src="{% static 'admin-lte/plugins/select2/js/select2.full.min.js' %}"></script>
  <script>
  $(function() {
    $('#id_seller').select2({
      theme: 'bootstrap4',
      width: '100%',
      placeholder: '{% trans "Select seller" %}',
      allowClear: false
    });

    $('#id_campaign').select2({
      theme: 'bootstrap4',
      width: '100%',
      placeholder: '{% trans "Select campaign" %}',
      allowClear: true
    });
  });
  </script>
{% endblock extra_js %}
```

**Configuración de Select2:**

- **Campo de vendedor:** `allowClear: false` (campo requerido)
- **Campo de campaña:** `allowClear: true` (campo opcional con botón X para limpiar)
- **Tema Bootstrap 4:** Estilo consistente con AdminLTE
- **Con búsqueda:** Escribir para filtrar opciones
- **Placeholders traducibles:** Sugerencias amigables para el usuario

### 3. Reestructuración del Diseño del Formulario

**Archivo:** `support/templates/validate_subscription_sales_record.html`

Se reorganizó el formulario usando el sistema de grilla de Bootstrap para mejor espaciado y alineación:

**Antes:**

- Usaba flexbox con anchos inconsistentes
- Los campos tenían espaciado variable
- Etiquetas e inputs no estaban alineados apropiadamente

**Después:**

```html
<div class="row mb-3">
  <div class="col-md-3">
    <label for="seller_id" class="form-label">{% trans "Seller" %}</label>
    {% render_field form.seller class="form-control" %}
  </div>
  <div class="col-md-3">
    <label for="campaign_id" class="form-label">{% trans "Campaign" %}</label>
    {% render_field form.campaign class="form-control" %}
  </div>
  <div class="col-md-3">
    <label for="override" class="form-label">{% trans "Add Commission Value Manually" %}</label>
    {% render_field form.override_commission_value class="form-control" %}
  </div>
  <div class="col-md-3">
    <div class="form-check mt-4 pt-2">
      {% render_field form.can_be_commissioned class="form-check-input" %}
      <label for="can_be_commissioned_id" class="form-check-label">{% trans "Can be commissioned" %}</label>
    </div>
  </div>
</div>
```

**Mejoras de Diseño:**

- **Columnas de ancho igual:** Cada campo ocupa 25% del ancho (`col-md-3`)
- **Espaciado consistente:** Utilidades de margen de Bootstrap (`mb-3`, `mt-4`, `pt-2`)
- **Alineación apropiada:** Etiquetas sobre inputs, checkbox alineado con otros campos
- **Diseño responsivo:** Se adapta a diferentes tamaños de pantalla

## Detalles Técnicos

### Configuración del Campo de Formulario

**Campo de Campaña:**

- **Modelo:** SalesRecord
- **Campo:** campaign (ForeignKey a Campaign)
- **Queryset:** `Campaign.objects.filter(active=True)`
- **Requerido:** False (opcional)
- **Widget:** Select con clase form-control

**Validación:**

- El ModelForm de Django maneja la validación automáticamente
- Solo se pueden seleccionar campañas activas
- El campo puede dejarse en blanco (NULL en la base de datos)

### Implementación de Select2

Se usaron assets locales del plugin AdminLTE:

- `admin-lte/plugins/select2/css/select2.min.css`
- `admin-lte/plugins/select2-bootstrap4-theme/select2-bootstrap4.min.css`
- `admin-lte/plugins/select2/js/select2.full.min.js`

**Beneficios sobre select estándar:**

- Menú desplegable con búsqueda (escribir para filtrar)
- Mejor presentación visual
- Botón de limpiar para campos opcionales
- Consistente con patrones de UI modernos
- Amigable para móviles

## Beneficios

### 1. Gestión Completa de Datos

- **Editar todos los campos relevantes:** Vendedor, campaña y comisión en un solo lugar
- **No se necesita acceso al admin:** Los gerentes pueden corregir datos de campaña durante la validación
- **Flujo de trabajo único:** No es necesario cambiar entre vistas

### 2. Mejor Precisión de Datos

- **Corregir errores de campaña:** Corregir campañas mal atribuidas inmediatamente
- **Mejores reportes:** Atribución precisa de campaña para análisis
- **Registro de auditoría:** Cambios rastreados a través del proceso de validación

### 3. Experiencia de Usuario Mejorada

- **Menús desplegables con búsqueda:** Encontrar vendedores y campañas rápidamente escribiendo
- **Claridad visual:** Campos de ancho igual con espaciado apropiado
- **Campos opcionales claros:** Botón X en el campo de campaña indica que es opcional
- **Interfaz consistente:** Coincide con otras implementaciones de Select2 en el sistema

### 4. Eficiencia del Flujo de Trabajo

- **Validación en un paso:** Editar todos los campos y validar en una sola acción
- **Reducción de cambio de contexto:** No es necesario abrir la interfaz de administración
- **Correcciones más rápidas:** Actualizaciones de campaña inmediatas durante la validación

## Uso

### Para Gerentes

Acceso vía: **Gestión de Campañas > Registro de Ventas > Validar**

**Flujo de Trabajo de Validación:**

1. Hacer clic en el botón "Validar" en un registro de ventas no validado
2. Revisar los detalles de la suscripción y el registro de ventas
3. **Editar campos según sea necesario:**
   - **Vendedor:** Seleccionar de vendedores internos (con búsqueda)
   - **Campaña:** Seleccionar de campañas activas (con búsqueda, opcional)
   - **Comisión:** Sobrescribir la comisión calculada si es necesario
   - **Puede ser comisionada:** Marcar si la venta debe generar comisión
4. Hacer clic en "Validar" para guardar cambios y marcar la suscripción como validada

**Casos de Uso de Ejemplo:**

- **Corregir atribución de campaña:** La venta se registró bajo la campaña incorrecta
- **Agregar campaña faltante:** La venta se creó sin campaña, agregarla durante la validación
- **Eliminar campaña:** Limpiar el campo de campaña si se configuró incorrectamente
- **Actualizar vendedor y campaña:** Corregir ambos en un solo paso de validación

### Funcionalidad de Búsqueda

**Menú Desplegable de Vendedor:**

- Escribir el nombre del vendedor para filtrar la lista
- Campo requerido (sin botón de limpiar)
- Muestra solo vendedores internos

**Menú Desplegable de Campaña:**

- Escribir el nombre de la campaña para filtrar la lista
- Campo opcional (botón X para limpiar)
- Muestra solo campañas activas
- Puede dejarse en blanco

## Pruebas

### Pasos de Verificación

1. **Probar selección de campaña:**
   - Ir a la lista de Registros de Ventas
   - Hacer clic en "Validar" en un registro no validado
   - Hacer clic en el menú desplegable de Campaña
   - Escribir para buscar una campaña
   - Seleccionar una campaña
   - Hacer clic en "Validar"
   - Verificar que la campaña se guarda en el registro de ventas

2. **Probar limpieza de campaña:**
   - Abrir vista de validación para registro con campaña
   - Hacer clic en el botón X del campo de campaña
   - Hacer clic en "Validar"
   - Verificar que la campaña se elimina del registro de ventas

3. **Probar búsqueda de Select2:**
   - Hacer clic en el menú desplegable de Vendedor
   - Escribir nombre parcial del vendedor
   - Verificar que la lista filtra a vendedores coincidentes
   - Repetir para el menú desplegable de Campaña

4. **Probar diseño del formulario:**
   - Verificar que los cuatro campos tienen ancho igual
   - Verificar que las etiquetas están alineadas apropiadamente
   - Verificar que el checkbox se alinea con otros campos
   - Probar en diferentes tamaños de pantalla

5. **Probar ediciones combinadas:**
   - Cambiar vendedor, campaña y valor de comisión
   - Hacer clic en "Validar"
   - Verificar que todos los cambios se guardan correctamente

## Archivos Modificados

- `support/forms.py` - Se agregó campo de campaña a ValidateSubscriptionForm
- `support/templates/validate_subscription_sales_record.html` - Se agregó Select2, se reestructuró el diseño del formulario, se agregó campo de campaña

## Impacto en Base de Datos

**No se requieren cambios en la base de datos** - usa el campo existente SalesRecord.campaign:

- El campo ya existe en la base de datos
- ForeignKey al modelo Campaign
- Nullable (puede ser NULL)

## Compatibilidad Hacia Atrás

- Se preserva toda la funcionalidad de validación existente
- El campo de campaña es opcional - puede dejarse en blanco
- No hay cambios que rompan el flujo de trabajo de validación
- Los registros de ventas existentes no se ven afectados

## Mejoras Futuras

Posibles mejoras para futuras iteraciones:

1. **Historial de campaña:** Rastrear cambios de campaña en el historial de validación
2. **Actualizaciones masivas de campaña:** Actualizar campaña para múltiples registros de ventas
3. **Reglas de validación de campaña:** Advertir si la campaña no coincide con las fechas de suscripción
4. **Sugerencias de campaña:** Auto-sugerir campaña basada en la fecha de suscripción
5. **Estadísticas de campaña:** Mostrar rendimiento de campaña durante la validación

## Notas

- Select2 usa assets locales del plugin AdminLTE para mejor rendimiento
- El campo de campaña filtra solo a campañas activas para evitar seleccionar inactivas
- Tanto vendedor como campaña usan Select2 para experiencia de usuario consistente
- El diseño del formulario usa grilla de Bootstrap para diseño responsivo
- Todas las etiquetas y placeholders son traducibles para internacionalización

## Funcionalidades Relacionadas

- Validación de registros de ventas (vista ValidateSubscriptionSalesRecord)
- Gestión y reportes de campañas
- Funcionalidad de consola de vendedor
- Gestión de suscripciones
