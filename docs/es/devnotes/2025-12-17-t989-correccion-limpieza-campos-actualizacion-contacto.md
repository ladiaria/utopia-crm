# Corrección de Limpieza de Campos en Actualización de Contactos

**Fecha:** 2025-12-17
**Ticket:** t989
**Tipo:** Corrección de Bug
**Componente:** Formularios, Vistas
**Impacto:** Gestión de Contactos, Integridad de Datos

## Resumen

Se corrigió un bug crítico en `ContactUpdateView` donde campos no renderizados en la plantilla de actualización de contactos (como `cms_date_joined`, `ranking`, `protected`, `protection_reason`, y otros) se estaban borrando accidentalmente cuando los usuarios actualizaban la información de contacto. Se creó un formulario dedicado `ContactUpdateForm` que solo incluye los campos realmente visibles y editables en la interfaz de actualización.

## Problema

### Causa Raíz

El `ContactUpdateView` estaba usando `ContactAdminForm` que incluye **todos** los campos del modelo Contact (`fields = "__all__"`). Sin embargo, la plantilla de actualización de contactos (`create_contact/create_contact.html`) solo renderiza un subconjunto de estos campos (15 de más de 30 campos).

### Qué Estaba Pasando

Cuando se envía un ModelForm de Django:

1. Django espera que todos los campos definidos en el formulario estén presentes en los datos POST
2. Si un campo no está renderizado en la plantilla, no estará en los datos POST
3. Django interpreta los campos faltantes como "el usuario quiere limpiar este campo"
4. Para campos nullable, esto resulta en establecerlos a `NULL`

### Campos que se Borraban Accidentalmente

Cualquier campo no presente en la plantilla estaba en riesgo de ser borrado, incluyendo:

- `cms_date_joined` - Fecha de ingreso al CMS (problema reportado)
- `ranking` - Ranking del contacto
- `protected` / `protection_reason` - Estado de protección del contacto
- `ocupation` - Ocupación del contacto
- `person_type` - Clasificación de tipo de persona
- `business_entity_type` - Clasificación de entidad empresarial
- `phone_extension` / `work_phone_extension` - Extensiones telefónicas
- `private_birthdate` - Flag de privacidad para fecha de nacimiento
- `no_email` - Flag para contactos sin email

## Implementación

### 1. Creación del Formulario Dedicado `ContactUpdateForm`

**Archivo:** `core/forms.py`

Se creó una nueva clase de formulario que solo incluye los 15 campos realmente renderizados en la plantilla de actualización de contactos:

```python
class ContactUpdateForm(EmailValidationForm, forms.ModelForm):
    class Meta:
        model = Contact
        fields = [
            'name',
            'last_name',
            'email',
            'phone',
            'mobile',
            'work_phone',
            'id_document_type',
            'id_document',
            'birthdate',
            'gender',
            'education',
            'tags',
            'notes',
            'allow_polls',
            'allow_promotions',
        ]
        widgets = {
            "birthdate": forms.TextInput(attrs={"class": "form-control datepicker"}),
        }
```

**Características:**

- Hereda de `EmailValidationForm` para validación de email
- Incluye toda la lógica de validación de `ContactAdminForm`:
  - Validación de email y verificación de duplicados
  - Verificación de duplicados de documento de identidad
  - Parseo de tags desde formato JSON de Tagify
- Solo procesa campos que son realmente editables en la UI

### 2. Actualización de `ContactAdminFormWithNewsletters`

**Archivo:** `support/views/contacts.py`

Se cambió la herencia de `ContactAdminForm` a `ContactUpdateForm`:

```python
class ContactAdminFormWithNewsletters(ContactUpdateForm):
    newsletters = ModelMultipleChoiceField(
        queryset=Product.objects.filter(type="N", active=True),
        widget=CheckboxSelectMultiple(...),
        required=False,
    )
    # ... resto de la implementación
```

Este formulario es usado por `ContactUpdateView` y ahora solo procesa los campos visibles más el campo de newsletters.

### 3. Actualización de Imports

**Archivo:** `support/views/contacts.py`

Se agregó `ContactUpdateForm` a los imports:

```python
from core.forms import ContactAdminForm, ContactUpdateForm
```

## Beneficios

### Integridad de Datos

