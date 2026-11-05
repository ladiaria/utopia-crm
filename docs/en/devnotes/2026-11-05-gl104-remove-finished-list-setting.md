# The old list of terminal statuses leaves the settings

- **Date:** 2026-11-05
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#104
- **Type:** Refactor
- **Component:** Settings, Support
- **Impact:** None for deployments that already applied `support/0044`

## 🎯 Summary

Whether a status is terminal is `IssueStatus.is_terminal`, managed from the admin. `ISSUE_STATUS_FINISHED_LIST` was deprecated and only the migration `support/0044` read it. It leaves `settings.py`, and the migration keeps its old default so a deployment that has not migrated yet does not lose its terminal statuses.

## ✨ Changes

### 1. The setting goes away

**File:** `settings.py`

Removes `ISSUE_STATUS_FINISHED_LIST` and its comment.

### 2. The migration keeps the default

**File:** `support/migrations/0044_issuestatus_is_terminal.py`

```python
DEFAULT_FINISHED_LIST = ["solved", "not-solved"]
finished_list = getattr(settings, "ISSUE_STATUS_FINISHED_LIST", DEFAULT_FINISHED_LIST) or []
```

A deployment that defines the list in its `local_settings.py` still uses its own. Editing an applied migration is safe here: it only changes the default of a data step, and a deployment that already applied it does not run it again.

## 📁 Files Modified

- **`settings.py`** — The setting
- **`support/migrations/0044_issuestatus_is_terminal.py`** — The default
- **`tests/test_issue_status_terminal.py`** — The migration without the setting

## 🧪 Manual Testing

1. **Happy path:**
   - Run `python manage.py check` on a deployment that already applied `support/0044`.
   - **Verify:** No issues, and the terminal statuses in the admin do not change.

2. **Edge case, not migrated yet:**
   - On a database before `support/0044`, with `solved` and `not-solved` statuses and no list in `local_settings.py`, run `migrate`.
   - **Verify:** Both statuses end up terminal.

## 📝 Deployment Notes

No new migrations. The list can stay in a `local_settings.py` without any effect, once `support/0044` is applied.

---

- **Date:** 2026-11-05
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl104-sacar-finished-list
- **Type:** Refactor
- **Modules affected:** settings, support
