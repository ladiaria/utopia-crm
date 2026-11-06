# One way to read the CSV files people upload

- **Date:** 2026-11-06
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#107
- **Type:** Bug Fix
- **Component:** Core, Support, Logistics
- **Impact:** Data Integrity, User Experience

## 🎯 Summary

Each screen that receives a CSV decoded it in its own way. What Excel saves depends on the option and on the locale: a BOM with "CSV UTF-8", cp1252 with plain "CSV", and semicolons with a Spanish locale. Depending on the screen, that ended in a 500 or, worse, in wrong data without any error. All the screens of this repository now read through the same functions in `core/utils.py`.

## ✨ Changes

### 1. The reading functions

**File:** `core/utils.py`

- **`uploaded_csv_content`** decodes UTF-8 with or without a BOM, then cp1252, with latin-1 as the last resort, and detects the delimiter.
- **`read_uploaded_csv`** reads by column name, as it did. A short row gets empty strings, what a long row has left over goes to `extra_columns`, and spaces around column names are removed.
- **`read_uploaded_csv_rows`** is new, for files read by position.

cp1252 replaces latin-1 as the first fallback: in latin-1, Excel's `’`, `–` and `€` become control characters.

### 2. What each screen did wrong

**Files:** `support/views/all_views.py`, `support/views/campaign_management.py`, `support/views/contacts.py`, `logistics/views.py`

| Screen | With an Excel file, before |
| --- | --- |
| Do not call list | Stored `﻿099123456` or `099123456;Ana`, which match nobody |
| Tag contacts | Skipped the first row with a BOM, added nothing with semicolons, and a row without a tag answered a 500 |
| Bulk delete campaign status | 500 with plain "CSV", and "column not found" with a BOM |
| Import contacts | Imported nothing with semicolons or with plain "CSV" |
| Labels from CSV | 500 with plain "CSV", and "wrong column count" with semicolons |
| Print labels for day | 500 with any file: it passed whole rows as ids |
| Print labels | 500 with a header or a BOM |

### 3. Import contacts: a long row no longer shifts the data

**File:** `support/views/contacts.py`

With a row longer than the header, pandas took the first column as an index: the name went to the last name, without any error. `index_col=False` prevents it.

## 📁 Files Modified

- **`core/utils.py`** — The reading functions
- **`support/views/all_views.py`** — Do not call list and tag contacts
- **`support/views/campaign_management.py`** — Bulk delete
- **`support/views/contacts.py`** — Import contacts
- **`logistics/views.py`** — The three label screens
- **`locale/es/LC_MESSAGES/django.po`** — The message for rows without a tag
- **`CHANGELOG.md`** — Entry for this change

## 📁 Files Created

- **`tests/test_read_uploaded_csv.py`** — Encodings, delimiters, and short, long and empty files
- **`tests/test_csv_uploads.py`** — Each screen with what Excel saves

## 🧪 Manual Testing

1. **Happy path:**
   - In a spreadsheet with a Spanish locale, save a list of contact ids and tags as "CSV", with an accent in a tag, and upload it to Tag Contacts.
   - **Verify:** Every row is tagged, including the first one, and the accent reads right.

2. **Edge case, row without a tag:**
   - Upload the same file with a row that only has the id.
   - **Verify:** The rest is tagged, and a message says how many rows were skipped.

3. **Edge case, the do not call list:**
   - Upload a list saved as "CSV UTF-8", with `0` header rows.
   - **Verify:** In the admin, the first number has no strange characters.

## 📝 Deployment Notes

No migrations. Files that worked keep working the same way. This goes before the `utopia-crm-ladiaria` change, which uses `read_uploaded_csv_rows`.

## 📚 Technical Details

In a local copy of the do not call list, the 522,809 numbers are all clean: the problem hadn't happened with the files uploaded so far.

The delimiter detection is tested with the cases most likely to fool it: commas inside the values of a semicolon file, quoted commas, a quoted semicolon in a comma file, one column, and an empty file.

## 🎓 Design Decisions

- **Files with a fixed format stay out:** those from banks and card processors have an encoding and delimiter defined by whoever generates them.
- **The print labels tests mock `Canvas`:** with nothing to draw, the PDF itself fails in `flush`, and that is unrelated to reading the file.

---

- **Date:** 2026-11-06
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl107-lectura-csv
- **Type:** Bug Fix
- **Modules affected:** core, support, logistics, locale, tests
