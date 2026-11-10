# Check for existing contacts: a minimum of 7 digits to search a phone, and instructions that match the screen

- **Date:** 2026-11-06
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#105
- **Type:** Bug Fix
- **Component:** Support
- **Impact:** Campaign management

## 🎯 Summary

The phone check strips everything but digits and searches with `icontains`. A value without digits (`N/A`, `-`) became an empty search that matched every contact and loaded them all in memory, with their subscriptions. Measured on a local copy with 640,959 contacts: `N/A` matched all of them, and `099` matched 3,985.

A phone with fewer than 7 digits is no longer searched. It goes to its own table, because the instructions present "No Matches" as candidates for import. The instructions also said things the screen does not do, so they are corrected.

## ✨ Changes

### 1. Minimum digits to search a phone

**File:** `support/views/contacts.py`

```python
if len(re.sub(r'\D', '', value)) < self.min_phone_digits:
    not_searched_phones.append({'value': value, 'row_number': row_number + 1})
    continue
```

`min_phone_digits` is a class attribute with the value 7. Symbols do not count, so `+99-12-34` is not searched. An empty phone cell goes to the same list instead of showing as `N/A` under "No Matches". The email check does not change.

### 2. A table for what was not searched

**File:** `support/templates/check_for_existing_contacts.html`

"Phone Numbers Not Searched" shows above the results, with the CSV row, the value and its own export.

### 3. Excel's "CSV UTF-8"

**File:** `support/views/contacts.py`

Excel starts these files with a BOM, which became part of the first column name: `email` was not found and every row was listed as `N/A`. The file is now decoded with `utf-8-sig`. The instructions recommend this format, so without this change they would have sent people to the failure.

### 4. The instructions

**Files:** `support/templates/check_for_existing_contacts.html`, `locale/es/LC_MESSAGES/django.po`

| Topic | Before | Now |
| --- | --- | --- |
| Phone format | Nothing | Country code or no leading 0: `099123456` is usually not found, because 97.5% of the phones are stored as `+598…` |
| Partial numbers | Nothing | The CSV number can be part of the stored one, so a row can find several contacts |
| Minimum | Nothing | Fewer than 7 digits is not searched |
| "No Matches" | "Don't exist in the database" | "Were not found", and check how phones are written |
| Pro Tip | Upload the "No Matches" export to the import | It cannot be uploaded as is: the import has its own template, with other columns |
| Column name | "Must contain an 'email' column" | Exactly `email`, in lowercase: `Email` is not recognized |
| Encoding | Nothing | Save as UTF-8 |

The two headings of the "What to Expect" panel lose their color, because the green one was almost unreadable on blue. In Spanish, typos are fixed ("bse", "enconttradas", "entcontradas"), and the texts that are changed use voseo.

## 📁 Files Created

- **`tests/test_check_existing_contacts.py`** — The minimum, the lists, the leading 0 and the BOM

## 📁 Files Modified

- **`support/views/contacts.py`** — The minimum, the list and the decoding
- **`support/templates/check_for_existing_contacts.html`** — The table and the instructions
- **`locale/es/LC_MESSAGES/django.po`** — Translations

## 🧪 Manual Testing

1. **Happy path:**
   - Upload a CSV with a `phone` column and a number that exists, written as `+598…`.
   - **Verify:** The contact is in the results, and there is no "Phone Numbers Not Searched" table.

2. **Edge case, values that cannot be searched:**
   - Upload a CSV with `N/A`, `-` and `099`.
   - **Verify:** The response is immediate, the three are in "Phone Numbers Not Searched" and none is in "No Matches".

3. **Edge case, Excel:**
   - Save a CSV with an `email` column from Excel as "CSV UTF-8" and upload it.
   - **Verify:** The emails are searched, and the rows are not listed as `N/A`.

## 📝 Deployment Notes

No migrations. Merging restarts the application, and whoever is waiting for a result on that screen loses it. `django.po` changes, so the server compiles the translations.

## 🚀 Future Improvements

The rest is in it/utopia-crm-ladiaria#105: grouping the searches to avoid the queries per row, and deciding what to do with partial matches.

## 🎓 Design Decisions

- **A separate table, not "No Matches":** that list is what people take to the import, and a value that was not searched says nothing about whether the contact exists.
- **The leading 0 is documented, not changed:** finding those numbers changes what the search returns. That is a decision of its own.

---

- **Date:** 2026-11-06
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl105-telefonos-minimo-digitos
- **Type:** Bug Fix
- **Modules affected:** support, locale, tests
