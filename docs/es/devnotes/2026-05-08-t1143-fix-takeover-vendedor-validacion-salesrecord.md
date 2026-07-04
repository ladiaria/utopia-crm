# Fix: La validación de SalesRecord sobreescribía el vendedor de productos no relacionados

- **Fecha:** 2026-05-08
- **Autor:** Tanya Tree + Claude Sonnet 4.6
- **Ticket:** t1143
- **Tipo:** Corrección
- **Componente:** Support — Registro de Ventas, Suscripciones
- **Impacto:** Integridad de Datos, Cálculo de Comisiones

## 🎯 Resumen

Cuando un manager validaba un `SalesRecord` con el checkbox "puede comisionar" activado, una consulta `UPDATE` masiva reemplazaba el campo `seller` en **todos** los `SubscriptionProduct` de tipo S de esa suscripción — incluyendo productos que no tenían ninguna relación con la venta que se estaba validando. En suscripciones que habían pasado por un flujo de cambio de producto o producto adicional (que generan `SalesRecord` parciales cubriendo solo los productos nuevos), esto reasignaba silenciosamente el vendedor original de los productos preexistentes al vendedor del `SalesRecord` que se validaba. El mismo bug existía en `SalesRecordCreateView`, que crea un `SalesRecord` de forma manual para suscripciones que no tenían ninguno. El fix acota ambos updates para que solo afecten a los `SubscriptionProduct` cuyos productos estén explícitamente listados en `sales_record.products`, que es la intención semántica correcta de la operación.

## ✨ Cambios

### 1. Acotar el update masivo de seller en `ValidateSubscriptionSalesRecord`

**Archivo:** `support/views/all_views.py`

El filtro original usaba `product__type="S"` para seleccionar todos los productos de la suscripción, sin importar si estaban en el `SalesRecord` que se estaba validando:

```python
# Antes — sobreescribía todos los SPs tipo S de la suscripción
SubscriptionProduct.objects.filter(
    subscription=subscription, product__type="S"
).update(seller=sales_record.seller)
```

El fix filtra por `product__in=sales_record.products.all()`, de modo que solo se tocan los productos explícitamente asociados a ese `SalesRecord` en particular:

```python
# Después — solo toca los productos de este SalesRecord específico
SubscriptionProduct.objects.filter(
    subscription=subscription, product__in=sales_record.products.all()
).update(seller=sales_record.seller)
```

### 2. Mismo fix en `SalesRecordCreateView`

**Archivo:** `support/views/all_views.py`

`SalesRecordCreateView.form_valid` tenía un update masivo idéntico, demasiado amplio, que se ejecutaba inmediatamente después de asignar todos los productos tipo S de la suscripción al nuevo registro. Se aplicó el mismo acotamiento:

```python
# Después — usa el M2M ya poblado por products.set() en la línea anterior
SubscriptionProduct.objects.filter(
    subscription=subscription, product__in=sales_record_obj.products.all()
).update(seller=sales_record_obj.seller)
```

Nota: en `SalesRecordCreateView`, `products.set()` se llama con `self.subscription.products.filter(type="S")` en la línea inmediatamente anterior al update, por lo que en la práctica las consultas antigua y nueva producen el mismo resultado para esa vista. El fix se aplica igualmente por correctitud y simetría.

### 3. Tests de regresión

**Archivo:** `tests/test_product_change_seller.py`

Se agregó una nueva clase `TestValidateSalesRecordSellerPreservation` con dos escenarios:

- **`test_validate_sale_only_updates_sellers_in_sr`**: la suscripción tiene dos productos con vendedores distintos; el `SalesRecord` cubre solo uno de ellos. Verifica que al validar el registro, el seller se actualiza únicamente en el producto cubierto y el otro queda intacto.
- **`test_validate_sale_does_not_overwrite_unrelated_sp_sellers`**: misma configuración, pero el `SalesRecord` cubre el segundo producto con un vendedor distinto al del primero. Verifica que el seller del primer producto no es modificado.

Ambos tests fueron escritos antes de aplicar el fix y se confirmó que fallaban; luego se verificó que pasan con el fix aplicado.

## 📁 Archivos Modificados

- **`support/views/all_views.py`** — Acotado el filtro del update masivo de `SubscriptionProduct` en `ValidateSubscriptionSalesRecord.form_valid` y `SalesRecordCreateView.form_valid`
- **`tests/test_product_change_seller.py`** — Agregada la clase `TestValidateSalesRecordSellerPreservation` con dos tests de regresión; agregado `SalesRecord` a los imports

## 📚 Detalles Técnicos

**Por qué el bug era raramente visible en la práctica:**

El takeover solo se manifestaba en suscripciones con productos pertenecientes a más de un vendedor — un estado que surge después de flujos de cambio de producto o producto adicional. Una suscripción FULL nueva siempre tiene un único vendedor en todos sus productos, por lo que validar su `SalesRecord` no producía ninguna diferencia observable aunque el filtro fuera demasiado amplio.

