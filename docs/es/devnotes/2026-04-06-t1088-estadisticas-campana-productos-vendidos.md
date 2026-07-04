# Estadísticas de Campaña: Contar Solo Productos Vendidos

- **Fecha:** 2026-04-06
- **Autor:** Tanya Tree + Claude Sonnet 4.6
- **Ticket:** t1088
- **Tipo:** Mejora / Corrección de comportamiento
- **Componente:** Estadísticas de Campaña, Registros de Ventas
- **Impacto:** Precisión de reportes

## 🎯 Resumen

`CampaignStatisticsDetailView` construía el conteo de productos por campaña consultando `SubscriptionProduct` filtrado por `subscription__campaign`. Esto devolvía todos los productos actualmente en la suscripción, incluyendo los que el suscriptor tenía antes de que ocurriera la venta en la campaña. El fix reemplaza esa consulta por `SalesRecord.objects.filter(campaign=...).filter(products=product)`, usando el campo M2M que ya registra únicamente lo que fue vendido. El método `export_csv()` de la misma vista tenía el mismo problema y fue corregido en el mismo commit. Se agregaron tests de regresión en `utopia-crm-ladiaria` para documentar el comportamiento correcto.

## 🔍 Problema Identificado

Cuando un vendedor usa la vista de edición de suscripción para agregar el producto C a una suscripción que ya tenía los productos A y B:

1. Se crea un `SalesRecord` con `products = {C}` únicamente — esto ya era correcto.
2. Se setea `subscription.campaign = campaña_actual` (vía `mark_as_sale` o `handle_direct_sale`).
3. La vista de estadísticas consultaba `SubscriptionProduct` filtrando por `subscription__campaign`, lo que devolvía A, B y C como "productos vendidos en la campaña".

La vista `SalesRecordFilterManagersView` ya usaba `SalesRecord.products` y era correcta. La inconsistencia era entre las dos vistas.

## ✨ Cambios

### 1. Conteo de productos en estadísticas de campaña

**Archivo:** `support/views/all_views.py`

En `get_context_data()`, el bloque que construye `subs_dict` ahora consulta `SalesRecord` en lugar de `SubscriptionProduct`:

```python
# Antes
subscription_products = SubscriptionProduct.objects.filter(
    subscription__campaign=self.campaign,
    subscription__contact_id__in=filtered_contact_ids
)
for product in Product.objects.filter(offerable=True, type="S"):
    subs_dict[product.name] = subscription_products.filter(product=product).count()

# Después
sales_records = SalesRecord.objects.filter(
    campaign=self.campaign,
    subscription__contact_id__in=filtered_contact_ids,
)
for product in Product.objects.filter(offerable=True, type="S"):
    subs_dict[product.name] = sales_records.filter(products=product).count()
```

### 2. Columna de productos en el CSV de exportación

**Archivo:** `support/views/all_views.py`

En `export_csv()`, la columna "Productos vendidos" antes leía `subscriptionproduct_set.all()` de la suscripción. Ahora acumula los productos de todos los `SalesRecord` del contacto para esa campaña, manejando correctamente el caso en que un contacto tenga múltiples registros de venta.

## 📁 Archivos Modificados

#### utopia-crm (base)

- **`support/views/all_views.py`** — `CampaignStatisticsDetailView`: `get_context_data()` y `export_csv()` actualizados para usar `SalesRecord.products`

## 📁 Archivos Creados

*(En utopia-crm-ladiaria — no en este repo)*

- **`utopia_crm_ladiaria/tests/test_seller_registry.py`** — Tests de diagnóstico para las vistas de suscripción y test de regresión para estadísticas de campaña

## 📚 Detalles Técnicos

`Subscription.campaign` es seteado por dos métodos en `core/models.py`:

- `Activity.mark_as_sale()` — llamado cuando el vendedor completa una venta desde una actividad existente (`?act=<id>`)
- `ContactCampaignStatus.handle_direct_sale()` — llamado cuando el vendedor registra una venta directa nueva (`?new=<ccs_id>`)

Ambos setean `subscription.campaign = campaign` y guardan. Esto es lo que hacía que `SubscriptionProduct.objects.filter(subscription__campaign=...)` encontrara la suscripción — con todos sus productos, nuevos y pre-existentes.

`SalesRecord.products` es seteado explícitamente en el momento de la venta: un producto por registro para ventas parciales (vista de edición), o todos los productos seleccionados a la vez para suscripciones nuevas (vista de creación). Esta es la fuente autorizada de "qué se vendió".

## 🧪 Pruebas Manuales

1. **Vendedor agrega un producto a una suscripción existente desde la consola de campaña:**
   - Abrir la consola de campaña para un contacto que ya tiene una suscripción activa con productos.
   - Usar "Editar suscripción" y agregar un producto nuevo.
   - Ir a Estadísticas de campaña → la campaña correspondiente.
   - **Verificar:** El producto nuevo aparece con conteo 1. Los productos pre-existentes muestran conteo 0 para esa campaña.

2. **Caso borde — contacto con múltiples registros de venta en la misma campaña:**
   - Crear dos `SalesRecord` para el mismo contacto y campaña, cada uno con un producto distinto.
   - Ver estadísticas de campaña.
   - **Verificar:** Ambos productos aparecen con conteo 1 cada uno; sin duplicados ni omisiones.

3. **Exportación CSV:**
   - Ir a Estadísticas de campaña → una campaña con ventas.
   - Hacer clic en "Exportar".
   - **Verificar:** La columna "Productos vendidos" muestra solo los productos del `SalesRecord`, no la lista completa de productos de la suscripción.

## 📝 Notas de Despliegue

- No se requieren migraciones de base de datos.
- No se requieren cambios de configuración.
- Este ticket tiene un commit en `utopia-crm` (este repo) y uno en `utopia-crm-ladiaria`. Ambas ramas deben mergearse juntas.

## 🎓 Decisiones de Diseño

El fix se aplicó en `CampaignStatisticsDetailView` y no en las vistas de suscripción, porque el dato de origen ya era correcto — `SalesRecord.products` contenía solo los productos vendidos. El problema era que la vista de estadísticas ignoraba el `SalesRecord` y leía los productos de la suscripción directamente.

Esto es una alineación de comportamiento y no una corrección de bug estricta: `SalesRecordFilterManagersView` ya mostraba el dato correcto. Los usuarios no conocían esa vista y esperaban la misma semántica en estadísticas de campaña. La decisión fue hacer ambas vistas consistentes.

---

- **Fecha:** 2026-04-06
- **Autor:** Tanya Tree + Claude Sonnet 4.6
- **Branch:** t1088
- **Tipo de cambio:** Mejora / Corrección de comportamiento
- **Módulos afectados:** Support (Estadísticas de Campaña, Registros de Ventas)
