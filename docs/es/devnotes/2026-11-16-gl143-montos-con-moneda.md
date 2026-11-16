# Los montos que no están en la moneda local muestran su moneda

- **Fecha:** 2026-11-16
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#143
- **Tipo:** Mejora de UX
- **Componente:** Core (template tags), Invoicing, Support (ficha del contacto)
- **Impacto:** Experiencia de usuario

## 🎯 Resumen

Desde que las suscripciones y las facturas tienen moneda (it/utopia-crm-ladiaria#120), hay facturas en USD (PayPal, it/utopia-crm-ladiaria#64). Varias pantallas mostraban sus montos sin moneda, o peor, con un `$` adelante: el «Último pago» de una factura de USD 6 decía «$6,00», que en Uruguay cualquiera lee como pesos. Un filtro de template nuevo, `with_currency`, le pone adelante el código de la moneda a un monto cuando la moneda no es la local, y lo deja intacto cuando lo es. Así, **las pantallas en moneda local no cambian en nada**: sólo los montos en otra moneda ganan el prefijo.

## ✨ Cambios

### 1. El filtro `with_currency`

**Archivo:** `core/templatetags/core_tags.py`

```python
@register.filter
def with_currency(amount, currency):
    if amount is None or amount == "" or is_default_currency(currency):
        return amount
    return f"{currency} {formats.localize(amount)}"
```

Se usa como `{{ amount|with_currency:currency }}`. En la moneda local devuelve el monto mismo, así que el template lo muestra exactamente como antes. En otra moneda formatea el número con `formats.localize`, para que el separador decimal coincida con el resto de la pantalla («USD 6,00» en español).

### 2. `Invoice.in_default_currency`

**Archivo:** `invoicing/models.py`

La misma property que ya tenía `Subscription`. La vista general del contacto la usa para el «Último pago», que conserva su `$` en las facturas en pesos.

### 3. La vista general del contacto

**Archivos:** `support/templates/contact_detail/tabs/_overview.html`, `support/templates/contact_detail/tabs/includes/_overview_subscription_list_item.html`, `support/templates/contact_detail/tabs/includes/_subscription_card.html`

- **Último pago:** `$6,00` en pesos, como antes; `USD 6,00` en otra moneda.
- **Saldo de la suscripción:** con la moneda de la suscripción.
- **Precio:** la línea entera se oculta en las suscripciones que no están en moneda local (vista general y pestaña Suscripciones). Decía «No hay precios en esta moneda», y la moneda está en la línea de abajo. El msgid quedó sin uso y se sacó del `.po` en español.

### 4. La pestaña Facturas

**Archivo:** `support/templates/contact_detail/htmx/_invoices_htmx.html`

La columna Monto, con la moneda de la factura. El paquete de customización de la diaria pisa este template y hace el mismo cambio (MR de it/utopia-crm-ladiaria de la misma rama).

### 5. El detalle de la factura

**Archivo:** `invoicing/templates/invoice/invoice_detail.html`

Monto y precio de los ítems de productos, monto de los ítems de descuento, y los totales (productos, descuentos, redondeo y total), todos con la moneda de la factura. El campo «Monto» de arriba queda como estaba: el campo «Moneda» está justo abajo.

## 📁 Archivos modificados

- **`core/templatetags/core_tags.py`** — El filtro `with_currency`
- **`invoicing/models.py`** — `Invoice.in_default_currency`
- **`support/templates/contact_detail/tabs/_overview.html`** — Último pago
- **`support/templates/contact_detail/tabs/includes/_overview_subscription_list_item.html`** — Saldo, y sin línea de precio en otra moneda
- **`support/templates/contact_detail/tabs/includes/_subscription_card.html`** — Sin línea de precio en otra moneda
- **`support/templates/contact_detail/htmx/_invoices_htmx.html`** — Columna Monto
- **`invoicing/templates/invoice/invoice_detail.html`** — Ítems y totales
- **`locale/es/LC_MESSAGES/django.po`** — Se sacó el msgid que quedó sin uso
- **`tests/test_currency.py`** — Tests del filtro, la property y las pantallas
- **`CHANGELOG.md`** — Entrada de este cambio

## 🧪 Pruebas manuales

**Tests automáticos** (`tests/test_currency.py`): el filtro deja intactos los montos locales y `None`, y les pone la moneda adelante a los otros, localizados; el último pago, la pestaña Facturas y el detalle de la factura muestran «USD» para una factura en dólares; las mismas pantallas no cambian para una factura en pesos; la vista general no muestra la línea de precio de una suscripción en dólares.

1. **Caso normal, una factura en otra moneda:**
   - Abrir un contacto con una factura paga en USD.
   - **Verificar:** «Último pago» dice `USD 6,00`, no `$6,00`. La pestaña Facturas dice `USD 6,00` en la columna Monto. El detalle de la factura muestra `USD` adelante de los ítems y los totales.

2. **Caso borde, la moneda local:**
   - Abrir un contacto con todas sus facturas en pesos.
   - **Verificar:** Todo se ve exactamente igual que antes: `$` en «Último pago», números solos en la pestaña Facturas y en el detalle de la factura.

3. **Una suscripción en otra moneda:**
   - Abrir la vista general y la pestaña Suscripciones de un contacto con una suscripción en USD.
   - **Verificar:** No hay línea «Precio», y se muestra «Moneda: USD».

## 📝 Notas de despliegue

- Sin migraciones ni settings. Compilar los mensajes (`compilemessages`) como siempre.
- **Va antes** que el MR del paquete de customización de la misma rama, cuya pestaña Facturas usa el filtro.

## 🎓 Decisiones de diseño

- **El prefijo sólo para otras monedas:** la moneda local es el caso de siempre, y sus pantallas quedan como la gente las conoce.
- **Un filtro y no un método del modelo:** los montos salen de varios lados (factura, ítems, agregados, saldo de la suscripción), y el filtro acepta cualquiera de ellos más una moneda.
- **El código («USD») y no un símbolo:** `$` es justamente la ambigüedad que se arregla.

---

- **Fecha:** 2026-11-16
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Rama:** gl143-moneda-montos
- **Tipo:** Mejora de UX
- **Módulos afectados:** core, invoicing, support
