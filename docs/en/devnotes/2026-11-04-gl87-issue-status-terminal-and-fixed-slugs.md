# Terminal issue statuses are managed from the admin, and slugs no longer change on rename

- **Date:** 2026-11-04
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** gl87-estados-terminales (it/utopia-crm-ladiaria#87, #81)
- **Type:** Enhancement
- **Component:** Support (issues), Core Models, Logistics
- **Impact:** Operations, Data Integrity

## 🎯 Summary

Whether an issue status is terminal (a closing one) was a list of slugs in `local_settings.py`,
`ISSUE_STATUS_FINISHED_LIST`, different on each server. Making a status terminal meant editing the configuration of
every server and filling in, by hand, the closing date of the issues already in that status. It is now a boolean on the
status, `IssueStatus.is_terminal`, managed from the admin by whoever has its own permission. This goes together with a
second fix, because managing statuses from the admin makes renaming them more likely: renaming a status or a subcategory
rebuilt its slug, which silently broke everything that looks it up by slug. Slugs are now set only on creation.

## ✨ Changes

### 1. `IssueStatus.is_terminal` replaces the list

**Files:** `support/models.py`, `core/models.py`, `support/filters.py`, `support/forms.py`, `logistics/views.py`,
`support/views/all_views.py`, `support/views/seller_console.py`, `support/management/commands/close_invoicing_issues.py`

Every read of the list now reads the boolean:

```python
# Before
Issue.objects.exclude(status__slug__in=settings.ISSUE_STATUS_FINISHED_LIST)
# After
Issue.objects.exclude(status__is_terminal=True)
```

`Issue.has_terminal_status()` and `Issue.apply_status_change()` use it too. The guards in `seller_console.py` for
deployments without the list are gone: with the boolean there is no "not configured" case.

### 2. Own permission to change it

**File:** `support/admin.py`

`support.change_issuestatus_terminal` is separate from the permission to edit a status. Without it, `is_terminal` is read
only, also when creating a status, so a new status is not terminal. `is_terminal` is shown and filterable in the
changelist, but it is not `list_editable`: editing it there would skip the checks below.

### 3. Statuses that settings rely on cannot change sides

**File:** `support/forms.py` (`IssueStatusAdminForm`)

Checked only when `is_terminal` changes, so these statuses can still be renamed:

- `ISSUE_STATUS_SOLVED` and `ISSUE_STATUS_AUTO_CLOSE_UNCOLLECTIBLE` cannot be unmarked: the automatic closings move issues
  to them to close them.
- `ISSUE_STATUS_NEW`, `ISSUE_STATUS_ASSIGNED`, `ISSUE_STATUS_UNASSIGNED` and `ISSUE_STATUS_PENDING` cannot be marked: the
  CRM gives them to issues that are still open.

### 4. Changing the boolean brings the status' issues along

**Files:** `support/models.py` (`IssueStatus.sync_issues_with_terminal`), `support/forms.py`, `support/admin.py`

`apply_status_change` acts when an issue changes status, not when the status itself changes. So, if the status has issues,
the form asks to confirm with their number, and saving applies the same rules to them:

- **To terminal:** the ones without a closing date get today's.
- **To not terminal:** all of them lose their closing date, and get tomorrow as the next action date if it is missing or
  past.

It uses `bulk_update_with_history`, so each issue's history says who closed or reopened it and why, without a `save()` per
row. The admin's `LogEntry` of the status records how many issues it touched.

### 5. Slugs fixed on creation, and names unique in the admin

**Files:** `support/models.py`, `support/forms.py` (`UniqueNameAdminFormMixin`, `IssueSubcategoryAdminForm`), `support/admin.py`

`IssueStatus.slug` and `IssueSubcategory.slug` now use `always_update=False`. `AutoSlugField` does not make them unique,
and a second "Resuelto" would break every `IssueStatus.objects.get(slug=...)`. So both admins reject a new or changed name
that is already in use, or that only differs from one in case, accents or punctuation (that is, the same slug). Saving
without changing the name is not checked.

### 6. The migration seeds the boolean from each deployment's list

**Files:** `support/migrations/0044_issuestatus_is_terminal.py`, `settings.py`

It adds the field and the permission, alters both slugs (state only: no column or data is touched) and marks as terminal
the statuses in `ISSUE_STATUS_FINISHED_LIST`, with the settings of the server it runs on. The list is marked as deprecated
in `settings.py`: only this migration reads it.

## 📁 Files Modified

- **`support/models.py`** — `is_terminal`, the permission, fixed slugs, `issues_to_sync_with_terminal()` and
  `sync_issues_with_terminal()`.
- **`support/forms.py`** — `IssueStatusAdminForm`, `IssueSubcategoryAdminForm`, `UniqueNameAdminFormMixin`; the "not
  delivered" block reads the boolean.
- **`support/admin.py`** — `IssueStatusAdmin` and `IssueSubcategoryAdmin` with the new forms; read only without the
  permission; log and message with the number of issues.
- **`core/models.py`**, **`logistics/views.py`**, **`support/filters.py`**, **`support/views/all_views.py`**,
  **`support/views/seller_console.py`**, **`support/management/commands/close_invoicing_issues.py`** — Read the boolean.
- **`settings.py`** — `ISSUE_STATUS_FINISHED_LIST` marked as deprecated.
- **`locale/es/LC_MESSAGES/django.po`** — Spanish translations.
- **`tests/test_bulk_reassign_issue_status.py`**, **`tests/test_close_invoicing_issues.py`**,
  **`tests/test_issue_resolution_auto_solved.py`**, **`tests/test_issue_terminal_status_badge.py`**,
  **`tests/test_new_issue_not_delivered_block.py`**, **`tests/test_seller_console_never_paid.py`** — Create the terminal
  statuses with `is_terminal=True`.
- **`CHANGELOG.md`** — Entry.

## 📁 Files Created

- **`support/migrations/0044_issuestatus_is_terminal.py`** — Field, permission, slugs and seed.
- **`tests/test_issue_status_terminal.py`** — 19 tests: the seed, renaming keeps the slug, the permission, the checks on
  settings statuses, confirmation, closing and reopening, unique names, and issues without a status counting as open.

## 📚 Technical Details

- **Issues without a status still count as open:** `exclude(status__is_terminal=True)` keeps them, like the old
  `exclude(status__slug__in=...)`. There is a test for it.
- **Measured on a copy of production data:** reopening a status with 39,644 issues takes 13.5 seconds, inside the admin's
  transaction. If it fails, nothing is left half done.
- **Reverting the migration** drops the column and does not touch the list, so the old code keeps working with it if the
  list is still in the settings.
- **Automated tests:** the whole suite without `test_cmssync` (418 tests) passes.

## 🧪 Manual Testing

1. **Mark a status with issues (happy path):**
   - With the permission, in the admin, open a non terminal status that has open issues, check "Terminal" and save.
   - **Verify:** an error asks to confirm, with the number of issues. Check the confirmation box and save again: the issues
     have today's closing date, leave the open lists, and their history shows your user.

2. **Unmark it:**
   - On the same status, uncheck "Terminal", confirm and save.
   - **Verify:** the issues have no closing date, come back to the open lists, and the ones with no next action date, or
     with a past one, have tomorrow's.

3. **Without the permission (edge case):**
   - With a user that can edit statuses but lacks the new permission, open a status.
   - **Verify:** "Terminal" can be seen but not changed, and there is no confirmation box.

4. **Statuses that settings rely on (edge case):**
   - Try to unmark the `ISSUE_STATUS_SOLVED` status and to mark the `ISSUE_STATUS_NEW` one.
   - **Verify:** both are rejected with an error on the field. Renaming them works.

5. **Rename and repeat a name (edge case):**
   - Rename a status, then try to create another one with its name written with different case or accents.
   - **Verify:** the slug of the renamed one did not change, and the new one is rejected.

## 📝 Deployment Notes

- **Migration required:** `support/0044_issuestatus_is_terminal`.
- **`ISSUE_STATUS_FINISHED_LIST` must still be in `local_settings.py` when `migrate` runs**, or no status is marked.
  Afterwards, it can be removed from there.
- **Run `migrate` right after deploying the code:** until then, the screens that filter issues answer 500, because the
  column does not exist yet.
- **A customization package that reads the list** can keep doing it until this is migrated, and must move to the field
  afterwards: the list no longer tells what is terminal. la diaria's does it in it/utopia-crm-ladiaria!211, deployed after
  this one.
- **Give the permission** "Can change whether an issue status is terminal" to whoever should have it. Superusers already
  do.

## 🎓 Design Decisions

- **The list is not a runtime fallback:** an `OR` between the boolean and the list would make unmarking a status in the
  admin have no effect. It stays only as the seed of the migration.
- **Form checks, not a system check:** a check that queries the database runs before `migrate`, and would fail on the
  column that does not exist yet.
- **No `HistoricalRecords` on `IssueStatus`:** the `LogEntry` already records who changed the boolean, when and how many
  issues it touched. It would be another table for the same thing.
- **Unique names in the form, not in the database:** enough for the admin, which is where statuses are created, and it
  needs no check of existing data. A status created from a shell or a fixture could still repeat a slug.

## 🚀 Future Improvements

- Decide whether unmarking a status with issues should be blocked instead of confirmed (it/utopia-crm-ladiaria#95).
- Remove `ISSUE_STATUS_FINISHED_LIST` from `settings.py` once no deployment needs it to migrate.
- `unique=True` on both slugs, to cover what the form does not.
- `get_finished_issues_by_subcategory_count()` and `get_finished_issues_by_category_count()` in `core/models.py` use
  `exclude`, so they return the open ones: this change kept that behaviour.

---

- **Date:** 2026-11-04
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl87-estados-terminales
- **Type:** Enhancement
- **Modules affected:** Support, Core, Logistics
