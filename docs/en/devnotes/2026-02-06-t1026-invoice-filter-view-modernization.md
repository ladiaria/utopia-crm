# t1026: Invoice Filter View Modernization

**Date:** 2026-02-06
**Type:** Refactor, Performance Optimization & UI Enhancement
**Component:** Invoice Filter (`invoicing`)
**Impact:** Performance, User Experience, Maintainability

## Summary

Comprehensive modernization of the invoice filter page: converted the function-based view to a class-based `FilterView`, optimized database queries, implemented streaming CSV export, enhanced the CSV with additional contact fields, added new filter options, and significantly improved the template UI/UX.

## Changes

### 1. View Conversion: FBV → CBV

**File:** `invoicing/views.py`

Converted `invoice_filter` function-based view to `InvoiceFilterView`, a class-based view inheriting from `FilterView` and `BreadcrumbsMixin`.

- `filterset_class = InvoiceFilter`
- `paginate_by = 200`, `page_kwarg = 'p'`
- `context_object_name = 'invoices'`
- Breadcrumbs: Home → Invoice filter
- Backward compatibility alias: `invoice_filter = InvoiceFilterView.as_view()`

### 2. Queryset Optimization

**File:** `invoicing/views.py`

- Added `select_related('contact', 'subscription')` — eliminates N+1 queries for both contact and subscription access (subscription was previously missing)
- Added `prefetch_related('invoiceitem_set')` — pre-loads invoice items for the description column

### 3. Streaming CSV Export

**File:** `invoicing/views.py`

Replaced `HttpResponse` with `StreamingHttpResponse` using a generator pattern with `io.StringIO` buffer. Uses `iterator(chunk_size=1000)` for memory-efficient processing of large datasets.

- Starts download immediately instead of building entire response in memory
- Prevents timeouts on large exports

### 4. Enhanced CSV Export Fields

**File:** `invoicing/views.py`

Added 4 new contact fields to the CSV export (after Contact ID):

- **ID document** (`contact.id_document`)
- **Email** (`contact.email`)
- **Phone** (`contact.phone`)
- **Mobile** (`contact.mobile`)

### 5. New Filter Fields

**File:** `invoicing/filters.py`

Added 3 new filters for finding invoices by contact information:

- **`contact_email`** — filters by `contact__email__icontains`
- **`contact_id_document`** — filters by `contact__id_document__icontains`
- **`contact_phone`** — searches both `contact__phone` and `contact__mobile` using `Q` objects

All filters include placeholder text and `autocomplete="off"` in their widget attrs.

### 6. Native HTML5 Date Pickers

**File:** `invoicing/filters.py`, `invoicing/templates/invoice_filter.html`

Replaced jQuery UI datepickers with native HTML5 `<input type="date">`:

- Changed all date filter widgets from `forms.TextInput` to `forms.DateInput(attrs={'type': 'date', 'autocomplete': 'off'})`
- Removed jQuery `.datepicker()` initialization from template
- Suppresses browser autofill suggestions

### 7. Default "Today" Filter on Initial Load

**File:** `invoicing/views.py`

When the page is loaded with no GET parameters, it now redirects to `?creation_date=today` so the "Today" option is visibly selected in the dropdown, matching the displayed data. Previously, the queryset was silently filtered to today but the dropdown showed empty, confusing users.

### 8. Statistics Card Redesign

**Files:** `invoicing/views.py`, `invoicing/templates/invoice_filter.html`

- Replaced the plain `callout` block with an AdminLTE **collapsible card** (`card-outline card-info`)
- Starts **expanded** by default, collapsible via `+`/`−` button
- Color-coded status badges: Paid (green), Pending (yellow), Overdue (red), Canceled (gray), Uncollectible (dark)
- Each badge shows count + dollar amount
- **Date range display**: shows oldest → newest invoice date in the header using `Min`/`Max` aggregation on `creation_date`
- Reset button styled as outline-danger with undo icon
- Amounts use `floatformat:"-2"` to drop unnecessary `.00` decimals

### 9. Filter Card Made Collapsible

**File:** `invoicing/templates/invoice_filter.html`

Wrapped the filter form in an AdminLTE collapsible card (`card-outline card-primary`) with a "Filters" header and `−` collapse button.

### 10. Table & Template Improvements

**File:** `invoicing/templates/invoice_filter.html`

- **Horizontal scroll**: Table wrapped in `.table-responsive-custom` with `overflow-x: auto` and a visual scroll indicator
- **Compact items column**: CSS removes bullet points from `<ul>`, adds subtle separator lines between items, each item is `nowrap`
- **`nowrap` on key columns**: Status, S/N, Payment type, dates, Amount, Contact name, ID — prevents awkward line breaks
- **Invoice link on ID**: Invoice ID is now a clickable link to the invoice detail page
- **Clean amounts**: `floatformat:"-2"` shows `245` instead of `245.00`, keeps `1251.50` as-is
- **Number field**: `autocomplete="off"` prevents browser from treating it as a credit card number
- **Table styling**: Added `table-striped table-bordered` classes

### 11. Filter Layout Reorganization

**File:** `invoicing/templates/invoice_filter.html`

Reorganized into 3 logical rows:

- **Row 1 (Contact info)**: Name, Email, ID document, Phone (with helper text "Searches both phone and mobile")
- **Row 2 (Invoice dates)**: Creation date + inline From/To range + Status + Payment type — all `col` flex so the row fills naturally whether custom date range is visible or not
- **Row 3 (Payment & serial)**: Payment from, Payment to, Series, Number, No serial

### 12. URL Configuration

**File:** `invoicing/urls.py`

Updated to use `InvoiceFilterView.as_view()` directly.

## Files Modified

- `invoicing/views.py` — New `InvoiceFilterView` CBV, streaming CSV, context with date range
- `invoicing/filters.py` — New contact filters, HTML5 date widgets, placeholders
- `invoicing/templates/invoice_filter.html` — Complete UI overhaul
- `invoicing/urls.py` — Updated to CBV

## Migration Notes

- No database migrations required
- All changes are view, filter, template, and URL level
- Backward compatible: `invoice_filter` alias still available

---

**Date:** 2026-02-06
**Issue:** t1026
**Type:** Refactor + UI Enhancement + Performance
**Priority:** Medium
