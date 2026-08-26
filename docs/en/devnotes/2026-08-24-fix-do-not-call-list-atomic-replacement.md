# Bug Fix: Atomic Replacement of the Do Not Call List

- **Date:** 2026-08-24
- **Author:** Tanya Tree + Claude Opus 5
- **Ticket:** fix/upload_do_not_call_numbers (no ticket)
- **Type:** Bug Fix (+ Performance, Security)
- **Component:** Support — Campaign Management, Core Models (DoNotCallNumber)
- **Impact:** Data Integrity, Performance, Access Control, User Experience

## 🎯 Summary

Uploading the do not call list (`/support/upload_do_not_call_numbers/`) started failing with
`IntegrityError: duplicate key value violates unique constraint "core_donotcallnumber_pkey"` on the
**first** number of the file. The uploaded CSV turned out to be clean (512,734 rows, all 8 digits,
zero duplicates, zero blanks), and the delete step worked correctly when replayed in a shell. The
cause was structural: `delete_all_numbers()` and `upload_new_numbers()` ran in **two separate
transactions**, so the several seconds between them were a window in which a second upload (a double
click on the button, a browser resubmit) could delete nothing — the first request had already
committed its delete — and then insert the same numbers the first request was still inserting.
Whichever committed second hit the duplicate key.

The same gap hid a worse failure mode: because the delete committed on its own, **any** failure
during the insert left the table empty, silently making every contact callable again.

The fix makes the replacement a single atomic operation, hardens the parsing so a malformed row
cannot abort the whole load, restricts the tool to admins (it destroys the entire list), and rewrites
a template that still carried copy-pasted text from the address complementary information screen.

## ✨ Changes

### 1. Delete and insert in one transaction

**File:** `core/models.py`

A new `DoNotCallNumber.replace_all_numbers()` wraps both steps in a single `transaction.atomic()`
block. Either the new list is completely in place, or the previous one survives untouched:

```python
numbers, discarded = DoNotCallNumber.clean_numbers(numbers_list)
if not numbers:
    return 0, discarded
with transaction.atomic():
    DoNotCallNumber.delete_all_numbers()
    DoNotCallNumber._bulk_create_numbers(numbers, batch_size=batch_size)
return len(numbers), discarded
```

The early return matters as much as the transaction: a file that yields no valid number is treated as
a broken file and nothing is touched. Replacing the list with nothing is never the intended outcome.

`delete_all_numbers()` and `upload_new_numbers()` keep their original meaning (delete only / insert
only) so any external caller of the base app keeps working.

### 2. TRUNCATE instead of DELETE, which also serializes concurrent uploads

**File:** `core/models.py`

The list holds hundreds of thousands of rows. On PostgreSQL the table is now emptied with `TRUNCATE`,
which is much faster than a `DELETE` and — the part that matters here — takes an `ACCESS EXCLUSIVE`
lock held until commit. Two simultaneous uploads now queue behind each other instead of interleaving,
which is exactly the race that produced the duplicate key error:

```python
if connection.vendor == "postgresql":
    with connection.cursor() as cursor:
        cursor.execute('TRUNCATE TABLE "{}"'.format(DoNotCallNumber._meta.db_table))
else:
    DoNotCallNumber.objects.all().delete()
```

The table name comes from the model's `_meta`, never from user input. The non-PostgreSQL branch keeps
the base app working on other backends.

### 3. Rows that used to abort the whole insert are now discarded

**File:** `core/models.py`

`clean_numbers()` normalises the rows before anything is inserted. Empty rows, blank values, repeated
values and values longer than the column are dropped and counted, since a single one of them aborted
the entire `bulk_create`:

```python
max_length = DoNotCallNumber._meta.get_field("number").max_length
numbers, discarded = {}, 0
for row in rows:
    value = row[0].strip() if row else ""
    if not value or len(value) > max_length:
        discarded += 1
        continue
    # A dict keeps insertion order and removes duplicates in a single pass.
    numbers[value] = None
return list(numbers), discarded
```

The old code did `DoNotCallNumber(number=number[0])` with no guard at all, so an empty row raised
`IndexError` and a repeated number raised `IntegrityError`.

### 4. Insert in batches, parse without materialising the file

**File:** `core/models.py`, `support/views/all_views.py`

`bulk_create` now runs with `batch_size=5000` instead of building one INSERT of half a million rows,
and the view parses with `io.StringIO` + `itertools.islice` instead of `splitlines()`, which used to
build a 512k-element list of strings before the CSV reader even started. Measured against the real
file: **7.0 s → 4.7 s**, with substantially lower memory use.

`islice` also replaces the two bare `next(numbers)` calls, which raised `StopIteration` (a 500) on a
file with fewer than two rows.

### 5. Restricted to admins

**File:** `support/views/all_views.py`, `support/templates/campaign_management_menu.html`, `templates/components/sidebar_items/_campaign_management.html`

The view destroys the entire list, so `@staff_member_required` is no longer enough. It now uses
`@user_passes_test(user_is_admin)`, matching the pattern already used by `BulkReassignIssueStatusView`
and `BulkDeleteCampaignStatusView`:

