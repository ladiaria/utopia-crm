# Ningún total de plata mezcla monedas

- **Fecha:** 2026-11-10
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#123
- **Tipo:** Funcionalidad, Corrección
- **Componente:** Invoicing, Core, Support
- **Impacto:** Reportes, Exactitud de los datos

## 🎯 Resumen

Las facturas tienen moneda desde it/utopia-crm-ladiaria#120, pero todos los totales de plata seguían sumando `amount` sin mirarla: con la primera factura en dólares, US$ 13 se sumarían como 13 pesos. Ahora todo total suma sólo la moneda local, y lo que esté en otra moneda se muestra aparte, en la suya. Hasta que haya una factura en otra moneda no cambia ningún número. De paso, el listado de deudores mostraba como «deuda» todo lo que se le había facturado al contacto, incluidas las facturas pagas; ahora muestra las facturas vencidas impagas.

## ✨ Cambios

### 1. `split_by_currency`

**Archivo:** `util/currency.py`

```python
local, others = split_by_currency(queryset)
# others: [{"currency": "USD", "count": 2, "total": Decimal("19.50")}]
```

Devuelve las filas en moneda local, que son las únicas que suma un total de plata, y un resumen del resto, una entrada por moneda. El resumen se calcula sobre las filas mismas, por `pk`, porque el queryset puede venir con joins y `distinct()` (los reportes de ladiaria filtran por ítems de factura), y una `Sum` sobre un join cuenta una fila una vez por cada fila unida.

### 2. El filtro de facturas

**Archivos:** `invoicing/views.py`, `invoicing/templates/invoice_filter.html`, `invoicing/templates/invoicing/_other_currency_totals.html`

Las cantidades y las sumas (total, pagas, pendientes, vencidas, anuladas, incobrables) son sólo en moneda local, así que una cantidad nunca incluye una factura que su suma deja afuera. Un aviso arriba lista lo que quedó afuera, por moneda. El rango de fechas del encabezado sigue abarcando todas las facturas filtradas: describe el filtro, no es un total de plata. El aviso es un include reutilizable.

### 3. La deuda del contacto

**Archivos:** `core/models.py`, `support/views/contacts.py`, `invoicing/views.py`, `support/templates/contact_detail/tabs/_overview.html`, `support/templates/contact_detail/tabs/_invoices.html`, `invoicing/templates/contact_invoices.html`, `invoicing/templates/invoicing/_debt_in_other_currencies.html`

`Contact.get_debt` devuelve la deuda en moneda local, y `Contact.get_debt_in_other_currencies`, el resto. La ficha del contacto (resumen y pestaña de facturas) y su listado de facturas muestran cada deuda en su moneda, en su propio aviso.

### 4. El listado de deudores

**Archivos:** `support/views/all_views.py`, `support/templates/debtor_contacts.html`

La anotación `debt` era `Sum("invoice__amount")` sin filtro: sumaba todas las facturas del contacto. En una copia de producción, un contacto con 7 facturas vencidas de 101 aparecía debiendo $ 39.932 en vez de $ 5.857. Ahora suma las facturas vencidas impagas en moneda local, con las mismas condiciones que la cantidad de facturas adeudadas. El total de abajo se calcula sobre esas facturas, y lo que los deudores filtrados deben en otras monedas se muestra aparte. La exportación a CSV ya usaba `get_debt` y estaba bien.

## 📁 Archivos modificados

- **`util/currency.py`** — `split_by_currency`
- **`core/models.py`** — `get_debt` en moneda local, `get_debt_in_other_currencies`
- **`invoicing/views.py`** — Totales del filtro de facturas y listado de facturas del contacto
- **`support/views/contacts.py`** — La deuda en otra moneda en la ficha
- **`support/views/all_views.py`** — Listado de deudores: la deuda es lo que se debe, en moneda local
- **`invoicing/templates/invoice_filter.html`**, **`invoicing/templates/contact_invoices.html`**, **`support/templates/contact_detail/tabs/_overview.html`**, **`support/templates/contact_detail/tabs/_invoices.html`**, **`support/templates/debtor_contacts.html`** — Los avisos
- **`locale/es/LC_MESSAGES/django.po`** — Traducciones
- **`CHANGELOG.md`** — Entrada de este cambio

## 📁 Archivos creados

- **`invoicing/templates/invoicing/_other_currency_totals.html`** — Lo que un total dejó afuera, por moneda
- **`invoicing/templates/invoicing/_debt_in_other_currencies.html`** — La deuda en otras monedas
- **`tests/test_currency_totals.py`** — Tests

## 🧪 Pruebas manuales

**Tests automatizados** (`tests/test_currency_totals.py`, 7): la separación, un queryset con join que no cuenta dos veces una fila, la deuda del contacto y su ficha, los totales y el aviso del filtro de facturas, y el listado de deudores (deuda y total, regresión de las facturas pagas). Pasa el suite completo del base (536 tests, sin `test_cmssync`).

1. **Caso exitoso, no cambia nada:**
   - Abrir el filtro de facturas y el listado de deudores.
   - **Verificar:** No hay aviso, y los números del filtro de facturas son los mismos de antes.

2. **Caso borde, una factura en otra moneda:**
   - En un shell, crear una factura vencida en `USD` para un contacto, y abrir el contacto, sus facturas y el filtro de facturas.
   - **Verificar:** La deuda y los totales en pesos no la incluyen; se muestra aparte como «USD …».

3. **Corrección, el listado de deudores:**
   - Abrir el listado de deudores y comparar la deuda de un contacto con su ficha.
   - **Verificar:** Coinciden.

## 📝 Notas de despliegue

- No se requieren migraciones. Necesita it/utopia-crm-ladiaria#120 (los campos de moneda), ya en producción.
- Los números del listado de deudores cambian (bajan): ahora muestran lo que se debe.

## 🚀 Mejoras futuras

- Reportes por moneda y una vista «todo en moneda local» convertida con la cotización de cada factura (it/utopia-crm-ladiaria#64, D7).

---

- **Fecha:** 2026-11-10
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Rama:** gl123-sumas-por-moneda
- **Tipo:** Funcionalidad, Corrección
- **Módulos afectados:** util, core, invoicing, support
