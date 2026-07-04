# Canceled Invoices Report View

- **Date:** 2026-04-08
- **Author:** Tanya Tree + Claude Sonnet 4.6
- **Ticket:** t0243
- **Type:** Feature
- **Component:** Invoicing
- **Impact:** Operator Workflow, Access Control, Performance

## 🎯 Summary

A new `CanceledInvoicesReportView` was added to the `invoicing` app, making the canceled invoices CSV report part of the open-source base CRM. The report previously existed only as a function view (`facturas_anuladas`) inside the `utopia-crm-ladiaria` private customisation package. Moving it to the base app makes it available to all deployments, applies access control consistently, and fixes potential N+1 query problems that the original function view had.

## ✨ Changes

### 1. Class-based view with access control

**File:** `invoicing/views.py`

`CanceledInvoicesReportView` is a class-based view that mixes in `BreadcrumbsMixin`, `UserPassesTestMixin`, and `TemplateView`. Access is restricted by `test_func` to members of the `"Admins"` group, the `"Finances"` group, and superusers:

```python
def test_func(self):
    user = self.request.user
    return user.is_superuser or user.groups.filter(name__in=["Admins", "Finances"]).exists()
```

`GET` renders a simple date-range form using HTML5 `<input type="date">` pickers. `POST` queries canceled invoices within the submitted date range, streams the results as a CSV download, and returns an `HttpResponse` with `Content-Type: text/csv`.

### 2. N+1 prevention with prefetch_related

**File:** `invoicing/views.py`

The queryset uses `prefetch_related` to load line items and credit notes in two additional queries rather than one per invoice:

```python
Invoice.objects.filter(
    canceled=True,
    cancelation_date__date__range=(date_from, date_to),
).prefetch_related("invoiceitem_set", "creditnote_set")
```

This keeps the view fast on date ranges that return hundreds of invoices.

### 3. Translated CSV column headers

**File:** `invoicing/views.py`

All column headers passed to `csv.writer` are wrapped in `_()` so they respect the active language of the Django installation:

```python
writer.writerow([
    _("Invoice number"), _("Date"), _("Contact"), _("Amount"),
    _("Cancelation date"), _("Credit note"), ...
])
```

### 4. URL registration

**File:** `invoicing/urls.py`

A new named URL `canceled_invoices_report` maps the path `canceled_invoices_report/` to the new view.

### 5. Template

**File:** `invoicing/templates/canceled_invoices_report.html`

An AdminLTE card wrapping a minimal form: two HTML5 date inputs (From / To) and a Submit button. The form uses `method="post"` so the date range is sent in the request body rather than the URL, consistent with other report views in the app.

## 📁 Files Modified

- **`invoicing/views.py`** — Added `CanceledInvoicesReportView` and updated imports
- **`invoicing/urls.py`** — Added `canceled_invoices_report/` URL and import of the new view

## 📁 Files Created

- **`invoicing/templates/canceled_invoices_report.html`** — Date-range form for the report download

## 📚 Technical Details

- `UserPassesTestMixin` redirects unauthenticated users to the login page automatically; authenticated users who fail `test_func` receive a 403 response.
- The view responds to `GET` and `POST` within the same class. `get()` renders the form; `post()` validates the dates, builds the queryset, and returns the CSV response.
- `prefetch_related("invoiceitem_set", "creditnote_set")` is evaluated lazily when iterating inside `post()`, so no extra queries are fired on `GET`.
- The original `facturas_anuladas` function view in `utopia-crm-ladiaria` can be removed or redirected to this URL once this version is deployed to all environments that used it.

## 🧪 Manual Testing

1. **Happy path — Finances user downloads the report:**
   - Log in as a user in the `"Finances"` group.
   - Navigate to `invoicing/canceled_invoices_report/`.
   - **Verify:** The page loads with a date-range form (two date pickers and a Submit button).
   - Enter a date range that includes known canceled invoices and submit.
   - **Verify:** A CSV file is downloaded. Open it and confirm the columns are present and data matches the expected canceled invoices within the range.

2. **Happy path — superuser downloads the report:**
   - Log in as a superuser.
   - Navigate to `invoicing/canceled_invoices_report/` and submit a date range.
   - **Verify:** The CSV downloads successfully, same as above.

3. **Edge case — user without the required group is denied:**
   - Log in as a regular staff user not in `"Admins"` or `"Finances"` and not a superuser.
   - Navigate to `invoicing/canceled_invoices_report/`.
   - **Verify:** A 403 Forbidden response is returned; no form or CSV is served.

4. **Edge case — date range with no canceled invoices:**
   - Submit a date range in the distant future (or any range with no canceled invoices).
   - **Verify:** A CSV is downloaded with only the header row and no data rows.

5. **Edge case — invoice with multiple line items:**
   - Identify a canceled invoice with more than one `InvoiceItem`. Submit a range that includes it.
   - **Verify:** The CSV row for that invoice correctly reflects data from the prefetched `invoiceitem_set` without triggering extra queries (check Django debug toolbar or test with `assertNumQueries` if available).

## 📝 Deployment Notes

- No database migrations required.
- No configuration changes required.
- Ensure the `"Admins"` and `"Finances"` groups exist in the target environment; users who should access the report must be members of at least one of them (or be superusers).
- The legacy `facturas_anuladas` view in `utopia-crm-ladiaria` can be retired after this version is deployed; its URL can be redirected to `canceled_invoices_report` or simply removed.

## 🎓 Design Decisions

The view was implemented as a class-based view (`TemplateView` + `UserPassesTestMixin`) rather than a function view to match the pattern used by other report and filter views added recently to the app. `UserPassesTestMixin` provides a clean, declarative access-control hook without needing a decorator or manual permission check at the top of each handler method.

`prefetch_related` was chosen over `select_related` because `invoiceitem_set` and `creditnote_set` are reverse FK / M2M relations that cannot be JOINed efficiently with `select_related`. Two extra queries for any result set is much better than one query per invoice.

HTML5 native date pickers were used for the form inputs in keeping with the project's UI guidelines: use `<input type="date">` when no richer picker behaviour is needed, avoiding any additional JavaScript dependency.

## 🚀 Future Improvements

- Add server-side validation of the submitted date range (reject reversed or unreasonably wide ranges) with a user-facing error message.
- Consider adding a filter for invoice serie or product type to allow more targeted exports.
- Add an optional "include credit note details" toggle to expand credit note columns in the CSV.

---

- **Date:** 2026-04-08
- **Author:** Tanya Tree + Claude Sonnet 4.6
- **Branch:** t0243
- **Type:** Feature
- **Modules affected:** Invoicing