```python
def user_is_admin(user):
    return user.is_superuser or user.groups.filter(name="Admins").exists()
```

The Campaign Management menu card and the sidebar entry are wrapped in
`{% if request.user|in_group_exclusive:"Admins" %}` so users who cannot run it do not see the link.

### 6. Template rewritten, operator feedback added

**File:** `support/templates/upload_do_not_call_numbers.html`

The template's card title read *"Upload address complementary information"* and its wrapper `div` was
still `id="address_complementary_information"` — leftovers from a copy-paste. Nothing on the page
said the upload **replaces the whole list**. It now shows a warning callout stating exactly that, the
number of entries currently stored, a `header_rows` input (default 2, since the file published by the
regulator carries two header rows), and a Cancel button back to Campaign Management.

The view reports the outcome through `messages` — how many numbers were loaded, how many rows were
ignored, or the error with the previous list kept — instead of always redirecting to `/` with a
generic success message. The file is decoded as UTF-8 with a latin-1 fallback, the same pattern
`tag_contacts` already uses.

## 📁 Files Modified

- **`core/models.py`** — `DoNotCallNumber`: `replace_all_numbers()`, `clean_numbers()`, `_bulk_create_numbers()`, TRUNCATE-based `delete_all_numbers()`, batched `upload_new_numbers()`
- **`support/views/all_views.py`** — `upload_do_not_call_numbers` rewritten; `user_is_admin` helper added
- **`support/templates/upload_do_not_call_numbers.html`** — full rewrite (wrong copy-pasted texts, no explanation of the destructive behaviour)
- **`support/templates/campaign_management_menu.html`** — card hidden from non-admins, description updated
- **`templates/components/sidebar_items/_campaign_management.html`** — sidebar entry hidden from non-admins

## 📁 Files Created

- **`tests/test_upload_do_not_call_numbers.py`** — 10 tests covering permissions, replacement, repeated numbers, numbers already stored, blank/oversized rows, empty files, latin-1 encoding and the header row setting

## 📚 Technical Details

**Why the error pointed at the first row.** Postgres reports the first conflicting key it hits. With
the delete already committed by request A, request B deleted nothing and started inserting from the
top of the same file, so the collision surfaced on row 1. That is why the error looked like "the
delete is not working" while the delete was in fact working perfectly.

**Why `TRUNCATE` is safe inside a transaction.** Unlike MySQL, PostgreSQL's `TRUNCATE` is fully
transactional and rolls back with the enclosing block. The test suite relies on this: every test runs
inside `TestCase`'s transaction and the data is restored afterwards.

**Backward compatibility.** `delete_all_numbers()` and `upload_new_numbers()` keep their names and
their original semantics. `upload_new_numbers()` gained an optional `batch_size` argument and now
returns a `(loaded, discarded)` tuple where it previously returned `None`; it is called only from
this view inside the suite.

## 🧪 Manual Testing

1. **Happy path — replace the list:**
   - Log in as a superuser or a member of the `Admins` group
   - Go to Campaign Management → Upload do not call list
   - Confirm the page shows how many numbers are currently stored
   - Upload the regulator's CSV leaving "Header rows to skip" at 2
   - **Verify:** you are redirected to Campaign Management with a message stating how many numbers were loaded, and reopening the upload page shows that same count as stored

2. **Edge case — a file that yields no valid numbers:**
   - Upload a file containing only its two header rows
   - **Verify:** an error message says no valid numbers were found and the previous list was kept; the stored count on the page is unchanged

3. **Edge case — repeated numbers:**
   - Upload a file where a number appears twice
   - **Verify:** the upload succeeds, the number is stored once, and a warning reports the ignored rows

4. **Access control:**
   - Log in as a staff user who is **not** in `Admins`
   - **Verify:** the "Upload do not call list" card and sidebar entry are not visible, and navigating directly to `/support/upload_do_not_call_numbers/` redirects to the login page

5. **Regression — do not call flags still resolve:**
   - After a successful upload, open a contact whose phone is on the list
   - **Verify:** the contact detail and the seller console still mark the phone as "No llamar"

## 📝 Deployment Notes

- No database migrations required
- No configuration changes required
- No post-deployment commands required
- Users who need this tool must belong to the `Admins` group (or be superusers). Staff membership
  alone no longer grants access — worth confirming with whoever runs the upload before deploying
- The upload is a long request (roughly 5 s of database work plus the file transfer for a 5 MB file).
  It is well inside the usual proxy limits, but it is worth keeping in mind if the file grows

## 🚀 Future Improvements

- Use PostgreSQL `COPY` instead of `bulk_create` if the list grows to the point where 5 s is a problem
- Record who replaced the list and when (a `LogEntry`, as the bulk reassign view already does)
- Move the upload to a management command / background job if the file ever gets large enough to risk
  a request timeout

---

- **Date:** 2026-08-24
- **Author:** Tanya Tree + Claude Opus 5
- **Branch:** fix/upload_do_not_call_numbers
- **Type:** Bug Fix (+ Performance, Security)
- **Modules affected:** Core, Support
