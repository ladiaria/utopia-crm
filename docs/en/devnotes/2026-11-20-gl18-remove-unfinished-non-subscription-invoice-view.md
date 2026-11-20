# Remove the unfinished non-subscription invoice view

- **Date:** 2026-11-20
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#18
- **Type:** Refactor
- **Component:** Invoicing
- **Impact:** None for users (dead code)

## 🎯 Summary

`InvoiceNonSubscriptionCreateView` was a screen to create a one-off invoice by hand, without a subscription. It came in on 2024-08-14 with the one-shot invoice API (`1d2e1b4d`), and two days later its URL was commented out with `WIP: UI for creating invoices, unfinished. Uncomment when ready.` (`59104e57`). It was never finished. With no URL nobody could reach it, and it was also broken: it called `Contact.add_single_invoice_with_products(products)` without the required `payment_type`, so it would have raised `TypeError` if anyone had wired it up. This change deletes it along with its form and template.

## ✨ Changes

### 1. The view and its commented-out URL

**Files:** `invoicing/views.py`, `invoicing/urls.py`

- `InvoiceNonSubscriptionCreateView` is gone, and so is the commented `new_non_subscription/<int:contact_id>/` block (`create_non_subscription_invoice`).
- `CreateView` is no longer imported: this view was its only user. The other imports it used (`staff_member_required`, `method_decorator`, `get_object_or_404`, `Contact`, `settings`) are still used by other views and stay.

### 2. The form and the template

**Files:** `invoicing/forms.py`, `invoicing/templates/invoice_non_subscription_form.html`

`invoicing/forms.py` only held `InvoiceForm` and `InvoiceItemFormSet`, which only this view used, so the whole module is deleted.

## 📁 Files Modified

- **`invoicing/views.py`** — Removed `InvoiceNonSubscriptionCreateView` and the imports only it used
- **`invoicing/urls.py`** — Removed the commented-out URL
- **`CHANGELOG.md`** — Entry for this change

## 📁 Files Deleted

- **`invoicing/forms.py`** — `InvoiceForm` and `InvoiceItemFormSet`
- **`invoicing/templates/invoice_non_subscription_form.html`** — The view's template

## 📚 Technical Details

Before deleting, the whole `~/git` tree (base, la diaria's package, rponline, the CMS repos and the docs) was searched for `InvoiceNonSubscriptionCreateView`, `create_non_subscription_invoice`, `invoice_non_subscription_form`, `InvoiceForm`, `InvoiceItemFormSet` and `invoicing.forms`. The only matches outside these files were in old clones of a deployment that no longer uses the CRM. `OneshotDirectInvoiceForm` in la diaria's package is a different class and is not affected.

The template's strings stay in `locale/es/LC_MESSAGES/django.po` with stale `#:` references. They do no harm, and the next `makemessages -l es` marks them obsolete.

## 🧪 Manual Testing

1. **Invoicing screens still work:** open a contact's invoices, an invoice's detail and the invoice filter. **Verify:** they load as before.
2. **The old URL does not exist:** open `/invoicing/new_non_subscription/1/`. **Verify:** 404, as before (the URL was already commented out).

## 📝 Deployment Notes

- No database migrations required. No settings.

---

- **Date:** 2026-11-20
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl18-gl91-codigo-muerto
- **Type:** Refactor
- **Modules affected:** Invoicing
