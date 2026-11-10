# Money totals never mix currencies

- **Date:** 2026-11-10
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#123
- **Type:** Feature, Bug fix
- **Component:** Invoicing, Core, Support
- **Impact:** Reports, Data Accuracy

## 🎯 Summary

Invoices have a currency since it/utopia-crm-ladiaria#120, but every money total still added up `amount` regardless of it: with the first invoice in US dollars, US$ 13 would add up as 13 pesos. Now every total adds up the local currency only, and whatever is in another currency is shown apart, in its own. Until there is an invoice in another currency no number changes. On the way, the debtor list showed as "debt" everything the contact had ever been invoiced, paid invoices included; it now shows the overdue unpaid invoices.

## ✨ Changes

### 1. `split_by_currency`

**File:** `util/currency.py`

```python
local, others = split_by_currency(queryset)
# others: [{"currency": "USD", "count": 2, "total": Decimal("19.50")}]
```

It returns the rows in the local currency, which are the only ones a money total adds up, and a summary of the rest, one entry per currency. The summary is computed over the rows themselves by `pk`, because the queryset may come with joins and `distinct()` (the ladiaria reports filter by invoice items), and a `Sum` over a join adds a row up once per joined row.

### 2. The invoice filter

**Files:** `invoicing/views.py`, `invoicing/templates/invoice_filter.html`, `invoicing/templates/invoicing/_other_currency_totals.html`

Counts and sums (total, paid, pending, overdue, canceled, uncollectible) are in the local currency only, so a count never includes an invoice its sum leaves out. A notice above them lists what was left out per currency. The date range in the header still covers every filtered invoice: it describes the filter, it is not a money total. The notice is a reusable include.

### 3. The contact's debt

**Files:** `core/models.py`, `support/views/contacts.py`, `invoicing/views.py`, `support/templates/contact_detail/tabs/_overview.html`, `support/templates/contact_detail/tabs/_invoices.html`, `invoicing/templates/contact_invoices.html`, `invoicing/templates/invoicing/_debt_in_other_currencies.html`

`Contact.get_debt` returns the debt in the local currency, and `Contact.get_debt_in_other_currencies` the rest. The contact screen (overview and invoices tab) and the contact's invoice list show each debt in its currency, in its own alert.

### 4. The debtor list

**Files:** `support/views/all_views.py`, `support/templates/debtor_contacts.html`

The `debt` annotation was `Sum("invoice__amount")` with no filter: it added up every invoice of the contact. On a copy of production, a contact with 7 overdue invoices out of 101 showed $ 39,932 owed instead of $ 5,857. It now sums the overdue unpaid invoices in the local currency, with the same conditions as the owed invoices count. The total at the bottom is computed over those invoices, and what the filtered debtors owe in other currencies is shown apart. The CSV export already used `get_debt` and was right.

## 📁 Files Modified

- **`util/currency.py`** — `split_by_currency`
- **`core/models.py`** — `get_debt` in the local currency, `get_debt_in_other_currencies`
- **`invoicing/views.py`** — Invoice filter totals and the contact's invoice list
- **`support/views/contacts.py`** — The other-currency debt in the contact screen
- **`support/views/all_views.py`** — Debtor list: the debt is what is owed, in the local currency
- **`invoicing/templates/invoice_filter.html`**, **`invoicing/templates/contact_invoices.html`**, **`support/templates/contact_detail/tabs/_overview.html`**, **`support/templates/contact_detail/tabs/_invoices.html`**, **`support/templates/debtor_contacts.html`** — The notices
- **`locale/es/LC_MESSAGES/django.po`** — Translations
- **`CHANGELOG.md`** — Entry for this change

## 📁 Files Created

- **`invoicing/templates/invoicing/_other_currency_totals.html`** — What a total left out, per currency
- **`invoicing/templates/invoicing/_debt_in_other_currencies.html`** — The debt in other currencies
- **`tests/test_currency_totals.py`** — Tests

## 🧪 Manual Testing

**Automated tests** (`tests/test_currency_totals.py`, 7): the split, a joined queryset not adding a row up twice, the contact's debt and its screen, the invoice filter totals and notice, and the debtor list (debt and total, regression of the paid invoices). The whole base suite passes (536 tests, without `test_cmssync`).

1. **Happy path, nothing changes:**
   - Open the invoice filter and the debtor list.
   - **Verify:** No notice, and the invoice filter numbers are the same as before.

2. **Edge case, an invoice in another currency:**
   - In a shell, create an overdue invoice in `USD` for a contact, then open the contact, its invoices and the invoice filter.
   - **Verify:** The debt and the totals in pesos do not include it; it is shown apart as "USD …".

3. **Bug fix, the debtor list:**
   - Open the debtor list and compare a contact's debt with its contact screen.
   - **Verify:** They match.

## 📝 Deployment Notes

- No migrations required. Needs it/utopia-crm-ladiaria#120 (the currency fields), already in production.
- The debtor list numbers change (down): they now show what is owed.

## 🚀 Future Improvements

- Reports per currency and an "all in local currency" view converted with each invoice's rate (it/utopia-crm-ladiaria#64, D7).

---

- **Date:** 2026-11-10
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl123-sumas-por-moneda
- **Type:** Feature, Bug fix
- **Modules affected:** util, core, invoicing, support
