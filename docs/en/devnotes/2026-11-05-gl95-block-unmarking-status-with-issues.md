# A terminal status with issues cannot be unmarked

- **Date:** 2026-11-05
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#95
- **Type:** Enhancement
- **Component:** Support (issue statuses)
- **Impact:** Data Integrity

## 🎯 Summary

Unmarking "Terminal" on a status reopened all its issues and removed their closing dates, and marking it again gave them all that day's date, so the real dates could only be recovered by hand from the history. A confirmation was not enough protection for something that can touch tens of thousands of issues. The admin now rejects unmarking while the status has issues.

## ✨ Changes

### 1. The admin form rejects it

**File:** `support/forms.py`

`IssueStatusAdminForm` adds an error on `is_terminal` when the status has issues. To unmark it, the issues have to be moved to another status first. A status without issues can still be unmarked.

### 2. The code that reopened issues goes away

**Files:** `support/models.py`, `support/admin.py`

Nothing can reach it anymore, so `IssueStatus.sync_issues_with_terminal()` becomes `close_issues()`, and `issues_to_sync_with_terminal()` becomes `issues_to_close()`: they only handle marking. Marking works as before: it closes today the issues without a closing date, and asks for confirmation if there are any.

## 📁 Files Modified

- **`support/forms.py`** — The check, and the confirmation only for marking
- **`support/models.py`** — `close_issues()` and `issues_to_close()`
- **`support/admin.py`** — Only closes after marking
- **`locale/es/LC_MESSAGES/django.po`** — Removes the reopening messages and adds the new one
- **`tests/test_issue_status_terminal.py`** — Unmarking with and without issues

## 🧪 Manual Testing

1. **Happy path:**
   - In the admin, unmark "Terminal" on a status that has issues.
   - **Verify:** An error says to move them first, and nothing changes.

2. **Edge case, no issues:**
   - Unmark "Terminal" on a status without issues.
   - **Verify:** It is saved.

## 📝 Deployment Notes

No migrations required.

---

- **Date:** 2026-11-05
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl95-bloquear-desmarcar-estado
- **Type:** Enhancement
- **Modules affected:** support
