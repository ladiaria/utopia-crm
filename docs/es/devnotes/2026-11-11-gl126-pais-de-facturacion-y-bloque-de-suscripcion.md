# El detalle de la factura muestra el país de facturación, y la tarjeta de suscripción suma un bloque a todo el ancho

- **Fecha:** 2026-11-11
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#126
- **Tipo:** Mejora
- **Componente:** Invoicing, Support (ficha del contacto)
- **Impacto:** Interfaz, extensibilidad

## 🎯 Resumen

Dos cosas chicas que necesitaban las pantallas de PayPal del paquete de customización (it/utopia-crm-ladiaria#64). `Invoice.billing_country` se guardaba pero ninguna pantalla lo mostraba: ahora el detalle de la factura lo muestra debajo de la ciudad de facturación, sólo cuando la factura lo tiene. Y la tarjeta de la suscripción en la ficha del contacto tenía un solo bloque de extensión, `extra_information`, dentro de una columna de un cuarto del ancho: alcanza para una línea, pero una tabla no entra. Un bloque nuevo y vacío, `extra_sections`, queda a todo el ancho debajo de los datos de la suscripción.

## ✨ Cambios

### 1. El país de facturación en el detalle de la factura

**Archivo:** `invoicing/templates/invoice/invoice_detail.html`

```django
{% if object.billing_country %}
  <div class="form-group">
    <label>{% trans "Billing Country" %}</label>
    <p>{{ object.billing_country }}</p>
  </div>
{% endif %}
```

Sólo cuando la factura tiene país. Las facturas en la moneda local no lo completan, y un `-` vacío en todas sería ruido.

### 2. `extra_sections` en la tarjeta de suscripción

**Archivo:** `support/templates/contact_detail/tabs/includes/_subscription_card.html`

Un bloque vacío dentro del `card-body`, después de la fila con los datos de la suscripción y antes del pie con las acciones. Lo llena el `_subscription_card.html` de un paquete, que extiende el del base. Está documentado en `CLAUDE.md`, con los otros puntos de extensión.

## 📁 Archivos modificados

- **`invoicing/templates/invoice/invoice_detail.html`** — El país de facturación
- **`support/templates/contact_detail/tabs/includes/_subscription_card.html`** — El bloque `extra_sections`
- **`CLAUDE.md`** — El punto de extensión nuevo
- **`tests/test_currency.py`** — Test del país de facturación
- **`CHANGELOG.md`** — Entrada de este cambio

## 🧪 Pruebas manuales

**Tests automáticos** (`tests/test_currency.py`): el detalle de la factura muestra el país cuando la factura lo tiene, y no muestra un campo vacío cuando no. El test falla sin el cambio del template.

1. **Caso feliz:**
   - Abrir el detalle de una factura con país de facturación (una de PayPal, en la diaria).
   - **Verificar:** «País de facturación» aparece debajo de la ciudad.

2. **Caso borde, sin país:**
   - Abrir el detalle de una factura en la moneda local.
   - **Verificar:** No aparece el campo «País de facturación».

3. **El bloque, sin un paquete que lo llene:**
   - Abrir la pestaña de suscripciones de un contacto.
   - **Verificar:** La tarjeta se ve exactamente igual que antes.

## 📝 Notas de deployment

- Sin migraciones ni settings.
- **Va antes** de que el paquete de customización llene `extra_sections` (it/utopia-crm-ladiaria!245). Sin esto no se rompe nada, pero lo que el paquete pone ahí no aparece.

## 🎓 Decisiones de diseño

- **Un bloque nuevo en vez de ensanchar `extra_information`:** otros paquetes pueden estar usando `extra_information` para una o dos líneas; moverlo les cambiaría el diseño.
- **El país sólo cuando existe:** el campo lo completan sólo los flujos que facturan al exterior.

---

- **Fecha:** 2026-11-11
- **Autor:** Tanya Tree + Claude Opus 5.5
- **Rama:** gl126-pais-factura-y-bloque-suscripcion
- **Tipo:** Mejora
- **Módulos afectados:** invoicing, support
