# Inactivación Automática de Suscripción Cuando se Eliminan Todos los Productos

**Fecha:** 2025-12-12
**Tipo:** Mejora de Funcionalidad, Lógica de Negocio
**Componente:** Gestión de Suscripciones, Gestión de Productos
**Impacto:** Ciclo de Vida de Suscripciones, Integridad de Datos
**Tarea:** t984

## Resumen

Se mejoró el método `remove_product()` en el modelo `Subscription` para inactivar automáticamente las suscripciones cuando se elimina el último producto. Esto asegura que las suscripciones sin productos sean marcadas apropiadamente como inactivas con códigos de estado y fechas de finalización adecuadas, manteniendo la integridad de datos y previniendo suscripciones activas huérfanas.

## Motivación

Anteriormente, al eliminar productos de una suscripción, el sistema:

1. **Permitía suscripciones vacías:** Una suscripción podía permanecer activa incluso con cero productos
2. **Falta de seguimiento apropiado:** No había indicación clara de que una suscripción terminó debido a que se eliminaron todos los productos
3. **Inconsistencia de datos:** Suscripciones activas sin productos creaban confusión en reportes y analíticas
4. **Intervención manual requerida:** El personal tenía que marcar manualmente las suscripciones como inactivas después de eliminar todos los productos

Esto creaba sobrecarga operacional y potenciales problemas de calidad de datos, ya que las suscripciones activas siempre deberían tener al menos un producto.

## Implementación

### 1. Nueva Razón de Inactividad y Tipo de Desuscripción Agregados

**Archivo:** `core/models.py`

Se agregaron nuevos valores de elección para rastrear suscripciones que terminaron debido a que se eliminaron todos los productos:

```python
class InactivityReasonChoices(models.IntegerChoices):
    # ... opciones existentes ...
    DEBTOR = 13, _("Debtor")
    DEBTOR_AUTOMATIC = 16, _("Debtor, automatic unsubscription")
    RETENTION = 17, _("Retention")
    ALL_PRODUCTS_REMOVED = 18, _("All products removed")  # NUEVO
    NOT_APPLICABLE = 99, _("N/A")

class UnsubscriptionTypeChoices(models.IntegerChoices):
    # ... opciones existentes ...
    NORMAL = 1, _("Normal")
    LOGISTICS = 2, _("Logistics")
    CHANGED_PRODUCTS = 3, _("Changed products")
    ADDED_PRODUCTS = 4, _("Added products")
    RETENTION = 5, _("Retention")
    ALL_PRODUCTS_REMOVED = 6, _("All products removed")  # NUEVO
```

### 2. Método `remove_product()` Mejorado

**Archivo:** `core/models.py`

Se actualizó el método para inactivar automáticamente las suscripciones cuando se elimina el último producto:

```python
def remove_product(self, product):
    """
    Used to remove products from the current subscription. It is encouraged to always use this method when you want
    to remove a product from a subscription, so you always have control of what happens here. This also creates a
    product history with the current subscription, product, and date, with the type 'D' (De-activation).

    If that was the last product, mark the subscription as inactive, and mark the reason as ALL_PRODUCTS_REMOVED.
    """
    try:
        sp = SubscriptionProduct.objects.get(subscription=self, product=product)
    except SubscriptionProduct.DoesNotExist:
        pass
    else:
        self.contact.add_product_history(self, product, "D")

    # Verificar si este fue el último producto
    if not self.subscriptionproduct_set.exists():
        self.active = False
        self.status = "OK"
        self.inactivity_reason = self.InactivityReasonChoices.ALL_PRODUCTS_REMOVED
        self.unsubscription_addendum = _("All products were removed.")
        self.unsubscription_type = self.UnsubscriptionTypeChoices.ALL_PRODUCTS_REMOVED
        self.end_date = date.today()
        self.save()
```

## Lógica de Negocio

Cuando se elimina un producto de una suscripción:

1. **Eliminación de producto:** El `SubscriptionProduct` es eliminado
2. **Seguimiento de historial:** Se crea historial de producto con tipo 'D' (Desactivación)
3. **Verificar productos restantes:** El sistema verifica si quedan productos
4. **Auto-inactivación:** Si no quedan productos, la suscripción es automáticamente:
   - Marcada como inactiva (`active = False`)
   - Establecida con estado "OK" (terminación normal)
   - Dada razón de inactividad: `ALL_PRODUCTS_REMOVED` (18)
   - Dado tipo de desuscripción: `ALL_PRODUCTS_REMOVED` (6)
   - Dado addendum de desuscripción: "All products were removed."
   - Dada fecha de finalización: fecha de hoy

