# Creación de SalesRecord en flujos de cambio de producto, producto adicional y retención

- **Fecha:** 2026-04-24
- **Autor:** Tanya Tree + Claude Sonnet 4.6
- **Ticket:** t1126
- **Tipo:** Corrección | Mejora
- **Componente:** Support — Suscripciones, Registro de Ventas
- **Impacto:** Integridad de Datos, Flujo de Trabajo de Operadores, Cálculo de Comisiones

## 🎯 Resumen

El `SalesRecordFilterManagersView` (el filtro de ventas para gestores en `support/sales_record_filter/`) no mostraba ventas realizadas a través de los flujos de cambio de producto, producto adicional o descuento de retención, porque esas vistas nunca creaban objetos `SalesRecord`. Solo los flujos de nueva suscripción y edición de suscripción creaban registros. Este ticket corrige los tres flujos faltantes en el paquete base y en la capa de personalización de ladiaria, estandariza la creación de registros de venta parcial en la vista `edit_subscription` de ladiaria (un registro por sesión en lugar de uno por producto), corrige un bug de `AttributeError` causado por una ruta de atributo incorrecta, y mejora la UX del formulario de validación de ventas poniendo el checkbox de comisión marcado por defecto con una nota explicativa.

## ✨ Cambios

### 1. Creación de SalesRecord en `product_change` (base y ladiaria)

**Archivos:** `support/views/subscriptions.py`, `utopia_crm_ladiaria/views/subscriptions.py`

Tanto `product_change` (base) como `ladiaria_product_change` ahora crean un `SalesRecord` PARTIAL en la nueva suscripción, conteniendo solo los productos de tipo `S` recién activados. El precio es la diferencia entre el precio de la nueva y la vieja suscripción, siguiendo el mismo patrón que ya usaba `book_additional_product`.

```python
sf = SalesRecord.objects.create(
    subscription=new_subscription,
    seller_id=seller_id,
    price=new_subscription.get_price_for_full_period() - old_subscription.get_price_for_full_period(),
    sale_type=SalesRecord.SALE_TYPE.PARTIAL,
)
sf.products.add(*new_products_list)  # solo productos tipo "S"
if not seller_id:
    sf.set_generic_seller()
```

### 2. Creación de SalesRecord en `add_retention_discount` (base y ladiaria)

**Archivos:** `support/views/subscriptions.py`, `utopia_crm_ladiaria/views/retention.py`

Tanto `add_retention_discount` (base) como `ladiaria_add_retention_discount` ahora crean un `SalesRecord` PARTIAL. Los productos de descuento de retención (tipo `D`, `P` o `A`) se excluyen intencionalmente — solo se vinculan al registro los nuevos productos de suscripción (tipo `S`), porque los productos de descuento no tienen valor de venta independiente.

### 3. Ventas parciales en `edit_subscription`: un registro por sesión (ladiaria)

**Archivo:** `utopia_crm_ladiaria/views/subscriptions.py` — `LadiariaSubscriptionMixin.process_subscription_products`

Anteriormente, cada producto nuevo agregado dentro de un POST de edición de suscripción creaba su propio `SalesRecord` con tipo FULL por defecto. Esto era inconsistente con los otros flujos de venta parcial y generaba registros repetidos al agregar dos o más productos al mismo tiempo.

El método fue refactorizado: la creación del registro por producto fue eliminada del interior del loop; en su lugar, todos los productos de tipo `S` recién agregados se acumulan y se crea un único `SalesRecord` PARTIAL después del loop, con el precio igual a la suma de los precios individuales:

```python
if self.edit_subscription and added_subscription_products:
    price = sum(p.price for p in added_subscription_products)
    sf = SalesRecord.objects.create(
        subscription=subscription,
        seller_id=self.user_seller_id,
        price=price,
        sale_type=SalesRecord.SALE_TYPE.PARTIAL,
        campaign=self.campaign,
    )
    sf.products.add(*added_subscription_products)
    if not self.user_seller_id:
        sf.set_generic_seller()
```

No se crea ningún registro si no se agregaron productos de suscripción nuevos (por ejemplo, si el usuario solo actualizó direcciones).

### 4. Corrección de bug: `SalesRecord.TYPES.PARTIAL` → `SalesRecord.SALE_TYPE.PARTIAL`

