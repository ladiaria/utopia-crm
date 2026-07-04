# Bulk Reassign Issue Status from the Issue List

- **Date:** 2026-06-15
- **Author:** Tanya Tree + Claude Opus 4.8
- **Ticket:** t1154
- **Type:** Feature
- **Component:** Support — Issues (list, detail), Core (Issue model)
- **Impact:** User Experience, Operator Productivity, Data Integrity

## 🎯 Summary

Support needed a way to change the **status** of many issues at once after filtering them, instead of editing each issue one by one from the issue detail view — unworkable when dozens or hundreds of issues share the same situation. This change adds a bulk-reassign tool integrated into the existing issue list (`list_issues`). The main risk driving the design was an operator accidentally selecting "everything" and reassigning issues they did not mean to, so the feature combines Gmail-style explicit selection, a mandatory two-step confirmation, a "narrow filter" guardrail for the whole-filter mode, and group-based access restriction. The shared status-change side effects (`next_action_date` / `closing_date`) were extracted to a model helper so the individual and bulk flows behave identically.

## ✨ Changes

### 1. Shared status-change helper on the Issue model

**File:** `support/models.py`

The `next_action_date` / `closing_date` rules that previously lived inline in `IssueDetailView.form_valid` were extracted to a reusable method, so both the individual and bulk flows apply the same logic:

```python
def apply_status_change(self, new_status):
    """Change status applying shared rules; returns changed field names.

    - Terminal new status (slug in ISSUE_STATUS_FINISHED_LIST) with no
      closing_date -> set closing_date to today.
    - Non-terminal new status with missing/past next_action_date -> set it
      to tomorrow.
    Does not save; the caller persists via save()/bulk_update.
    """
```

The method returns the list of modified field names so callers can pass them to `save(update_fields=...)`.

### 2. Individual issue edit reuses the shared helper

**File:** `support/views/all_views.py`

`IssueDetailView.form_valid` now delegates the post-save side effects to `apply_status_change`. As a deliberate consequence, selecting a terminal status manually now also sets `closing_date` (previously only set via the resolution-forces-solved path) — see Design Decisions.

### 3. Bulk reassign view (two-step, two selection modes)

**File:** `support/views/bulk_reassign_status.py` (new)

`BulkReassignIssueStatusView` accepts a POST with a destination `new_status` and a `mode`:

- `ids`: an explicit list of checked issue ids.
- `filter`: the whole filtered queryset, rebuilt server-side by replaying the original filter querystring through `IssueFilter` — the same mechanism the CSV export uses, so "the whole filter" always matches what the user saw.

The first POST (without `confirmed`) renders a confirmation screen; the second (`confirmed=1`) applies the change inside `transaction.atomic()`, calling `apply_status_change` per issue and logging each change to `LogEntry` (old → new). Access is restricted to superusers and the `Admins` group via `UserPassesTestMixin`.

### 4. Narrow-filter guardrail for whole-filter mode

**Files:** `support/views/bulk_reassign_status.py`, `support/views/all_views.py`, `support/templates/list_issues.html`

The whole-filter option is only available when the filter has **both** a `status` and a `sub_category` selected. This is enforced in two layers:

- **Backend (authoritative):** the view rejects a `filter`-mode POST with an error message when the querystring lacks either param.
- **Frontend (UX):** `IssueListView` exposes a `filter_is_narrow` flag; the list JS only shows the "Select all N matching the filter" banner when it is true.

### 5. List UI: checkboxes, action bar, Gmail-style banner

**File:** `support/templates/list_issues.html`

Added a checkbox column, a header check-all (selects the visible page), an action bar with a native status `<select>` (excluded from Chosen so it keeps auto width and the button sits beside it) and a "Change status" button, plus the whole-filter banner. The entire block is gated on `can_bulk_reassign`.

### 6. Confirmation screen

**File:** `support/templates/bulk_reassign_issue_status_confirm.html` (new)

