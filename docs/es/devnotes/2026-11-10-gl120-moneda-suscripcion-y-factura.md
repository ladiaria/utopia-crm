# La suscripción y la factura tienen moneda

- **Fecha:** 2026-11-10
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#120
- **Tipo:** Funcionalidad
- **Componente:** Core, Invoicing
- **Impacto:** Modelo de datos, Facturación

## 🎯 Resumen

Hasta ahora todos los importes del CRM estaban, sin decirlo, en la moneda local. la diaria va a vender suscripciones en dólares por PayPal (it/utopia-crm-ladiaria#64), así que la suscripción y la factura ahora guardan su moneda (ISO 4217). La factura copia la moneda de la suscripción al facturarla, y guarda la cotización de su comprobante fiscal cuando se emite. Los precios de los productos siguen estando sólo en moneda local, así que la facturación de siempre se niega a facturar una suscripción en otra moneda, en vez de convertir. El monto de las notas de crédito pasa a decimal, porque un entero no puede guardar US$ 4,99. Para los datos existentes no cambia nada: todas las filas quedan en moneda local.

## ✨ Cambios

### 1. La moneda local, como setting

**Archivos:** `settings.py`, `util/currency.py`

`DEFAULT_CURRENCY` (por defecto `"UYU"`) es la moneda en la que están los precios de los productos. `get_default_currency()` la lee y es el valor por defecto de los campos nuevos. Es una función, así que las migraciones referencian la función y no congelan el valor de los settings con que se generaron. `is_default_currency(code)` es el chequeo que usa la facturación.

Vive en `util/`, al lado de `util/dates.py` (que ya da los defaults de fechas), para que `core` e `invoicing` la importen sin import circular.

### 2. `currency` en suscripciones y facturas, `exchange_rate` en facturas

**Archivos:** `core/models.py`, `invoicing/models.py`, `core/migrations/0124_historicalsubscription_currency_and_more.py`, `invoicing/migrations/0033_historicalinvoice_currency_and_more.py`

- `Subscription.currency` e `Invoice.currency`: `CharField(max_length=3)`, por defecto `get_default_currency`. Los modelos históricos también los tienen.
- `Invoice.exchange_rate`: `DecimalField(12, 6)`, nulo, la misma precisión que `ExchangeRate.rate`. Es la moneda local por unidad de la moneda de la factura, y **se fija al emitir el comprobante fiscal**, no al crear la factura: el contador de la diaria confirmó que la cotización es la del día hábil anterior a la emisión, y una factura se puede emitir días después de creada. Queda vacía en las facturas en moneda local.

En PostgreSQL 11 o más nuevo, agregar una columna con un valor por defecto fijo no reescribe la tabla, así que las migraciones son rápidas aun en la tabla de facturas y en las históricas.

### 3. La facturación copia la moneda, y nunca convierte

**Archivo:** `invoicing/utils.py`

`bill_subscription` copia `subscription.currency` a la factura. Antes, se niega a facturar una suscripción que no esté en moneda local:

```python
assert is_default_currency(subscription.currency), _(
    "The subscription is in %(currency)s and there are no prices in that currency, it can't be billed"
) % {"currency": subscription.currency}
```

Todavía no hay precios en otras monedas, así que facturarla pondría un precio en moneda local en una factura en moneda extranjera. La aserción es del mismo tipo que las que la función ya levanta, por ejemplo con una suscripción sin forma de pago, así que la facturación nocturna la reporta y sigue.

### 4. El monto de las notas de crédito, con centavos

**Archivos:** `invoicing/models.py`, `invoicing/migrations/0033_historicalinvoice_currency_and_more.py`

`CreditNote.amount` pasa de `PositiveIntegerField` a `DecimalField(10, 2)`, como `Invoice.amount`. Los valores existentes se convierten a numérico. Hoy el campo casi no se usa (nada lo lee en ninguno de los dos repos), así que el cambio es seguro.

### 5. Admin

**Archivos:** `core/admin.py`, `invoicing/admin.py`

- **Suscripción:** la moneda se ve al lado del saldo, sólo lectura: la pone quien crea la suscripción, y de ella dependen sus facturas.
- **Factura:** la moneda en el listado y como filtro; moneda y cotización en el formulario, sólo lectura; y `billing_country`, que no se mostraba, al lado del documento de facturación.

### 6. La moneda en las pantallas, sólo para ver

**Archivos:** `core/models.py`, `support/templates/contact_detail/tabs/includes/_overview_subscription_list_item.html`, `support/templates/contact_detail/tabs/includes/_subscription_card.html`, `invoicing/templates/invoice/invoice_detail.html`

La moneda es informativa: ningún formulario la edita. La ficha del contacto la muestra debajo del precio, en el resumen y en la tarjeta de la suscripción, y el detalle de la factura la muestra debajo del monto, con la cotización cuando la hay. Los paquetes de customización que extienden estas plantillas también la muestran.

`Subscription.in_default_currency` dice si la suscripción está en moneda local. Si no lo está, la ficha no muestra el precio que calcula el CRM (sería un precio en moneda local) y dice que no hay precios en esa moneda. `calc_price_from_products` y `get_price_for_full_period` no cambian: ponen precio al catálogo, que está en moneda local, y los usan unos 40 lugares.

## 📁 Archivos modificados

- **`settings.py`** — `DEFAULT_CURRENCY`
- **`core/models.py`** — `Subscription.currency`
- **`invoicing/models.py`** — `Invoice.currency`, `Invoice.exchange_rate`, `CreditNote.amount` decimal
- **`invoicing/utils.py`** — `bill_subscription` copia la moneda y rechaza otra
- **`core/admin.py`** — La moneda en el admin de la suscripción, sólo lectura
- **`invoicing/admin.py`** — Moneda, cotización y país de facturación en el admin de la factura
- **`support/templates/contact_detail/tabs/includes/_overview_subscription_list_item.html`**, **`_subscription_card.html`** — La moneda, y sin precio local para otra moneda
- **`invoicing/templates/invoice/invoice_detail.html`** — La moneda y la cotización
- **`locale/es/LC_MESSAGES/django.po`** — Traducciones de los textos nuevos
- **`CHANGELOG.md`** — Entrada de este cambio

## 📁 Archivos creados

- **`util/currency.py`** — `get_default_currency` e `is_default_currency`
- **`core/migrations/0124_historicalsubscription_currency_and_more.py`** — Moneda de la suscripción
- **`invoicing/migrations/0033_historicalinvoice_currency_and_more.py`** — Moneda y cotización de la factura, monto decimal de la nota de crédito
- **`tests/test_currency.py`** — Tests

## 🧪 Pruebas manuales

**Tests automatizados** (`tests/test_currency.py`): las filas nuevas toman la moneda local, el valor por defecto se lee de los settings al crear la fila, la factura copia la moneda de la suscripción, una suscripción en otra moneda no se factura y no se crea ninguna factura, la moneda local es la de los settings, las notas de crédito guardan los centavos, y la ficha del contacto y el detalle de la factura muestran la moneda, sin precio local para otra moneda. Pasa el suite completo del base (526 tests, sin `test_cmssync`, que necesita un CMS corriendo).

1. **Caso exitoso, facturar como siempre:**
   - Facturar una suscripción existente desde la pantalla del contacto.
   - **Verificar:** La factura se crea como antes, y su admin muestra «UYU» como moneda y la cotización vacía.

2. **Caso borde, una suscripción en otra moneda:**
   - En un shell, ponerle `currency = "USD"` a una suscripción y llamar a `subscription.bill()`.
   - **Verificar:** `AssertionError` que dice que la suscripción está en USD y que no hay precios en esa moneda; no se crea ninguna factura.

3. **Caso borde, el admin:**
   - Abrir una suscripción y una factura en el admin.
   - **Verificar:** La moneda se ve y no se puede editar; el listado de facturas se puede filtrar por moneda.

## 📝 Notas de despliegue

- **Se requieren migraciones:** `core 0124` e `invoicing 0033`. Correr `python manage.py migrate` después de deployar.
- Sin cambios de settings: `DEFAULT_CURRENCY` es `"UYU"` por defecto. Una instalación en otra moneda lo define en `local_settings.py` antes de migrar, así las filas existentes quedan en su moneda.
- Los totales que suman importes todavía no miran la moneda. Eso no cambia ningún número hasta que exista la primera factura en otra moneda, y es el paso siguiente (it/utopia-crm-ladiaria#64, «barrido de sumas»).

## 🎓 Decisiones de diseño

- **La moneda es de la suscripción, y la factura la copia:** una suscripción no mezcla monedas, así que todos los ítems de una factura están en la misma.
- **Nunca convertir:** sin precio en la moneda de la suscripción, la factura no se crea. Convertir facturaría un importe que nadie acordó.
- **La cotización se fija al emitir, no al crear:** es la del comprobante fiscal, y el comprobante se puede emitir después.
- **Todavía no hay tabla de precios por moneda:** las suscripciones en dólares de la diaria las cobra PayPal, al precio del plan de PayPal, y sus facturas se crean con lo que cobró PayPal, no con `bill_subscription`.
- **Un default que es una función:** un valor literal congelaría el de los settings con que se generó la migración.

## 🚀 Mejoras futuras

- Totales y reportes por moneda (it/utopia-crm-ladiaria#64).
- Precios por moneda, si alguna vez el propio CRM tiene que facturar una suscripción en otra moneda.

---

- **Fecha:** 2026-11-10
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Rama:** gl120-moneda
- **Tipo:** Funcionalidad
- **Módulos afectados:** core, invoicing, util
