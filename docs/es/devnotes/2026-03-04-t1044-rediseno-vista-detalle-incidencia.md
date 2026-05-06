# Rediseño de la Vista de Detalle de Incidencia y Mejoras de UX

**Fecha:** 2026-03-04
**Tipo:** Mejora de UI/UX, Optimización de Rendimiento
**Componente:** Sistema de Gestión de Incidencias
**Impacto:** Experiencia de Usuario, Rendimiento, Accesibilidad
**Incidencia:** t1044

## Resumen

Rediseño completo de la Vista de Detalle de Incidencia (`view_issue.html`) con un diseño moderno y compacto, eliminación del modal de facturas que no funcionaba correctamente, optimización de consultas N+1 en `NewIssueView`, y mejora en la visualización de usuarios en todos los formularios de incidencias. Los cambios reducen el desplazamiento (scroll), dan mayor protagonismo a la información importante (notas, deuda), y muestran el nombre completo junto al nombre de usuario en todo el sistema de gestión de incidencias.

## Cambios

### 1. Rediseño del Template de Detalle de Incidencia

**Archivo:** `support/templates/view_issue.html`

Se rediseñó completamente el template para lograr un diseño más limpio y organizado:

- **Eliminación del modal de facturas** — Reemplazado por un enlace directo a la pestaña de facturas del contacto (`contact_detail#invoices`) que se abre en una nueva pestaña. El enlace indica claramente "(nueva pestaña)" para establecer expectativas.
- **Etiquetas en los badges de Categoría, Subcategoría y Estado** — Cada badge en el encabezado ahora tiene una etiqueta de texto (ej: "Categoría:", "Subcategoría:", "Estado:") y usa un estilo `badge-pill` más grande para mejor legibilidad.
- **Tarjeta de detalles compacta multi-columna** — Información de contacto, fechas, teléfonos y "Creado por" se muestran en una sola fila en lugar de una lista vertical, reduciendo significativamente el espacio vertical.
- **Sección de notas prominente** — Las notas se muestran en un recuadro resaltado con borde amarillo al final de la tarjeta de detalles, haciéndolas inmediatamente visibles.
- **Alerta de deuda para incidencias de facturación** — La información de deuda se muestra en un recuadro amarillo con el monto, cantidad de facturas vencidas, y un botón claro "Ver facturas" que enlaza a la pestaña de facturas del contacto en una nueva pestaña.
- **Retroalimentación positiva "Sin deuda"** — Cuando un contacto no tiene deuda, se muestra un mensaje verde de éxito en lugar de simplemente omitir la sección.
- **Formulario reorganizado con secciones agrupadas:**
  - **Estado y Asignación** (arriba) — Estado, Asignado a, Fecha próxima acción, Copias y Sobre, todo en una fila. `assigned_to` se movió del final al principio del formulario para reducir el scroll.
  - **Clasificación** — Subcategoría y Resolución lado a lado.
  - **Notas de progreso** — Textarea de progreso con Respuesta 1 y Respuesta 2 lado a lado.
- **Barra lateral de actividades mejorada** — Tarjetas de actividad compactas con íconos de dirección codificados por color (verde para entrantes, azul para salientes), badges de estado, contenedor con scroll (máximo 600px), y mensaje para estado vacío.
- **Items relacionados en grilla compacta** — Producto de suscripción, producto, dirección y suscripción mostrados en columnas en lugar de lista vertical.

### 2. Visualización de Nombre Completo para Usuarios

**Archivo:** `support/forms.py`

Se creó un campo reutilizable `UserFullNameChoiceField` que muestra usuarios como "Nombre Completo (usuario)" en lugar de solo "usuario":

```python
class UserFullNameChoiceField(forms.ModelChoiceField):
    """ModelChoiceField that displays users as 'Full Name (username)'"""
    def label_from_instance(self, obj):
        full_name = obj.get_full_name()
        if full_name:
            return f"{full_name} ({obj.username})"
        return obj.username
```