An AdminLTE card showing the affected count, destination status, the current-status breakdown, and the issue date range (oldest / newest), with explicit "Confirm and apply" and "Cancel" buttons.

## 📁 Files Modified

- **`support/models.py`** — Added `Issue.apply_status_change`; imported `timedelta`
- **`support/views/all_views.py`** — `IssueDetailView.form_valid` reuses the helper; `IssueListView.get_context_data` exposes `can_bulk_reassign`, `issue_statuses`, `filter_querystring`, `filter_is_narrow`
- **`support/views/bulk_reassign_status.py`** — (new) bulk reassign view
- **`support/templates/list_issues.html`** — Selection UI, action bar, whole-filter banner, JS
- **`support/templates/bulk_reassign_issue_status_confirm.html`** — (new) confirmation screen
- **`support/urls.py`** — Route `bulk_reassign_issue_status`

## 📁 Files Created

- **`support/views/bulk_reassign_status.py`** — `BulkReassignIssueStatusView`
- **`support/templates/bulk_reassign_issue_status_confirm.html`** — Two-step confirmation template
- **`tests/test_bulk_reassign_issue_status.py`** — Test suite (10 tests)

## 📚 Technical Details

**Why `select_for_update(of=("self",))`:** the apply loop locks issue rows while iterating, but `status` and `contact` are nullable FKs and a plain `FOR UPDATE` over their outer joins is unsupported by PostgreSQL. Restricting the lock to the Issue table (`of="self"`) avoids the error.

**Server-side as the source of truth:** in `filter` mode the affected set is always recomputed from the querystring on the POST; the client never sends a final count or id list for whole-filter selection. The destination status is validated against the DB, never trusted from the POST.

**No signals lost:** `bulk`-style saves skip signals, but `support/signals.py` is currently empty, so there are no side effects bypassed. (Noted for the future.)

## 🧪 Manual Testing

1. **Happy path — reassign a few selected issues:**
   - As an Admin, open the issue list, filter, check 2–3 rows, pick a destination status, click "Change status", confirm.
   - **Verify:** Only the chosen issues change; one `LogEntry` is created per issue; a non-terminal status sets `next_action_date` to tomorrow.

2. **Happy path — whole-filter mode with a narrow filter:**
   - Select a `status` and a `sub_category` in the filter, check the page's header box, then click "Select all N issues matching the filter", pick a status, confirm.
   - **Verify:** The confirmation count and date range match the filtered set; all matching issues change.

3. **Edge case — whole-filter blocked without a narrow filter:**
   - Filter by status only (no subcategory).
   - **Verify:** The "select all the filter" banner does not appear; a hand-crafted `filter`-mode POST is rejected with an error and nothing changes.

4. **Edge case — terminal status sets closing_date:**
   - Reassign issues to a terminal status (e.g. "resuelto").
   - **Verify:** `closing_date` is set to today for affected issues.

5. **Edge case — permission denied:**
   - As a non-admin user, POST to the bulk endpoint.
   - **Verify:** 403; the list does not render the bulk UI for that user.

## 📝 Deployment Notes

- No database migrations required (only a new model method, no schema change).
- No configuration changes required.
- Access depends on the `Admins` group existing; superusers always have access.

## 🎓 Design Decisions

- **Two-layer guardrail.** Hiding the whole-filter banner in the UI is not enough — the same restriction is enforced in the view, so the dangerous "reassign everything" path cannot be triggered by a crafted request.
- **Unified status side effects.** Extracting `apply_status_change` made the individual edit also set `closing_date` on terminal statuses. This was confirmed as desirable: it matches `mark_solved()` and the meaning of "closing date", at the cost of a minor behavior change in the individual form.

## 🚀 Future Improvements

- Allow bulk-reassigning `assigned_to` or `resolution` (this ticket covers only `status`).
- Optional numeric cap with reinforced confirmation above N issues.

---

**Date:** 2026-06-15
**Author:** Tanya Tree + Claude Opus 4.8
**Branch:** t1154
**Type:** Feature
**Modules affected:** Support (Issues), Core (Issue model)