**Archivo:** `support/views/subscriptions.py` — `book_additional_product`

El atributo `SalesRecord.TYPES` no existe; la ruta correcta es `SalesRecord.SALE_TYPE`. La llamada existente lanzaría un `AttributeError` en tiempo de ejecución. Corregido a `SalesRecord.SALE_TYPE.PARTIAL`.

### 5. Formulario de validación: `can_be_commissioned` marcado por defecto

**Archivos:** `support/views/all_views.py`, `support/templates/validate_subscription_sales_record.html`

`ValidateSubscriptionSalesRecord.get_initial` anteriormente forzaba `can_be_commissioned=False` para cualquier venta no FULL, lo que significaba que las ventas parciales (cambios de producto, retenciones) nunca aparecerían como comisionables por defecto. El override explícito fue eliminado; el campo ahora usa el valor por defecto del modelo (`True`).

Se agregó una nota explicativa debajo del checkbox en el template:

> "Si está marcado, el vendedor recibirá comisión por esta venta. Desmarcarlo excluye la venta de los cálculos de comisión (ej. descuentos de retención o cambios no comisionables)."

### 6. Tests unitarios extendidos

**Archivos:** `utopia_crm_ladiaria/tests/test_seller_registry.py`, `utopia_crm_ladiaria/tests/test_product_change_views.py`, `utopia_crm_ladiaria/tests/test_retention_view.py`

- **`TestSellerRegistryFullSalesRecord`** (13 casos nuevos): cubre registros FULL de nueva suscripción (cantidad, productos, vendedor, precio, tipo) y registros PARTIAL de edición (uno por sesión, solo productos nuevos, suma de precios correcta, tipo, productos de descuento excluidos, flujo sin vendedor).
- **`TestProductChangeSalesRecord`** (8 casos nuevos): cubre `ladiaria_product_change` y `ladiaria_book_additional_product` — registro creado, productos correctos, vendedor asignado, tipo PARTIAL.
- **`TestRetentionDiscountSalesRecord`** (7 casos nuevos): cubre `ladiaria_add_retention_discount` — registro creado, productos de descuento excluidos, productos tipo S incluidos, vendedor asignado, tipo PARTIAL, sin registro cuando falla la validación.

## 📁 Archivos Modificados

- **`support/views/subscriptions.py`** — Creación de `SalesRecord` agregada a `product_change` y `add_retention_discount`; corregido bug `TYPES.PARTIAL` en `book_additional_product`
- **`support/views/all_views.py`** — Eliminado el forzado de `can_be_commissioned=False` en `ValidateSubscriptionSalesRecord.get_initial`
- **`support/templates/validate_subscription_sales_record.html`** — Nota explicativa agregada para el checkbox `can_be_commissioned`
- **`utopia_crm_ladiaria/views/subscriptions.py`** — Creación de `SalesRecord` agregada a `ladiaria_product_change`; refactorización de `process_subscription_products` para crear un registro PARTIAL por sesión de edición
- **`utopia_crm_ladiaria/views/retention.py`** — Creación de `SalesRecord` agregada a `ladiaria_add_retention_discount`
- **`utopia_crm_ladiaria/tests/test_seller_registry.py`** — Nueva clase `TestSellerRegistryFullSalesRecord` con 13 casos de test
- **`utopia_crm_ladiaria/tests/test_product_change_views.py`** — Nueva clase `TestProductChangeSalesRecord` con 8 casos de test
- **`utopia_crm_ladiaria/tests/test_retention_view.py`** — Nueva clase `TestRetentionDiscountSalesRecord` con 7 casos de test

## 📚 Detalles Técnicos

- Solo los productos de tipo `S` (suscripción) se vinculan a `SalesRecord.products` en los flujos parciales. Los productos de descuento (tipo `D`, `P`, `A`) se filtran explícitamente porque no representan ítems vendidos de forma independiente y distorsionarían los cálculos de comisión.
- `set_generic_seller()` siempre se llama cuando no hay seller ID disponible, de forma consistente con todos los demás puntos de creación de `SalesRecord` en el código.
- Las vistas del paquete base (`product_change`, `add_retention_discount`) también fueron corregidas aunque son sobreescritas por las URLs de ladiaria, para mantener el paquete base correcto para otros despliegues.
- Los 55 tests en los tres archivos de test pasan correctamente después de los cambios.

