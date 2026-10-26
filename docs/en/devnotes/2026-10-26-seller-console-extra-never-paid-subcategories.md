# The seller console lists more than one "never paid" subcategory

- **Date:** 2026-10-26
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** gl60-consola-vendedor-no-consolidados
- **Type:** Enhancement
- **Component:** Support (seller console)
- **Impact:** User Experience

## 🎯 Summary

The seller console lists the open issues of the `ISSUE_SUBCATEGORY_NEVER_PAID` subcategory assigned to the seller,
and counts them on the campaign list. la diaria split "never paid" into variants, such as one for contacts that owe 2
or more invoices on the same subscription: when an issue moved to a variant it vanished from the console, although it
was still assigned to the seller. With the new optional setting `ISSUE_SUBCATEGORY_NEVER_PAID_EXTRA_SLUGS`, those
subcategories are listed and counted too (it/utopia-crm-ladiaria#60). Merged in PR #399; this entry was added
afterwards.

## ✨ Changes

### 1. `get_never_paid_subcategory_slugs()`

**File:** `support/views/seller_console.py`

Returns `ISSUE_SUBCATEGORY_NEVER_PAID` plus `ISSUE_SUBCATEGORY_NEVER_PAID_EXTRA_SLUGS`, or an empty list when the
first one is not set. Both seller console views use it, and a package that overrides `seller_console_list_campaigns`
can import it to count the same issues.

### 2. Never paid page and campaign list count

**Files:** `support/views/seller_console.py`, `support/templates/seller_console_never_paid_issues.html`

Both filter with `sub_category__slug__in`. With more than one subcategory, the page shows a Subcategory column (the
string was already translated); with one, the column would repeat the same value on every row, so it is hidden.

### 3. Setting

**File:** `local_settings_sample.py`

`ISSUE_SUBCATEGORY_NEVER_PAID_EXTRA_SLUGS`, commented out, with its explanation. It is read with `getattr`, so it has
no default in `settings.py`, like `ISSUE_SUBCATEGORY_NEVER_PAID`.

## 📁 Files Modified

- **`support/views/seller_console.py`** — `get_never_paid_subcategory_slugs()` and its use in both views.
- **`support/templates/seller_console_never_paid_issues.html`** — Optional Subcategory column.
- **`local_settings_sample.py`** — The new setting.

## 📁 Files Created

- **`tests/test_seller_console_never_paid.py`** — 6 tests: the slug list with and without extras or the base setting,
  the page listing both subcategories (and not other subcategories, finished issues or other sellers' issues), the
  hidden column, and the campaign list count.

## 🧪 Manual Testing

1. **Variant listed (happy path):**
   - Set `ISSUE_SUBCATEGORY_NEVER_PAID_EXTRA_SLUGS` with a variant's slug. Assign the seller one open issue of each
     subcategory.
   - Open the seller console and then its never paid issues page.
   - **Verify:** the count is 2, both issues are listed and the Subcategory column tells them apart.

2. **Without the setting:**
   - Unset it.
   - **Verify:** only the `ISSUE_SUBCATEGORY_NEVER_PAID` issue is listed, with no Subcategory column.

## 📝 Deployment Notes

- No database migrations required.
- Set `ISSUE_SUBCATEGORY_NEVER_PAID_EXTRA_SLUGS` in `local_settings.py` where wanted.
- A package that imports `get_never_paid_subcategory_slugs` needs this change deployed first.

---

- **Date:** 2026-10-26
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl60-consola-vendedor-no-consolidados
- **Type:** Enhancement
- **Modules affected:** Support