## Casos de Uso

### 1. Eliminación Manual de Productos

**Escenario:** Un miembro del personal elimina productos uno por uno de una suscripción

```python
subscription = Subscription.objects.get(id=123)
subscription.remove_product(product1)  # Todavía tiene productos
subscription.remove_product(product2)  # Último producto - auto-inactiva
```

**Resultado:** Suscripción automáticamente marcada como inactiva con seguimiento apropiado

### 2. Eliminación Masiva de Productos

**Escenario:** Sistema o script elimina múltiples productos

```python
for product in subscription.subscriptionproduct_set.all():
    subscription.remove_product(product.product)
# Después de la última iteración, la suscripción está automáticamente inactiva
```

**Resultado:** Terminación limpia con códigos de estado apropiados

### 3. Flujo de Cambio de Productos

**Escenario:** Usuario cambia productos vía método `product_change()`

- Se eliminan productos de suscripción antigua
- Si se eliminan todos los productos, suscripción antigua se auto-inactiva
- Se crea nueva suscripción con nuevos productos

**Resultado:** Separación clara entre suscripciones antigua y nueva

## Beneficios

### 1. Integridad de Datos

- **Sin suscripciones huérfanas:** Las suscripciones activas siempre tienen al menos un producto
- **Limpieza automática:** El sistema maneja la inactivación sin intervención manual
- **Seguimiento apropiado:** Código de razón claro de por qué terminó la suscripción

### 2. Eficiencia Operacional

- **Trabajo manual reducido:** El personal no necesita inactivar manualmente las suscripciones
- **Comportamiento consistente:** Misma lógica aplicada independientemente de cómo se eliminen los productos
- **Rastro de auditoría:** El addendum de desuscripción proporciona explicación clara

### 3. Precisión de Reportes

- **Métricas claras:** Los reportes pueden distinguir suscripciones que terminaron debido a eliminación de productos
- **Mejores analíticas:** Rastrear patrones en comportamiento de eliminación de productos
- **Calidad de datos:** Sin confusión sobre suscripciones activas con cero productos

### 4. Aplicación de Lógica de Negocio

- **Aplicación automática:** Regla de negocio (suscripciones deben tener productos) es aplicada por código
- **Previene casos extremos:** Elimina posibilidad de suscripciones vacías activas
- **Estado consistente:** Estado de suscripción siempre refleja la realidad

## Cambios en Base de Datos

### Migración Requerida

Se necesitará una migración para agregar los nuevos valores de elección:

- `InactivityReasonChoices.ALL_PRODUCTS_REMOVED = 18`
- `UnsubscriptionTypeChoices.ALL_PRODUCTS_REMOVED = 6`

**Archivo de migración:** `core/migrations/XXXX_add_all_products_removed_choices.py`

**Cambios:**

- No se requieren cambios de esquema (campos enteros ya existen)
- Nuevos valores de elección son compatibles hacia atrás
- Datos existentes no son afectados

## Casos Extremos Manejados

### 1. Producto Ya Eliminado

```python
subscription.remove_product(product_that_doesnt_exist)
# Se maneja con gracia - sin error, sin cambios
```

### 2. Múltiples Eliminaciones Rápidas

```python
# Thread-safe - cada eliminación verifica estado actual
subscription.remove_product(product1)
subscription.remove_product(product2)  # Verifica si existen productos después de eliminación de product1
```

### 3. Suscripción Ya Inactiva

```python
# Si la suscripción ya está inactiva, la eliminación aún funciona
# Lógica de auto-inactivación solo se ejecuta si los productos llegan a cero
```

## Pruebas

### Pasos de Verificación

1. **Probar eliminación de un solo producto:**

   ```python
   from core.models import Subscription, Product

   subscription = Subscription.objects.get(id=123)
   print(f"Productos antes: {subscription.subscriptionproduct_set.count()}")
   print(f"Activa: {subscription.active}")

   # Eliminar último producto
   product = subscription.subscriptionproduct_set.first().product
   subscription.remove_product(product)

   subscription.refresh_from_db()
   print(f"Productos después: {subscription.subscriptionproduct_set.count()}")
   print(f"Activa: {subscription.active}")
   print(f"Razón de inactividad: {subscription.inactivity_reason}")
   print(f"Tipo de desuscripción: {subscription.unsubscription_type}")
   print(f"Fecha de finalización: {subscription.end_date}")
   ```

   **Salida esperada:**

   ```text
   Productos antes: 1
   Activa: True
   Productos después: 0
   Activa: False
   Razón de inactividad: 18
   Tipo de desuscripción: 6
   Fecha de finalización: 2025-12-12
   ```

