# Se quita el modelo `Billing`, que no se usaba

- **Fecha:** 2026-10-27
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** gl65-remove-billing
- **Tipo:** Refactor
- **Componente:** Invoicing (modelos, vistas), fixtures
- **Impacto:** Modelo de datos, extensiones con FK a `Billing`

## 🎯 Resumen

`invoicing.Billing` modelaba las "corridas de facturación" de la época en que las facturas se generaban a mano: cada
corrida tenía un contador de progreso, un estado, una lista de contactos excluidos, y agrupaba las facturas que creaba
mediante `Invoice.billing`. Hace años que se factura por día y nada crea ni lee un `Billing` (en la diaria, la última
corrida es de abril de 2021). Se quitan el modelo, la FK en `Invoice`, la vista que listaba las facturas de una
corrida y su template, las opciones `BILLING_STATUS` y los permisos de "billing" de la fixture de grupos por defecto.
Lo encontró la diaria al revisar las sumas de importes para facturas en varias monedas (it/utopia-crm-ladiaria#65).

## ✨ Cambios

### 1. El modelo y la FK en `Invoice`

**Archivos:** `invoicing/models.py`, `invoicing/choices.py`, `invoicing/migrations/0031_remove_billing.py`

Se borran `Billing` y `BILLING_STATUS`. `Invoice.billing` (opcional, `SET_NULL`) se quita de `Invoice` y de
`HistoricalInvoice`. También se van los imports que sólo usaba `Billing` (`Q`, `User`, `Subscription`, `Contact`).

### 2. La vista inalcanzable y su template

**Archivos:** `invoicing/views.py`, `invoicing/templates/billing_invoices.html`

`billing_invoices` listaba las facturas de una corrida. Ninguna URL la enrutaba, así que ya era inalcanzable.

### 3. Permisos en la fixture de grupos por defecto

**Archivo:** `fixtures/default_groups.json`

Se quitan `add_billing` y `change_billing` de los dos grupos que los tenían. Sin el modelo, `loaddata` fallaría con
ellos.

### 4. `invoicing/api.py` importa `Subscription` de `core.models`

**Archivo:** `invoicing/api.py`

Lo importaba de `.models`, lo que sólo funcionaba porque `invoicing/models.py` lo importaba para `Billing`.

## 📁 Archivos Modificados

- **`invoicing/models.py`** — Se quitan `Billing` e `Invoice.billing`, y los imports que quedaron sin uso.
- **`invoicing/choices.py`** — Se quita `BILLING_STATUS`.
- **`invoicing/views.py`** — Se quita `billing_invoices`.
- **`invoicing/api.py`** — `Subscription` se importa de `core.models`.
- **`fixtures/default_groups.json`** — Se quitan los permisos `add_billing` / `change_billing`.

## 📁 Archivos Creados

- **`invoicing/migrations/0031_remove_billing.py`** — Quita `billing` de `Invoice` y de `HistoricalInvoice`, y borra
  `Billing`.

## 📁 Archivos Eliminados

- **`invoicing/templates/billing_invoices.html`** — Template de la vista eliminada.

## 📚 Detalles Técnicos

**No se borra ninguna factura.** La FK era `SET_NULL`, y quitar el campo elimina la columna (`ALTER TABLE ... DROP
COLUMN`), no filas. En PostgreSQL es un cambio de catálogo, rápido incluso con un `invoicing_invoice` grande.

**Extensiones con FK a `Billing`.** Un paquete de customización con un modelo que apunte a `Billing` (la diaria tenía
`BillingExtension`, un `OneToOneField`) tiene que borrar ese modelo en una migración propia, y esa migración tiene que
correr antes que `invoicing.0031_remove_billing`:

- **En una base existente**, alcanza con migrar el paquete antes que el base. Si no, `DROP TABLE invoicing_billing`
  falla, porque la restricción de la FK de la extensión depende de la tabla.
- **En una base nueva** (una instalación desde cero, una base de tests recreada), el orden no se puede elegir: Django
  planifica las apps en orden alfabético, `invoicing` corre antes que la mayoría de los nombres de paquete, y la
  migración vieja del paquete que crea la FK a `invoicing.Billing` falla porque el modelo ya no existe en el estado de
  migraciones. La migración del paquete que borra el modelo necesita un `run_before`:

```python
class Migration(migrations.Migration):
    dependencies = [("mypackage", "00XX_previous")]
    run_before = [("invoicing", "0031_remove_billing")]
    operations = [migrations.DeleteModel(name="BillingExtension")]
```

`run_before` apunta a una migración que ya tiene que existir; si no, Django lanza `NodeNotFoundError`. Por eso primero
sale (y se migra) el código del paquete que borra la extensión, después este cambio, y por último el `run_before` en
el paquete.

## 🧪 Pruebas Manuales

1. **Migración en una base existente:**
   - Con cualquier extensión que apunte a `Billing` ya borrada, ejecutar `python manage.py migrate invoicing`.
   - **Verificar:** `0031_remove_billing` se aplica, `invoicing_billing` ya no existe y la cantidad de facturas es la
     misma que antes.

2. **Las facturas siguen funcionando:**
   - Abrir la lista de facturas de un contacto y el detalle de una factura vieja que tenía corrida de facturación.
   - **Verificar:** las dos páginas cargan como antes.

3. **Fixture de grupos por defecto:**
   - En una base de prueba, ejecutar `python manage.py loaddata default_groups`.
   - **Verificar:** carga sin errores y el grupo Finances ya no tiene permisos de `billing`.

4. **Caso borde — base nueva con una extensión:**
   - Con un paquete de customización que todavía tenga su modelo apuntando a `Billing` y sin `run_before`, crear una
     base desde cero (por ejemplo, correr los tests sin `--keepdb`).
   - **Verificar:** la migración falla en la migración del paquete que crea la FK. Con el `run_before`, pasa.

## 📝 Notas de Despliegue

- **Se requieren migraciones:** `invoicing.0031_remove_billing`.
- Si un paquete de customización tiene un modelo con FK a `Billing`, borrarlo y migrar el paquete **primero**.
- Opcional: `python manage.py remove_stale_contenttypes` elimina el content type de `billing` y los permisos huérfanos
  de los grupos.

---

- **Fecha:** 2026-10-27
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl65-remove-billing
- **Tipo de cambio:** Refactor
- **Módulos afectados:** Invoicing, Fixtures
