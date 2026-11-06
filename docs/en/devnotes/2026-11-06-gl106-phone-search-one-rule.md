# One rule for every phone search box

- **Date:** 2026-11-06
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#106
- **Type:** Bug Fix
- **Component:** Core, Support, Invoicing
- **Impact:** User Experience

## 🎯 Summary

Numbers are stored with their country code, and the search boxes look for what was typed inside the stored number. So `099123456` is not part of `+59899123456`, and the most natural way to write a number in Uruguay found nobody. Written with spaces it didn't work either. "Check for existing contacts" already handled the leading 0, with its own code. Now one rule in `core/utils.py` serves every box that a person types into.

## ✨ Changes

### 1. The rule

**File:** `core/utils.py`

`phone_search_forms` takes what was typed and returns the forms to look for:

| Typed | Forms |
| --- | --- |
| `099123456` | `099123456`, `99123456` |
| `+59899123456` | `59899123456` |
| `099 123 456` | `099123456`, `99123456`, `099 123 456` |
| `0123` | `0123` |
| `+`, `N/A` | none: finds nothing |

- **Without the zeros only with 7 digits or more** (`MIN_PHONE_SEARCH_DIGITS`, the minimum "Check for existing contacts" already had). Otherwise `0123` would look for `123` in every number.
- **As typed, if it has symbols:** some old numbers are stored with spaces, such as `062 2 0308`.
- **Without digits, nothing:** an empty form would match every contact.

### 2. Two ways of using it

**File:** `core/utils.py`

- **`phone_search_q`**, for boxes that only search phones.
- **`phone_or_text_search_q`**, for boxes that also search names, emails or documents. If the text doesn't look like a number it stays literal, as before: taking the digits out of `Ana2` would look for `2` in every number.

### 3. The boxes that use it

**Files:** `core/filters.py`, `support/filters.py`, `invoicing/filters.py`, `support/views/contacts.py`

- **Contacts list and contact search (`apply_main_filter`):** only the phone fields change. A number written with spaces no longer goes through the name branch, and `id_document` and `id` still get the text exactly as typed, so `0123` keeps finding documents.
- **Scheduled tasks (`by_contact_data`) and invoices (`filter_by_contact_phone`):** the same rule, on the fields each one already searched.
- **`CheckForExistingContactsView`:** drops its own copy and uses the shared rule and minimum.

## 📁 Files Modified

- **`core/utils.py`** — The rule, its minimum and the two filters
- **`core/filters.py`** — Contacts box
- **`support/filters.py`** — Scheduled tasks box
- **`invoicing/filters.py`** — Invoices box
- **`support/views/contacts.py`** — Check for existing contacts uses the rule
- **`CHANGELOG.md`** — Entry for this change

## 📁 Files Created

- **`tests/test_phone_search.py`** — The rule and the three boxes of this repository

## 🧪 Manual Testing

1. **Happy path:**
   - In the contacts list, search for an existing number written as `099…`, then as `099 123 456`.
   - **Verify:** The contact appears both times.

2. **Edge case, part of a document:**
   - Search for `0123`.
   - **Verify:** It finds documents and numbers containing `0123`, but not every number containing `123`.

3. **Edge case, no digits:**
   - In the invoice filter, search the phone box for `+` or `N/A`.
   - **Verify:** No results, instead of everyone with a phone.

## 📝 Deployment Notes

No migrations. Boxes may find more than before, which is the goal. In la diaria's deployment this goes before the `utopia-crm-ladiaria` change, which imports `phone_search_q`.

## 📚 Technical Details

Measured on a local copy with 640,959 contacts, median of 8 real numbers written with the 0:

| Box | Before | After |
| --- | --- | --- |
| Contacts | 183 ms | 198 ms |
| Invoices | 90 ms | 48 ms |
| Scheduled tasks | 206 ms | 193 ms |
| Phones only, three fields | 38 ms | 56 ms |

`contains` replaces `icontains`, which applied `UPPER` to digits for no reason. That is why invoices got faster even though they search two forms.

The contacts test creates the `unaccent` extension: the box needs it, but no migration creates it (`INSTALL.md` says to do so by hand), so this box had no tests.

## 🎓 Design Decisions

- **Not including internal searches:** `identify_phone` and similar ones use `Contact.objects.get`, which fails with more than one match. Finding more could break them.
- **The same fields each box had:** invoices and scheduled tasks don't search `work_phone`, and this doesn't add it.
- **Not normalizing stored numbers in the query:** cleaning each number in the database would find `06220308` in `062 2 0308`, but at the cost of the whole table on every search.

---

- **Date:** 2026-11-06
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl106-buscar-telefono
- **Type:** Bug Fix
- **Modules affected:** core, support, invoicing, tests