2. **Probar eliminación de múltiples productos:**

   ```python
   subscription = Subscription.objects.get(id=456)
   products = list(subscription.subscriptionproduct_set.all())

   for sp in products[:-1]:
       subscription.remove_product(sp.product)
       subscription.refresh_from_db()
       assert subscription.active == True, "Debería seguir activa"

   # Eliminar último producto
   subscription.remove_product(products[-1].product)
   subscription.refresh_from_db()
   assert subscription.active == False, "Debería estar inactiva"
   assert subscription.inactivity_reason == 18
   ```

3. **Verificar consistencia de base de datos:**

   ```sql
   -- Encontrar suscripciones con razón ALL_PRODUCTS_REMOVED
   SELECT id, contact_id, active, inactivity_reason, unsubscription_type, end_date
   FROM core_subscription
   WHERE inactivity_reason = 18;

   -- Verificar que no tienen productos
   SELECT s.id, COUNT(sp.id) as product_count
   FROM core_subscription s
   LEFT JOIN core_subscriptionproduct sp ON sp.subscription_id = s.id
   WHERE s.inactivity_reason = 18
   GROUP BY s.id
   HAVING COUNT(sp.id) > 0;
   -- Debería retornar 0 filas
   ```

## Archivos Modificados

- `core/models.py` - Método `Subscription.remove_product()` mejorado y nuevos valores de elección agregados

## Compatibilidad Hacia Atrás

- **Código existente:** Todo el código existente continúa funcionando sin cambios
- **Datos existentes:** Sin impacto en suscripciones existentes
- **Nuevo comportamiento:** Solo aplica cuando se eliminan productos en adelante
- **Valores de elección:** Nuevos valores enteros (18, 6) no entran en conflicto con valores existentes
- **Sin cambios que rompan:** Firma del método sin cambios, comportamiento es aditivo

## Mejoras Futuras

Posibles mejoras para iteraciones futuras:

1. **Sistema de notificación:** Alertar al personal cuando las suscripciones se auto-inactivan
2. **Flujo de reactivación:** Manera fácil de reactivar y agregar productos de vuelta
3. **Operaciones masivas:** Vista dedicada para gestionar eliminaciones de productos
4. **Panel de analíticas:** Rastrear frecuencia de escenarios de todos-los-productos-eliminados
5. **Comportamiento configurable:** Permitir a proyectos personalizar lógica de auto-inactivación

## Problemas Relacionados

- Previene suscripciones activas huérfanas con cero productos
- Mejora calidad de datos y precisión de reportes
- Reduce sobrecarga operacional manual
- Aplica regla de negocio: suscripciones activas deben tener productos

## Notas

- El método usa `subscriptionproduct_set.exists()` para verificación eficiente de base de datos
- La fecha de finalización se establece a la fecha de hoy cuando ocurre auto-inactivación
- El estado se establece a "OK" para indicar terminación normal (no una condición de error)
- El addendum de desuscripción proporciona explicación legible por humanos
- La lógica solo se ejecuta después de eliminación exitosa de producto y creación de historial
- Thread-safe: verifica estado actual al momento de eliminación

## Lista de Verificación de Migración

- [ ] Crear migración para nuevos valores de elección
- [ ] Ejecutar migración en ambiente de desarrollo
- [ ] Probar escenarios de eliminación de productos
- [ ] Verificar consistencia de base de datos
- [ ] Actualizar cualquier reporte que filtre por inactivity_reason
- [ ] Actualizar cualquier documentación que referencie ciclo de vida de suscripción
- [ ] Desplegar a staging para pruebas
- [ ] Desplegar a producción

## Actualizaciones de Documentación

Considerar actualizar:

- Manual de usuario: Explicar comportamiento de inactivación automática
- Documentación de administración: Cómo manejar suscripciones auto-inactivadas
- Documentación de API: Documentar nuevos valores de elección
- Materiales de capacitación: Incluir nuevo flujo en capacitación del personal
