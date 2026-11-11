# The invoice detail shows the billing country, and the subscription card gets a full-width block

- **Date:** 2026-11-11
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#126
- **Type:** Enhancement
- **Component:** Invoicing, Support (contact detail)
- **Impact:** UI, Extensibility

## 🎯 Summary

Two small things the PayPal screens of the customization package needed (it/utopia-crm-ladiaria#64). `Invoice.billing_country` was saved but no screen showed it: the invoice detail now shows it under the billing city, only when the invoice has one. And the subscription card in the contact detail had a single extension block, `extra_information`, inside a quarter-width column: fine for a line, too narrow for a table. A new empty block, `extra_sections`, sits full width under the subscription details.

## ✨ Changes

### 1. The billing country in the invoice detail

**File:** `invoicing/templates/invoice/invoice_detail.html`

```django
{% if object.billing_country %}
  <div class="form-group">
    <label>{% trans "Billing Country" %}</label>
    <p>{{ object.billing_country }}</p>
  </div>
{% endif %}
```

Only when the invoice has a country. Invoices in the local currency don't fill it in, and an empty `-` on all of them would be noise.

### 2. `extra_sections` in the subscription card

**File:** `support/templates/contact_detail/tabs/includes/_subscription_card.html`

An empty block inside `card-body`, after the row with the subscription details and before the footer with the actions. A package's `_subscription_card.html`, extending the base one, fills it. Documented in `CLAUDE.md` with the other extension points.

## 📁 Files Modified

- **`invoicing/templates/invoice/invoice_detail.html`** — The billing country
- **`support/templates/contact_detail/tabs/includes/_subscription_card.html`** — The `extra_sections` block
- **`CLAUDE.md`** — The new extension point
- **`tests/test_currency.py`** — Test for the billing country
- **`CHANGELOG.md`** — Entry for this change

## 🧪 Manual Testing

**Automated tests** (`tests/test_currency.py`): the invoice detail shows the country when the invoice has one, and no empty field when it doesn't. The test fails without the template change.

1. **Happy path:**
   - Open the detail of an invoice with a billing country (a PayPal one, at la diaria).
   - **Verify:** "Billing Country" shows under the billing city.

2. **Edge case, no country:**
   - Open the detail of an invoice in the local currency.
   - **Verify:** There is no "Billing Country" field.

3. **The block, without a package filling it:**
   - Open the subscriptions tab of a contact.
   - **Verify:** The card looks exactly as before.

## 📝 Deployment Notes

- No migrations, no settings.
- **Goes before** the customization package fills `extra_sections` (it/utopia-crm-ladiaria!245). Without it nothing breaks, but what the package puts there doesn't show.

## 🎓 Design Decisions

- **A new block instead of widening `extra_information`:** other packages may already use `extra_information` for a line or two; moving it would change their layout.
- **The country only when it exists:** the field is filled only by flows that bill abroad.

---

- **Date:** 2026-11-11
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl126-pais-factura-y-bloque-suscripcion
- **Type:** Enhancement
- **Modules affected:** invoicing, support