Aplicado al campo `assigned_to` en los tres formularios de incidencias:

- **`IssueStartForm`** — Formulario de creación de incidencias
- **`IssueChangeForm`** — Formulario de edición (categorías no de facturación)
- **`InvoicingIssueChangeForm`** — Formulario de edición (categorías de facturación/cobranza)

El campo "Creado por" en el template también muestra ahora el formato "Nombre Completo (usuario)".

### 3. Optimización de Consultas N+1 en NewIssueView

**Archivo:** `support/views/all_views.py`

- **Precarga de relaciones del contacto** — `get_contact()` ahora usa `prefetch_related` para direcciones y un `Prefetch` anidado para suscripciones activas con sus productos, eliminando consultas repetidas al renderizar los dropdowns del formulario.
- **Querysets del formulario optimizados** — `get_form()` construye querysets de suscripciones y productos de suscripción a partir de datos precargados con `select_related('contact')` y `select_related('product', 'subscription__contact', 'address')` para prevenir consultas N+1 provocadas por los métodos `__str__`.
- **Cache de resoluciones por subcategoría** — El mapeo subcategoría-resolución ahora se cachea a nivel de clase para evitar consultas repetidas entre requests.
- **Cache de búsqueda de estado** — `get_initial()` cachea la búsqueda del estado "nuevo" para evitar consultas redundantes.
- **Asignado a por defecto** — El campo `assigned_to` ahora se inicializa con el usuario actualmente logueado (los usuarios pueden cambiarlo o eliminarlo).

### 4. Compatibilidad con Extensión Ladiaria

**Archivo:** `utopia_crm_ladiaria/templates/view_issue.html` (sin cambios)

El bloque `{% block issue_additional_actions %}` permanece en la misma posición lógica (junto al botón Actualizar), por lo que el template de extensión de ladiaria que agrega los botones "Ofrecer Retención" y "Procesar Baja" continúa funcionando sin necesidad de cambios.

## Archivos Modificados

- **`support/templates/view_issue.html`** — Rediseño completo del template
- **`support/forms.py`** — Agregado `UserFullNameChoiceField`, aplicado a `assigned_to` en 3 formularios
- **`support/views/all_views.py`** — Optimización de consultas N+1 en `NewIssueView`, agregado import de `Prefetch`

## Decisiones de Diseño

### ¿Por qué eliminar el modal de facturas?

El modal no funcionaba correctamente y proporcionaba una mala experiencia de usuario. Enlazar directamente a la pestaña de facturas del contacto en una nueva pestaña le da a los usuarios la interfaz completa de gestión de facturas con ordenamiento, filtrado y capacidades de descarga. El indicador "(nueva pestaña)" establece las expectativas correctas.

### ¿Por qué subir assigned_to al principio?

El campo `assigned_to` estaba al final de un formulario largo, requiriendo mucho scroll. Como uno de los campos que se cambian con más frecuencia (junto con el estado), tiene sentido ubicarlo en la primera sección junto al estado y la fecha de próxima acción.

### ¿Por qué mostrar nombres completos?

El `__str__` por defecto del User de Django retorna solo el nombre de usuario (ej: "jperez"), lo cual no es inmediatamente reconocible en organizaciones con muchos usuarios. Mostrar "Juan Perez (jperez)" proporciona identificación instantánea manteniendo el nombre de usuario como referencia técnica.

### ¿Por qué usar una clase de campo reutilizable?

`UserFullNameChoiceField` puede usarse en cualquier lugar del sistema que necesite mostrar dropdowns de usuarios con nombres completos, manteniendo consistencia sin duplicación de código.

## Notas de Despliegue

- No se requieren migraciones
- No hay nuevas dependencias
- Los cambios de template son visibles inmediatamente después del despliegue
- Los cambios en formularios afectan todos los flujos de creación y edición de incidencias
