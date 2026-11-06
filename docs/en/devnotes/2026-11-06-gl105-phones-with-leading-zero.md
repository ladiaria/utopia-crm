# Check for existing contacts finds phones written with the leading 0

- **Date:** 2026-11-06
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#105
- **Type:** Bug Fix
- **Component:** Support
- **Impact:** Campaign management

## 🎯 Summary

The phone check looks for the CSV digits inside the stored number. Numbers are stored with their country code, so `099123456` is not part of `+59899123456`: the contact was listed under "No Matches" and looked new. The search now tries the number with and without its leading zeros.

## ✨ Changes

### 1. The search tries both forms

**File:** `support/views/contacts.py`

```python
without_leading_zeros = phone_without_plus.lstrip('0')
if without_leading_zeros != phone_without_plus:
    phone_query |= Q(phone__icontains=without_leading_zeros)
    mobile_query |= Q(mobile__icontains=without_leading_zeros)
```

It keeps the form with the 0 because about 2,000 old numbers are stored that way. The "Phone" and "Mobile" badges use the same conditions. An international prefix also works: `00598 99 123 456` finds the number.

### 2. Leading zeros do not count for the minimum

**File:** `support/views/contacts.py`

```python
if len(re.sub(r'\D', '', value).lstrip('0')) < self.min_phone_digits:
```

Without this, `0000000` has 7 digits but becomes an empty search that matches every contact. `0123456` is not searched either, because it would search for `123456`.

### 3. The instructions

**Files:** `support/templates/check_for_existing_contacts.html`, `locale/es/LC_MESSAGES/django.po`

They no longer ask people to remove the 0. The minimum now says that leading zeros do not count, and the warning about how phones are written leaves "No Matches".

## 📁 Files Modified

- **`support/views/contacts.py`** — The search and the minimum
- **`support/templates/check_for_existing_contacts.html`** — The instructions
- **`locale/es/LC_MESSAGES/django.po`** — Translations
- **`tests/test_check_existing_contacts.py`** — The leading 0 in `phone` and `mobile`, the numbers stored with the 0, the international prefix and the minimum

## 🧪 Manual Testing

1. **Happy path:**
   - Upload a CSV with a `phone` column and a number that exists, written as `099…`.
   - **Verify:** The contact is in the results, with the right badge.

2. **Edge case, only zeros:**
   - Upload a CSV with `0000000` and `0123456`.
   - **Verify:** The response is immediate and both are in "Phone Numbers Not Searched".

## 📝 Deployment Notes

No migrations. More matches can appear than before, which is the point of the change. Merging restarts the application.

## 📚 Technical Details

Measured on a local copy with 640,959 contacts and 80 real mobile numbers: all of them were found written with the 0, with a median of 1 match per row and a maximum of 3. A row with the 0 takes about 170 ms, and one without it about 105 ms, because it searches twice. Rows that do not start with 0 do not change. Grouping the searches is still pending in it/utopia-crm-ladiaria#105.

---

- **Date:** 2026-11-06
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl105-telefono-cero-inicial
- **Type:** Bug Fix
- **Modules affected:** support, locale, tests