## 🧪 Pruebas Manuales

1. **Caso exitoso — cambio de producto por un vendedor crea un registro visible:**
   - Iniciar sesión como usuario con un `Seller` asociado.
   - Abrir un contacto con suscripción activa e ir a la vista de cambio de producto.
   - Seleccionar un producto nuevo para agregar y enviar el formulario.
   - Navegar a `support/sales_record_filter/` como gestor.
   - **Verificar:** El nuevo registro PARTIAL aparece en la lista, vinculado a la nueva suscripción y mostrando solo el/los producto(s) recién agregado(s).

2. **Caso exitoso — descuento de retención crea registro solo con productos tipo S:**
   - Aplicar un descuento de retención (tipo `D`) más un nuevo producto de suscripción (tipo `S`) desde la vista de retención.
   - Revisar el filtro de ventas.
   - **Verificar:** El registro muestra el producto tipo `S`; el producto de descuento no aparece.

3. **Caso exitoso — formulario de validación tiene comisión marcada por defecto:**
   - Abrir la página de validación de venta para una venta PARTIAL.
   - **Verificar:** El checkbox `can_be_commissioned` está marcado por defecto.
   - Leer la nota explicativa debajo del checkbox.
   - **Verificar:** La nota explica qué implica activar/desactivar el checkbox.

4. **Caso borde — editar suscripción agregando dos productos crea un solo registro:**
   - Editar una suscripción existente y agregar dos productos nuevos en el mismo POST.
   - Revisar `SalesRecord.objects.filter(subscription=...)`.
   - **Verificar:** Existe exactamente un registro; ambos productos están vinculados a él; el precio es igual a la suma de los precios de ambos productos.

5. **Caso borde — editar suscripción sin agregar productos no crea registro:**
   - Editar una suscripción existente y cambiar solo una dirección (sin productos nuevos).
   - **Verificar:** No se crea ningún `SalesRecord` nuevo.

6. **Caso borde — cambio de producto por usuario sin vendedor igual crea registro:**
   - Iniciar sesión como superusuario sin `Seller` asociado.
   - Ejecutar un cambio de producto.
   - **Verificar:** Se crea un `SalesRecord` con vendedor genérico (asignado vía `set_generic_seller()`).

## 📝 Notas de Despliegue

- No se requieren migraciones de base de datos.
- No se requieren cambios de configuración.
- Tras el despliegue, las suscripciones existentes que pasaron por flujos de cambio de producto o retención antes de esta corrección no tendrán entradas `SalesRecord` retroactivas. Si se necesitan registros históricos para esas suscripciones, pueden crearse manualmente usando la vista existente `SalesRecordCreateView` (`support/create_sales_record/<subscription_id>/`).

## 🎓 Decisiones de Diseño

Los productos de descuento se excluyen de `SalesRecord.products` porque un descuento de retención aplicado a una suscripción no es una venta — es una reducción de precio. Incluirlo inflaría los conteos de productos en los cálculos de comisión y estadísticas de campaña. El vendedor sigue registrado en el record (y las comisiones pueden calcularse en el momento de la validación) en base a la diferencia de precio de la suscripción, que ya contempla los descuentos.

Un registro PARTIAL por sesión de edición (en lugar de uno por producto) se alinea con el funcionamiento de los demás flujos de venta parcial y evita llenar el filtro de ventas con múltiples registros casi idénticos cuando un vendedor agrega un conjunto de productos al mismo tiempo. El precio es la suma de los precios individuales, lo cual es correcto para una suscripción mensual donde cada producto tiene un precio independiente.

## 🚀 Mejoras Futuras

- El `SalesRecordFilterManagersView` podría exponer una columna de filtro por "tipo de venta" para que los gestores distingan registros FULL vs PARTIAL de un vistazo sin tener que abrir cada uno.
- Considerar mostrar el default de `can_be_commissioned` de forma diferente según el tipo de venta (ej. una advertencia visual para registros de retención) en lugar de depender solo de que el gestor lo desmarque manualmente.

---

- **Fecha:** 2026-04-24
- **Autor:** Tanya Tree + Claude Sonnet 4.6
- **Branch:** t1126
- **Tipo de cambio:** Corrección | Mejora
- **Módulos afectados:** Support, Registro de Ventas
