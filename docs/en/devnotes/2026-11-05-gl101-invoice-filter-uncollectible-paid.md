# Invoice filter: uncollectible invoices that were paid or debited

- **Date:** 2026-11-05
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#101
- **Type:** Enhancement
- **Component:** Invoicing
- **Impact:** Reports

## 🎯 Summary

The status filter of the invoice list takes a single option, so there was no way to find the invoices written off as uncollectible that were collected anyway. A new option does it, and leaves out canceled invoices, because that money may not have stayed.

## ✨ Changes

### 1. New status option

**File:** `invoicing/filters.py`

```python
queryset.filter(Q(paid=True) | Q(debited=True), uncollectible=True, canceled=False)
```

The "Uncollectible" option does not change: it still brings all of them.

## 📁 Files Modified

- **`invoicing/filters.py`** — The new option
- **`locale/es/LC_MESSAGES/django.po`** — Its translation

## 📁 Files Created

- **`tests/test_invoice_filter_uncollectible.py`** — What the option brings and leaves out

## 🧪 Manual Testing

1. **Happy path:**
   - In the invoice list, choose "Uncollectible, paid or debited" as the status.
   - **Verify:** Each invoice is uncollectible and paid or debited, and the total at the top adds them up.

2. **Edge case, canceled:**
   - Take an uncollectible invoice that was paid and then canceled.
   - **Verify:** It does not show up with this option, and it does show up with "Uncollectible".

## 📝 Deployment Notes

No migrations required. The server compiles the translation.

---

- **Date:** 2026-11-05
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl101-filtro-incobrables-pagas
- **Type:** Enhancement
- **Modules affected:** invoicing
