# The invoice admin requires an amount

- **Date:** 2026-09-15
- **Author:** Tanya Tree + Claude Opus 5
- **Ticket:** fix/invoice-admin-amount-required
- **Type:** Bug Fix
- **Component:** Invoicing (admin)
- **Impact:** Data Integrity, Collections

## 🎯 Summary

The Django admin allowed saving an invoice with an empty amount, because `Invoice.amount` is `null=True, blank=True`
and the admin form inherited that. At la diaria, one invoice edited that way was included in the file sent every
night to a payment network (SISTARBANC), which rejected the **whole file** because of that single empty amount. For
five days no new invoice could be paid through that network. The admin form now requires the amount.

## ✨ Changes

### 1. Admin form with a required amount

**File:** `invoicing/admin.py`

New `InvoiceAdminForm`, set as `InvoiceAdmin.form`. It keeps every field of the model and only marks `amount` as
required:

```python
def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    if "amount" in self.fields:
        self.fields["amount"].required = True
```

The `if` guards against subclasses that remove `amount` from the fieldsets or make it read-only: in that case the
field is not in the form and there is nothing to require.

Customization packages that subclass `InvoiceAdmin` (such as `InvoiceAdminWithExtension` in `utopia_crm_ladiaria`)
inherit the form without any change on their side.

## 📁 Files Modified

- **`invoicing/admin.py`** — `InvoiceAdminForm` with `amount` required, used by `InvoiceAdmin`.
- **`CHANGELOG.md`** — Entry for this change.

## 📁 Files Created

- **`tests/test_invoice_admin.py`** — Builds the form of whatever admin is registered for `Invoice` and checks that
  an empty amount is rejected and a present one is accepted. The empty-amount test fails without the change.

## 📚 Technical Details

- **The model is not changed.** Making the column `NOT NULL` would need a data migration for the old invoices
  that have no amount, and would affect every code path that creates invoices. The problem was a person saving an
  empty field by hand, and that only happens in the admin.
- **Zero is still accepted.** There are legitimate zero-amount invoices. Downstream exports that cannot send a
  zero amount must filter it themselves (at la diaria, the SISTARBANC export skips null, zero and negative amounts
  and sends an alert).
- **Old invoices without an amount** can still be viewed in the admin, but saving them requires filling it in.
- No new translatable strings: the error is Django's standard "This field is required." message.

## 🧪 Manual Testing

1. **Editing with an amount (happy path):**
   - Open an invoice in the admin, change the notes and save.
   - **Verify:** it saves as before.

2. **Clearing the amount (edge case):**
   - Open an invoice in the admin, clear the amount and save.
   - **Verify:** the form is shown again with "This field is required." on the amount, and the history of the
     invoice has no new entry.

3. **Amount zero:**
   - Set the amount to `0` and save.
   - **Verify:** it saves.

## 📝 Deployment Notes

- No database migrations required.
- No translations to compile.
- No configuration changes.

## 🚀 Future Improvements

- Consider validating the amount at the model level (`clean`) so that other forms and imports get the same rule,
  after checking how many existing invoices have no amount.

---

- **Date:** 2026-09-15
- **Author:** Tanya Tree + Claude Opus 5
- **Branch:** fix/invoice-admin-amount-required
- **Type:** Bug Fix
- **Modules affected:** Invoicing
