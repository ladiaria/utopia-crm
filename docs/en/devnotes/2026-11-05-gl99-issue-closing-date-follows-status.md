# The issue closing date always follows the status

- **Date:** 2026-11-05
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#99
- **Type:** Bug Fix
- **Component:** Support (issues)
- **Impact:** Data Integrity, Community console

## 🎯 Summary

Two ideas of "closed" lived together: most of the system looks at whether the status is terminal, while the community console also required an empty closing date. Each path that closed an issue wrote the date on its own, and reopening one left it behind, so an open issue could stay hidden from the console. `Issue.save()` now keeps the rule in one place, and whether an issue is closed is decided only by `IssueStatus.is_terminal`.

## ✨ Changes

### 1. The rule lives in `Issue.save()`

**File:** `support/models.py`

- Moving to a terminal status sets today's date, unless the issue already has one.
- Moving between terminal statuses keeps the date.
- Moving to any other status, from anywhere, removes the date.

```python
if self.has_terminal_status():
    self.closing_date = self.closing_date or date.today()
else:
    self.closing_date = None
```

The rule does not need the previous status. When `update_fields` includes `status`, `closing_date` is added to it, because the bulk reassign tool saves that way. This is also why it is not a `pre_save` signal: a signal cannot add a field to `update_fields`.

`bulk_update` and `queryset.update()` do not call `save()`. The only one that changes statuses is `IssueStatus.sync_issues_with_terminal()`, which already handles the date.

### 2. The paths that wrote the date on their own

**Files:** `support/models.py`, `support/views/all_views.py`

- `apply_status_change()` only handles `next_action_date`.
- `mark_solved()` no longer overwrites the date of an issue that was already closed.
- `IssueDetailView` no longer sets the date when a resolution solves the issue automatically.
- `NewIssueView`, which created issues in a terminal status without a date, is covered by the rule.

### 3. The community console decides by status

**File:** `support/views/all_views.py`

`CommunityConsoleView`, `CommunityManagerDashboardView`, `CommunityManagerAssignView` and `CommunityManagerOverviewView` drop `closing_date__isnull=True` and keep the `is_terminal` exclusion.

## 📁 Files Modified

- **`support/models.py`** — `Issue.save()`, and `apply_status_change()` and `mark_solved()` without the date
- **`support/views/all_views.py`** — Community console filters and the automatic solve in `IssueDetailView`
- **`support/views/bulk_reassign_status.py`** — Comment
- **`tests/test_issue_status_terminal.py`** — The open issue with a date is now built with `update()`
- **`tests/test_issue_terminal_status_badge.py`** — Removes the case of a terminal status without a date, which no longer exists

## 📁 Files Created

- **`tests/test_issue_closing_date.py`** — The rule through `save()`, `update_fields`, `mark_solved()` and the issue page

## 🧪 Manual Testing

1. **Reopen and close again:**
   - Move an open issue to a terminal status from its page.
   - **Verify:** It has today's date.
   - Move it to a non terminal status.
   - **Verify:** It has no closing date, and it shows up in the community console if it is assigned.
   - Move it back to a terminal status.
   - **Verify:** It has the date of that day, not the first one.

2. **Edge case, between terminal statuses:**
   - Take a closed issue with an old date and move it to another terminal status.
   - **Verify:** The date does not change.

3. **Edge case, created closed:**
   - Create a new issue directly in a terminal status.
   - **Verify:** It has today's date.

## 📝 Deployment Notes

- No migrations required.
- **Normalize the data first.** Otherwise the next save of an old terminal issue without a date gives it today's date, and the next save of an open issue with a date removes it. la diaria does this with a one-off script in its private package, run before and after deploying.

## 🎓 Design Decisions

- **`save()` instead of a signal:** the model belongs to this repo, so a signal adds nothing, and it could not write through `update_fields`.
- **No previous status:** the rule depends only on the current status. That keeps it simple, and it is why the data has to be consistent before it applies.

---

- **Date:** 2026-11-05
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl99-fecha-cierre-regla
- **Type:** Bug Fix
- **Modules affected:** support
