# Subscriptions and invoices have a currency

- **Date:** 2026-11-10
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#120
- **Type:** Feature
- **Component:** Core, Invoicing
- **Impact:** Data Model, Billing

## 🎯 Summary

Until now every amount in the CRM was implicitly in the local currency. la diaria is about to sell subscriptions in US dollars through PayPal (it/utopia-crm-ladiaria#64), so subscriptions and invoices now record their currency (ISO 4217). The invoice copies the subscription's currency when it is billed, and keeps the exchange rate of its fiscal document once it is issued. Product prices are still in the local currency only, so the regular billing refuses to bill a subscription in another currency instead of converting. Credit note amounts become decimal, because a whole number cannot hold US$ 4.99. Nothing changes for existing data: every row stays in the local currency.

## ✨ Changes

### 1. The local currency, as a setting

**Files:** `settings.py`, `util/currency.py`

`DEFAULT_CURRENCY` (default `"UYU"`) is the currency product prices are in. `get_default_currency()` reads it and is the default of the new fields. It is a callable, so the migrations reference the function and do not freeze the value of whatever settings generated them. `is_default_currency(code)` is the check billing uses.

It lives in `util/`, next to `util/dates.py` (which already provides the date defaults), so both `core` and `invoicing` import it without a circular import.

### 2. `currency` on subscriptions and invoices, `exchange_rate` on invoices

**Files:** `core/models.py`, `invoicing/models.py`, `core/migrations/0124_historicalsubscription_currency_and_more.py`, `invoicing/migrations/0033_historicalinvoice_currency_and_more.py`

- `Subscription.currency` and `Invoice.currency`: `CharField(max_length=3)`, default `get_default_currency`. The historical models get them too.
- `Invoice.exchange_rate`: `DecimalField(12, 6)`, nullable, the same precision as `ExchangeRate.rate`. It is the local currency per unit of the invoice currency, **set when the fiscal document is issued**, not when the invoice is created: la diaria's accountant confirmed that the rate is the one of the business day before the issue date, and an invoice can be issued days after it is created. It stays empty for invoices in the local currency.

On PostgreSQL 11+, adding a column with a constant default does not rewrite the table, so the migrations are quick even on the invoice and historical tables.

### 3. Billing copies the currency, and never converts

**File:** `invoicing/utils.py`

`bill_subscription` copies `subscription.currency` to the invoice. Before that, it refuses to bill a subscription that is not in the local currency:

```python
assert is_default_currency(subscription.currency), _(
    "The subscription is in %(currency)s and there are no prices in that currency, it can't be billed"
) % {"currency": subscription.currency}
```

There are no prices in other currencies yet, so billing one would put a local-currency price on a foreign-currency invoice. The assertion is the same kind the function already raises for a subscription without a payment type, so the nightly billing reports it and moves on.

### 4. Credit note amounts with cents

**Files:** `invoicing/models.py`, `invoicing/migrations/0033_historicalinvoice_currency_and_more.py`

`CreditNote.amount` goes from `PositiveIntegerField` to `DecimalField(10, 2)`, like `Invoice.amount`. Existing values are cast to numeric. The field is barely used today (nothing in either repository reads it), so the change is safe.

### 5. Admin

**Files:** `core/admin.py`, `invoicing/admin.py`

- **Subscription:** the currency is shown next to the balance, read-only: whoever creates the subscription sets it, and its invoices depend on it.
- **Invoice:** the currency in the list and as a filter; currency and exchange rate in the form, read-only; and `billing_country`, which was not shown, next to the billing document.

## 📁 Files Modified

- **`settings.py`** — `DEFAULT_CURRENCY`
- **`core/models.py`** — `Subscription.currency`
- **`invoicing/models.py`** — `Invoice.currency`, `Invoice.exchange_rate`, decimal `CreditNote.amount`
- **`invoicing/utils.py`** — `bill_subscription` copies the currency and refuses another one
- **`core/admin.py`** — Currency in the subscription admin, read-only
- **`invoicing/admin.py`** — Currency, exchange rate and billing country in the invoice admin
- **`locale/es/LC_MESSAGES/django.po`** — Translations of the new texts
- **`CHANGELOG.md`** — Entry for this change

## 📁 Files Created

- **`util/currency.py`** — `get_default_currency` and `is_default_currency`
- **`core/migrations/0124_historicalsubscription_currency_and_more.py`** — Subscription currency
- **`invoicing/migrations/0033_historicalinvoice_currency_and_more.py`** — Invoice currency and exchange rate, decimal credit note amount
- **`tests/test_currency.py`** — Tests

## 🧪 Manual Testing

**Automated tests** (`tests/test_currency.py`): new rows default to the local currency, the default is read from settings when the row is created, the invoice copies the subscription's currency, a subscription in another currency is not billed and no invoice is created, the local currency is the one in settings, and credit notes keep their cents. The whole base suite passes (523 tests, without `test_cmssync`, which needs a running CMS).

1. **Happy path, billing as always:**
   - Bill an existing subscription from the contact screen.
   - **Verify:** The invoice is created as before, and its admin shows "UYU" as its currency and an empty exchange rate.

2. **Edge case, a subscription in another currency:**
   - In a shell, set a subscription's `currency` to `"USD"` and call `subscription.bill()`.
   - **Verify:** `AssertionError` saying the subscription is in USD and there are no prices in that currency; no invoice is created.

3. **Edge case, the admin:**
   - Open a subscription and an invoice in the admin.
   - **Verify:** The currency is shown and cannot be edited; the invoice list can be filtered by currency.

## 📝 Deployment Notes

- **Migrations required:** `core 0124` and `invoicing 0033`. Run `python manage.py migrate` after deploying.
- No settings change: `DEFAULT_CURRENCY` defaults to `"UYU"`. An installation in another currency sets it in `local_settings.py` before migrating, so existing rows get its own currency.
- Totals that add up amounts do not look at the currency yet. That does not change any number until the first invoice in another currency exists, and it is the next step (it/utopia-crm-ladiaria#64, "barrido de sumas").

## 🎓 Design Decisions

- **The currency belongs to the subscription, and the invoice copies it:** a subscription does not mix currencies, so all the items of an invoice are in the same one.
- **Never convert:** without a price in the subscription's currency the invoice is not created. Converting would invoice an amount nobody agreed to.
- **The exchange rate is set at issue time, not at creation:** it is the rate of the fiscal document, and the document may be issued later.
- **No price table per currency yet:** la diaria's dollar subscriptions are charged by PayPal at the price of the PayPal plan, and their invoices are created from what PayPal charged, not by `bill_subscription`.
- **A callable default:** a literal default would freeze the value of the settings that generated the migration.

## 🚀 Future Improvements

- Totals and reports per currency (it/utopia-crm-ladiaria#64).
- Prices per currency, if a subscription in another currency ever needs to be billed by the CRM itself.

---

- **Date:** 2026-11-10
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl120-moneda
- **Type:** Feature
- **Modules affected:** core, invoicing, util
