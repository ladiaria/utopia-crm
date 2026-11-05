# Invoice items no longer have an admin page of their own

- **Date:** 2026-11-04
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** gl96-sacar-admin-invoiceitem (it/utopia-crm-ladiaria#96)
- **Type:** Bug Fix
- **Component:** Invoicing (admin)
- **Impact:** Performance, Availability

## 🎯 Summary

Opening the change page of an invoice item in the admin could take the whole CRM down. `InvoiceItemAdmin` had no configuration, so the page built a dropdown with every invoice and another with every subscription. In production, with millions of invoices, the worker serving it kept growing after the browser gave up, reached 6.9 GB on an 8 GB server and was killed by the operating system, and other users got 502 errors for a few seconds. Nothing used that page: items are seen and edited in the inline of their invoice. So the page is removed rather than repaired.

## ✨ Changes

### 1. `InvoiceItem` is no longer registered in the admin

**File:** `invoicing/admin.py`

`InvoiceItemAdmin` is removed. `InvoiceItemInline` stays, and so do the invoice admin and the customization packages that reuse the inline.

### 2. Tests

**File:** `tests/test_invoice_admin.py`

- `InvoiceItem` has no admin of its own, so nobody brings the page back without seeing this test and its reason.
- The invoice change page still shows its items in the inline.

## 📁 Files Modified

- **`invoicing/admin.py`** — `InvoiceItemAdmin` removed.
- **`tests/test_invoice_admin.py`** — New `TestInvoiceItemOnlyThroughInvoice` class.
- **`CHANGELOG.md`** — Entry.

## 📁 Files Created

- **`docs/en/devnotes/2026-11-04-gl96-remove-invoice-item-admin.md`** — This devnote.
- **`docs/es/devnotes/2026-11-04-gl96-sacar-admin-de-items-de-factura.md`** — Spanish version.

## 📚 Technical Details

- **Why the browser giving up did not help:** the request keeps running in the worker while Django builds the page, so closing the tab does not free the memory.
- **Permissions:** the `InvoiceItem` model and its permissions stay, because the inline depends on them. Groups that have those permissions keep them.
- **Old links:** `/admin/invoicing/invoiceitem/` now answers 404. No template, view or `reverse()` in the known repositories points to it.

## 🧪 Manual Testing

1. **Items in the invoice (happy path):**
   - Open an invoice that has items in the admin (`/admin/invoicing/invoice/<id>/change/`).
   - **Verify:** the page loads quickly and its items appear in the inline, and can be edited.

2. **The page is gone (edge case):**
   - Go to `/admin/invoicing/invoiceitem/` and to `/admin/invoicing/invoiceitem/1/change/`.
   - **Verify:** both answer 404, and the invoicing section of the admin index no longer lists invoice items.

## 📝 Deployment Notes

- No database migrations required.
- No new translations.
- A customization package that imports `InvoiceItemAdmin` from `invoicing.admin` would fail on import. None of the known ones does: they only import `InvoiceItemInline`.

## 🎓 Design Decisions

- **Remove instead of adding `raw_id_fields`:** the fix would be just as short, but it would keep a page that nobody uses and that can edit an amount without going through its invoice. The inline already covers that.

## 🚀 Future Improvements

- The subscription add page has a similar, smaller problem: `SubscriptionAdminForm` only filters `billing_address` by contact when editing, so adding lists every address.
- A per-worker memory limit in uWSGI (`evil-reload-on-rss`) protects each deployment from any page with this problem. It belongs to the configuration of each server.

---

- **Date:** 2026-11-04
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl96-sacar-admin-invoiceitem
- **Type:** Bug Fix
- **Modules affected:** Invoicing
