# Amounts not in the local currency show their currency

- **Date:** 2026-11-16
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#143
- **Type:** UX Improvement
- **Component:** Core (template tags), Invoicing, Support (contact detail)
- **Impact:** User Experience

## 🎯 Summary

Since subscriptions and invoices have a currency (it/utopia-crm-ladiaria#120), there are invoices in USD (PayPal, it/utopia-crm-ladiaria#64). Several screens showed their amounts with no currency, or worse, with a `$` in front: the "Latest payment" of a USD 6 invoice read "$6,00", which anyone in Uruguay reads as pesos. A new template filter, `with_currency`, puts the currency code in front of an amount when the currency is not the local one, and leaves it untouched when it is. So **the screens in the local currency do not change at all**: only the amounts in another currency gain a prefix.

## ✨ Changes

### 1. The `with_currency` filter

**File:** `core/templatetags/core_tags.py`

```python
@register.filter
def with_currency(amount, currency):
    if amount is None or amount == "" or is_default_currency(currency):
        return amount
    return f"{currency} {formats.localize(amount)}"
```

Used as `{{ amount|with_currency:currency }}`. In the local currency it returns the amount itself, so the template renders it exactly as before. In another currency it formats the number with `formats.localize`, so the decimal separator matches the rest of the screen ("USD 6,00" in Spanish).

### 2. `Invoice.in_default_currency`

**File:** `invoicing/models.py`

The same property `Subscription` already had. The contact overview uses it for "Latest payment", which keeps its `$` for invoices in pesos.

### 3. The contact overview

**Files:** `support/templates/contact_detail/tabs/_overview.html`, `support/templates/contact_detail/tabs/includes/_overview_subscription_list_item.html`, `support/templates/contact_detail/tabs/includes/_subscription_card.html`

- **Latest payment:** `$6,00` in pesos as before; `USD 6,00` in another currency.
- **Subscription balance:** with the subscription's currency.
- **Price:** the whole line is hidden for subscriptions not in the local currency (overview and subscriptions tab). It said "There are no prices in this currency", while the currency is on the next line. The msgid is no longer used and was removed from the Spanish `.po`.

### 4. The invoices tab

**File:** `support/templates/contact_detail/htmx/_invoices_htmx.html`

The Amount column, with the invoice's currency. The customization package of la diaria overrides this template and makes the same change (it/utopia-crm-ladiaria MR of the same branch).

### 5. The invoice detail

**File:** `invoicing/templates/invoice/invoice_detail.html`

Amount and price of the product items, amount of the discount items, and the totals (products, discounts, rounding and total), all with the invoice's currency. The "Amount" field at the top is left as is: the "Currency" field is right below it.

## 📁 Files Modified

- **`core/templatetags/core_tags.py`** — The `with_currency` filter
- **`invoicing/models.py`** — `Invoice.in_default_currency`
- **`support/templates/contact_detail/tabs/_overview.html`** — Latest payment
- **`support/templates/contact_detail/tabs/includes/_overview_subscription_list_item.html`** — Balance, and no price line in another currency
- **`support/templates/contact_detail/tabs/includes/_subscription_card.html`** — No price line in another currency
- **`support/templates/contact_detail/htmx/_invoices_htmx.html`** — Amount column
- **`invoicing/templates/invoice/invoice_detail.html`** — Items and totals
- **`locale/es/LC_MESSAGES/django.po`** — Removed the msgid no longer used
- **`tests/test_currency.py`** — Tests for the filter, the property and the screens
- **`CHANGELOG.md`** — Entry for this change

## 🧪 Manual Testing

**Automated tests** (`tests/test_currency.py`): the filter leaves local amounts and `None` untouched and puts the currency in front of the others, localized; the latest payment, the invoices tab and the invoice detail show "USD" for an invoice in dollars; the same screens are unchanged for an invoice in pesos; the overview shows no price line for a subscription in dollars.

1. **Happy path, an invoice in another currency:**
   - Open a contact with a paid invoice in USD.
   - **Verify:** "Latest payment" says `USD 6,00`, not `$6,00`. The Invoices tab says `USD 6,00` in the Amount column. The invoice detail shows `USD` in front of the items and totals.

2. **Edge case, the local currency:**
   - Open a contact whose invoices are all in pesos.
   - **Verify:** Everything looks exactly as before: `$` in "Latest payment", bare numbers in the invoices tab and the invoice detail.

3. **A subscription in another currency:**
   - Open the overview and the subscriptions tab of a contact with a USD subscription.
   - **Verify:** There is no "Price" line, and "Currency: USD" is shown.

## 📝 Deployment Notes

- No migrations, no settings. Compile the messages (`compilemessages`) as usual.
- **Goes before** the customization package's MR of the same branch, whose invoices tab uses the filter.

## 🎓 Design Decisions

- **The prefix only for other currencies:** the local currency is the usual case, and its screens stay as people know them.
- **A filter instead of a model method:** the amounts come from several places (invoice, items, aggregates, subscription balance), and the filter takes any of them plus a currency.
- **The code ("USD"), not a symbol:** `$` is exactly the ambiguity being fixed.

---

- **Date:** 2026-11-16
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl143-moneda-montos
- **Type:** UX Improvement
- **Modules affected:** core, invoicing, support
