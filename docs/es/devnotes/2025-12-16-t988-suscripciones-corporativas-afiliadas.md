# Implementación de Sistema de Suscripciones Corporativas y Afiliadas

**Fecha:** 2025-12-16
**Ticket:** t988
**Tipo:** Nueva Funcionalidad
**Componente:** Suscripciones, Formularios, Vistas
**Impacto:** Gestión de Suscripciones Corporativas, Gestión de Afiliados, Experiencia de Usuario

## Resumen

Se implementó un sistema completo de suscripciones corporativas y afiliadas en utopia-crm, permitiendo la creación de suscripciones corporativas con múltiples sub-suscripciones afiliadas. Esto incluye importaciones faltantes, configuración de URL, integración de formularios y validación integral para gestionar espacios de suscripciones corporativas y relaciones de afiliados.

## Motivación

El sistema necesitaba funcionalidad para gestionar suscripciones corporativas donde:

1. **Múltiples suscripciones:** Una suscripción corporativa principal puede tener varias suscripciones afiliadas
2. **Precios personalizados:** Capacidad de anular precios calculados automáticamente para acuerdos corporativos especiales
3. **Gestión de espacios:** Rastrear y hacer cumplir límites en el número de suscripciones afiliadas
4. **Seguimiento de relaciones:** Relaciones claras padre-hijo entre suscripciones corporativas y afiliadas

La `CorporateSubscriptionCreateView` base existía pero era mínima e incompleta (marcada con TODO). La `AffiliateSubscriptionCreateView` fue traída de otro proyecto pero le faltaban importaciones y configuración de URL.

## Implementación

### 1. Corregidas Importaciones Faltantes en `AffiliateSubscriptionCreateView`

**Archivo:** `support/views/subscriptions.py`

Se agregaron las importaciones faltantes requeridas por la vista de suscripción afiliada:

```python
from dateutil.relativedelta import relativedelta
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.timezone import now
from django.views.generic import CreateView
```

**Propósito:**

- `LoginRequiredMixin` - Requisito de autenticación
- `CreateView` - Clase base para la vista
- `now` - Obtener fecha/hora actual para cálculos de fechas
- `relativedelta` - Calcular fechas de fin de suscripción basadas en duración del producto

### 2. Corregida Exportación de Vista

**Archivo:** `support/views/__init__.py`

Se corrigió el nombre de exportación de incorrecto a nombre de clase real:

```python
# Antes (incorrecto)
AffiliateSubscriptionView,

# Después (correcto)
AffiliateSubscriptionCreateView,
```

### 3. Agregado Patrón de URL para Suscripciones Afiliadas

**Archivo:** `support/urls.py`

Se agregó el patrón de URL faltante:

```python
path(
    "subscription/<int:subscription_id>/affiliate/new/",
    views.AffiliateSubscriptionCreateView.as_view(),
    name="add_affiliate_subscription",
),
```

**URL:** `/support/subscription/{subscription_id}/affiliate/new/`

Esto coincide con el nombre de URL referenciado en la plantilla de detalle de contacto (línea 153).

### 4. Corregidas Referencias de URL en Vista

**Archivo:** `support/views/subscriptions.py`

Se reemplazó la URL inexistente `subscription_detail` con `contact_detail`:

```python
# Antes (roto)
return HttpResponseRedirect(reverse("subscription_detail", args=[self.corporate_subscription.id]))

# Después (funcionando)
return HttpResponseRedirect(reverse("contact_detail", args=[self.corporate_subscription.contact.id]))
```

Esto asegura redirecciones apropiadas cuando falla la validación.

## Cómo Funciona el Sistema

### Suscripciones Corporativas

**Campos de Base de Datos:**

```python
type = models.CharField(max_length=1, choices=SUBSCRIPTION_TYPES)
# 'C' = Corporate (padre)
# 'A' = Affiliate (hijo)

parent_subscription = models.ForeignKey(
    'self',
    null=True,
    blank=True,
    on_delete=models.CASCADE,
    related_name='affiliate_subscriptions'
)

number_of_subscriptions = models.IntegerField(default=1)
# Para suscripciones corporativas, define espacios totales (incluyendo padre)
```

**Estructura de Relaciones:**

```text
Suscripción Corporativa (type='C')
├── number_of_subscriptions = 5
├── Suscripción Afiliada 1 (type='A', parent_subscription=Corporate)
├── Suscripción Afiliada 2 (type='A', parent_subscription=Corporate)
├── Suscripción Afiliada 3 (type='A', parent_subscription=Corporate)
└── Suscripción Afiliada 4 (type='A', parent_subscription=Corporate)
```

### Creando Suscripciones Afiliadas

**Acceso:** Desde una suscripción corporativa (type='C') en la página de detalle de contacto, hacer clic en el botón "Agregar Afiliado"

**Requisitos:**

- La suscripción padre debe ser tipo 'C' (Corporativa)
- Debe haber espacios disponibles (`current_affiliates < number_of_subscriptions`)
- El contacto seleccionado no puede ser el mismo que el contacto de la suscripción corporativa
- El contacto seleccionado no puede tener ya una suscripción afiliada activa

**Proceso:**