- **Campos Protegidos:** Campos como `cms_date_joined`, `ranking`, y `protected` ahora están protegidos de borrado accidental
- **Datos Preservados:** Todos los campos del modelo Contact que no están en el formulario de actualización permanecen sin cambios durante las actualizaciones
- **Sin Efectos Secundarios:** Actualizar información básica de contacto ya no afecta datos de integración con CMS o campos administrativos

### Mantenibilidad

- **Separación Clara:** `ContactAdminForm` (todos los campos) vs `ContactUpdateForm` (campos editables por usuario)
- **Control Explícito:** El formulario lista explícitamente qué campos pueden ser actualizados a través de la UI
- **A Prueba de Futuro:** Agregar nuevos campos al modelo Contact no los expondrá accidentalmente en el formulario de actualización

### Experiencia de Usuario

- **Sin Cambio de Comportamiento:** Los usuarios ven la misma interfaz y funcionalidad
- **Consistencia de Datos:** La información de contacto permanece estable y confiable
- **Confianza:** Los usuarios pueden actualizar contactos sin preocuparse por perder datos

## Detalles Técnicos

### Campos Excluidos del Formulario de Actualización

Los siguientes campos están **excluidos** de `ContactUpdateForm` y nunca serán modificados durante actualizaciones de contacto:

**Integración CMS:**

- `cms_date_joined` - Gestionado por el sistema CMS

**Administrativos:**

- `protected` - Flag de protección de contacto
- `protection_reason` - Razón de protección
- `ranking` - Ranking/puntuación del contacto

**Clasificación:**

- `ocupation` - Ocupación del contacto
- `person_type` - Clasificación de tipo de persona
- `business_entity_type` - Tipo de entidad empresarial

**Extensiones Telefónicas:**

- `phone_extension` - Extensión telefónica
- `work_phone_extension` - Extensión de teléfono laboral

**Flags de Privacidad:**

- `private_birthdate` - Configuración de privacidad de fecha de nacimiento
- `no_email` - Flag de sin email

**Campos del Sistema:**

- Cualquier otro campo del modelo Contact no listado explícitamente en el formulario

### Arquitectura de Formularios

```text
EmailValidationForm (validación base)
    ├── ContactAdminForm (todos los campos - para admin de Django)
    │   └── Usado en: Interfaz de administración de Django
    │
    └── ContactUpdateForm (solo campos editables por usuario)
        └── ContactAdminFormWithNewsletters (agrega gestión de newsletters)
            └── Usado en: ContactUpdateView
```

## Recomendaciones de Prueba

1. **Verificar Preservación de Campos:**
   - Establecer `cms_date_joined` en un contacto
   - Actualizar el contacto a través de la UI
   - Verificar que `cms_date_joined` permanece sin cambios

2. **Probar Todos los Campos Excluidos:**
   - Establecer valores para `ranking`, `protected`, `person_type`, etc.
   - Realizar actualizaciones de contacto
   - Confirmar que todos los campos excluidos retienen sus valores

3. **Validar Funcionalidad del Formulario:**
   - Probar validación de email y verificación de duplicados
   - Probar verificación de duplicados de documento de identidad
   - Probar gestión de tags
   - Probar suscripción/desuscripción de newsletters

## Notas de Migración

- **Sin Cambios en Base de Datos:** Esta es una corrección solo de código
- **No Requiere Migración de Datos:** Los datos existentes no se ven afectados
- **Compatible hacia Atrás:** Toda la funcionalidad existente se preserva
- **Efecto Inmediato:** La corrección aplica tan pronto como se despliega el código

## Archivos Relacionados

- `core/forms.py` - Nueva clase `ContactUpdateForm`
- `support/views/contacts.py` - `ContactAdminFormWithNewsletters` e imports actualizados
- `support/templates/create_contact/create_contact.html` - Plantilla de actualización de contacto (sin cambios)
- `support/templates/create_contact/tabs/_data.html` - Plantilla de campos del formulario (sin cambios)

## Conclusión

Esta corrección asegura la integridad de datos controlando explícitamente qué campos de Contact pueden ser modificados a través de la interfaz de actualización de contactos. Los campos gestionados por sistemas externos (como CMS) o usados para propósitos administrativos ahora están protegidos de modificación accidental, mientras se mantiene toda la funcionalidad existente para los usuarios.