Además, `SalesRecordCreateView` asigna `sr.products = todos los productos tipo S de la suscripción` antes de ejecutar el update, haciendo equivalentes los filtros antiguo y nuevo para esa ruta. El único camino peligroso era `ValidateSubscriptionSalesRecord` siendo usado para validar un `SalesRecord` PARTIAL (creado por `product_change`, `additional_product`, o los flujos de edición de `edit_subscription`) sobre una suscripción que aún tenía productos de un vendedor anterior.

**Por qué las ventas FULL nunca se veían afectadas:**

Un `SalesRecord` de tipo FULL se crea al momento de creación de la suscripción y cubre todos sus productos. Cuando se marca `can_be_commissioned` en la validación, el seller ya es el mismo que figura en todos los SPs, así que el update es una no-operación desde el punto de vista de la correctitud de datos.

**Relación con t1142:**

t1142 corrigió el takeover de seller en el flujo POST de `edit_subscription` (vía `capture_variables` / `process_subscription_products` en el mixin de ladiaria). t1143 cierra el camino restante: el paso de validación, que podía deshacer los sellers preservados por t1142 si un manager validaba una venta parcial después de editar.

## 🧪 Pruebas Manuales

1. **Caso exitoso — validar una venta completa, todos los sellers quedan correctos:**
   - Crear una suscripción nueva con dos productos tipo S, ambos vendidos por Vendedor A.
   - Validar el `SalesRecord` FULL resultante con `can_be_commissioned` activado y Vendedor A como seller.
   - **Verificar:** Ambos `SubscriptionProduct` siguen mostrando a Vendedor A como seller.

2. **Caso exitoso — validar una venta parcial, solo los productos cubiertos son actualizados:**
   - Crear una suscripción con dos productos tipo S: producto 1 → Vendedor A, producto 2 → Vendedor B.
   - Simular un flujo de cambio de producto o edición de suscripción que cree un `SalesRecord` PARTIAL cubriendo solo producto 2, con Vendedor B.
   - Ir a `support/validate_sale/<sr_id>/`, activar `can_be_commissioned`, confirmar el seller como Vendedor B y enviar.
   - **Verificar:** El `SubscriptionProduct` de producto 2 muestra a Vendedor B. El `SubscriptionProduct` de producto 1 sigue mostrando a Vendedor A (sin cambios).

3. **Caso borde — venta parcial donde el seller del SR difiere del seller original del SP:**
   - Misma configuración que el escenario 2, pero el seller del `SalesRecord` es Vendedor C (por ejemplo, un manager que tomó la llamada).
   - Validar con `can_be_commissioned` activado, Vendedor C como seller.
   - **Verificar:** El seller de producto 2 se actualiza a Vendedor C. El seller de producto 1 sigue siendo Vendedor A.

4. **Caso borde — `can_be_commissioned` desactivado, ningún seller es modificado:**
   - Repetir el escenario 2 pero dejar el checkbox desactivado.
   - **Verificar:** Ambos sellers de `SubscriptionProduct` quedan sin cambios después de la validación.

## 📝 Notas de Despliegue

- No se requieren migraciones de base de datos.
- No se requieren cambios de configuración.
- El fix es puramente a nivel de lógica: la consulta SQL `UPDATE` se acota con un subquery `IN` adicional sobre `sales_record.products`. No se hace backfill de datos; los sellers que hayan sido sobreescritos en producción antes de este fix deben corregirse usando el comando de gestión `detect_seller_takeovers` si fuera necesario.

## 🎓 Decisiones de Diseño

El fix no intenta determinar si el seller existente en el SP "debería" preservarse o sobreescribirse — simplemente restringe el update a los productos que el `SalesRecord` cubre explícitamente. Esto se corresponde con el significado semántico de la operación: "el vendedor que vendió estos productos específicos recibe el crédito por ellos." Los productos que no están en el registro fueron vendidos (o transferidos) a través de una transacción diferente y no deben ser tocados.

Se evaluó como alternativa eliminar el update masivo por completo y confiar únicamente en el campo seller ya establecido en cada SP en el momento de su creación. Esta opción fue descartada porque el flujo de validación de ventas está diseñado intencionalmente para que un manager pueda corregir o confirmar quién debe recibir la comisión por una venta — el seller en el `SalesRecord` puede diferir legítimamente del que fue asignado al crear el producto (por ejemplo, un supervisor reasignó la llamada). El update acotado preserva esa flexibilidad pero la circunscribe correctamente.

## 🚀 Mejoras Futuras

- Agregar un log de auditoría a `SubscriptionProduct` para rastrear los cambios del campo seller a lo largo del tiempo, facilitando la detección y diagnóstico de futuros bugs de tipo takeover sin necesidad de ejecutar un comando de gestión.
- Considerar si `ValidateSubscriptionSalesRecord` debería mostrar una advertencia cuando el `SalesRecord.seller` difiere de los sellers existentes en los SPs cubiertos, de modo que el manager pueda confirmar el cambio intencionalmente en lugar de que se aplique de forma silenciosa.

---

**Fecha:** 2026-05-08
**Autor:** Tanya Tree + Claude Sonnet 4.6
**Branch:** t1143
**Tipo de cambio:** Corrección
**Módulos afectados:** Support, Registro de Ventas
