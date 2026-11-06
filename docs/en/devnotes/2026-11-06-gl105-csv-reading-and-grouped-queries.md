# Check for existing contacts: any CSV from a spreadsheet, and emails in one query

- **Date:** 2026-11-06
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#105
- **Type:** Bug Fix, Performance
- **Component:** Core, Support
- **Impact:** Campaign management

## 🎯 Summary

The screen answered a 500 for a CSV that wasn't UTF-8 and for a row with fewer columns than the header, and it made 3 queries per row. A file of 2,000 emails took almost 3 minutes while the person waited. Now it reads those files, looks for all the emails in one query, and each phone row makes one query instead of three.

## ✨ Changes

### 1. A function to read the CSV files people upload

**File:** `core/utils.py`

`read_uploaded_csv` decodes as UTF-8 with or without a BOM and falls back to latin-1, which is how Excel saves a plain "CSV". It detects the delimiter, and a row with fewer columns gets empty strings instead of `None`. It returns the `DictReader` and the delimiter. For now only this screen uses it.

### 2. Emails in one query

**File:** `support/views/contacts.py`

`find_matching_contacts_by_emails` looks for all of them with `Lower` and `IN`, and returns a dict by lowercase email. It still ignores case, and results keep the order of the rows.

### 3. What the table shows comes in the same query

**File:** `support/views/contacts.py`

`with_results_data` annotates `has_active_subscription` and `is_in_active_campaign` with `Exists`. That replaces the prefetch of subscriptions, the `Count` and the prefetch of `contactcampaignstatus_set`, which nothing used. The `count` and `email_matches` keys, which the template didn't use, are gone too, along with the progress `print`.

## 📁 Files Modified

- **`core/utils.py`** — `read_uploaded_csv`
- **`support/views/contacts.py`** — The grouped search and the annotations
- **`tests/test_check_existing_contacts.py`** — Latin-1, short rows, row order, the table data and the number of queries
- **`CHANGELOG.md`** — Entry for this change

## 🧪 Manual Testing

1. **Happy path:**
   - Upload a CSV of 2,000 emails.
   - **Verify:** It answers in about a second, with the same results.

2. **Edge case, latin-1:**
   - Save a file with an accent in Excel as plain "CSV" and upload it.
   - **Verify:** It answers normally instead of a 500.

3. **Edge case, short row:**
   - Upload a file with a row that has fewer columns than the header.
   - **Verify:** The row appears without a match, or under "Phones not searched", instead of a 500.

## 📝 Deployment Notes

No migrations. It doesn't change what the screen finds. It goes after the phone search PR (it/utopia-crm-ladiaria#106), on top of which it is built.

## 📚 Technical Details

Measured through the screen on a local copy with 640,959 contacts:

| File | Before | After | Queries before | Queries after |
| --- | --- | --- | --- | --- |
| 300 emails | 26.3 s | 0.75 s | 907 | 8 |
| 2,000 emails | 166.7 s | 0.55 s | 6,007 | 8 |
| 300 phones | 17.4 s | 16.2 s | 907 | 307 |

Phones barely change, because almost all the time is in looking for the digits inside each number across the whole table.

## 🚀 Future Improvements

- **Phones:** a `pg_trgm` index on `phone` and `mobile` took 300 phones from 16.2 s to 3.2 s in a test that was rolled back, and it took about 22 MB with `work_phone` included. A single query with a regular expression doesn't help: it costs about the same per number, with or without the index. It needs a migration and a decision, so it is not included here.
- **The other CSV uploads:** they could use `read_uploaded_csv`. File formats fixed by banks and card processors should stay as they are.

---

- **Date:** 2026-11-06
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl105-csv-consultas-agrupadas
- **Type:** Bug Fix, Performance
- **Modules affected:** core, support, tests