1. La vista muestra espacios disponibles y afiliados actuales
2. El usuario busca un contacto usando búsqueda HTMX
3. Las fechas se pre-llenan basadas en la duración del producto
4. Al enviar, crea una nueva suscripción con:
   - `type='A'` (Afiliado)
   - `parent_subscription` = suscripción corporativa
   - Mismo producto que la suscripción corporativa
   - Fechas de inicio/fin especificadas

### Características de la Vista

**Validaciones:**

- ✅ Asegura que la suscripción padre sea corporativa (type='C')
- ✅ Verifica que no se haya alcanzado el límite de afiliados
- ✅ Previene contacto duplicado (no puede ser el mismo que el contacto corporativo)
- ✅ Previene que el contacto tenga múltiples suscripciones afiliadas activas

**Configuración Automática:**

- Establece tipo de suscripción a 'A' (Afiliado)
- Vincula a suscripción corporativa padre
- Agrega el mismo producto que la suscripción corporativa
- Establece tipo de renovación a 'M' (Manual)

**Características de UI:**

- Muestra conteo de afiliados actuales vs. espacios totales
- Lista todas las suscripciones afiliadas existentes
- Búsqueda de contactos con HTMX
- Fechas pre-llenadas basadas en duración del producto

## Integración de Plantilla

El botón "Agregar Afiliado" aparece en la lista de suscripciones del detalle de contacto cuando:

- El tipo de suscripción es 'C' (Corporativa)
- El usuario está en el grupo Support o Managers
- La suscripción no está obsoleta

**Plantilla:** `support/templates/contact_detail/tabs/includes/_overview_subscription_list_item.html`

```django
{% if subscription.type == "C" %}
  <a href="{% url "add_affiliate_subscription" subscription.id %}"
     class="btn btn-sm btn-success mr-1 mb-1">
    <i class="fas fa-user-plus"></i> {% trans "Add Affiliate" %}
  </a>
{% endif %}
```

## Formulario: AffiliateSubscriptionForm

**Archivo:** `support/forms.py`

```python
class AffiliateSubscriptionForm(forms.ModelForm):
    contact = forms.CharField(widget=forms.TextInput(...))
    start_date = forms.DateField(...)
    end_date = forms.DateField(...)

    class Meta:
        model = Subscription
        fields = ['contact', 'start_date', 'end_date']
```

**Características:**

- El campo de contacto acepta ID de contacto (validado en `clean_contact()`)
- Los campos de fecha usan selector de fecha HTML5
- Automáticamente establece type='A' y renewal_type='M' al guardar

## Ejemplo de Uso

1. Crear una suscripción corporativa con `number_of_subscriptions=5`
2. Navegar a la página de detalle del contacto de la suscripción corporativa
3. Hacer clic en el botón "Agregar Afiliado" en la suscripción corporativa
4. Buscar y seleccionar un contacto
5. Ajustar fechas si es necesario (pre-llenadas basadas en duración del producto)
6. Enviar formulario
7. La suscripción afiliada se crea y vincula a la suscripción corporativa

## Beneficios

✅ **Gestión Centralizada:** Todos los afiliados vinculados a una suscripción corporativa
✅ **Control de Espacios:** Hace cumplir el número máximo de afiliados
✅ **Asignación Automática de Producto:** Los afiliados obtienen el mismo producto que la corporativa
✅ **Navegación Fácil:** Enlaces entre suscripciones padre y afiliadas
✅ **Validación:** Previene afiliados duplicados y configuraciones inválidas
✅ **Integración Completa:** Funciona con el sistema de gestión de suscripciones existente

## Archivos Modificados

- `support/views/subscriptions.py` - Agregadas importaciones faltantes, corregidas referencias de URL
- `support/views/__init__.py` - Corregido nombre de exportación de vista
- `support/urls.py` - Agregado patrón de URL de suscripción afiliada
- `support/forms.py` - Ya tenía `AffiliateSubscriptionForm` (sin cambios necesarios)
- `support/templates/subscriptions/affiliate_subscriptions.html` - Ya existía (sin cambios necesarios)
- `tests/test_corporate_billing.py` - Nueva suite completa de pruebas para facturación corporativa y afiliada

## Pruebas

Se creó suite completa de pruebas en `tests/test_corporate_billing.py` que verifica:

- **Suscripciones corporativas usan override_price** cuando está configurado en lugar del precio calculado del producto
- **Suscripciones corporativas sin override_price** usan precio de producto normal
- **Suscripciones afiliadas (tipo='A') no pueden ser facturadas** - similar a suscripciones gratuitas
- **Suscripciones gratuitas (tipo='F') no pueden ser facturadas** - verificación base
- **Estructura de múltiples afiliados** - solo la suscripción corporativa crea facturas, los afiliados no
- **Suscripciones corporativas con end_date** - comportamiento de facturación única

Todas las pruebas manejan mensajes de error tanto en inglés como en español para internacionalización.

## Documentación

Se creó documentación completa en:

- `/docs/AFFILIATE_SUBSCRIPTION_INTEGRATION.md` - Guía completa de uso y arquitectura

## Cambios Relacionados

Para la implementación de suscripción corporativa específica de La Diaria con características adicionales (gigantes, tarjetas, preservación de vendedores), ver el changelog correspondiente en utopia-crm-ladiaria.
