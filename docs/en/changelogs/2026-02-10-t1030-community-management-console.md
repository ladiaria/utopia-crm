# Community Management Console (GDC Console)

**Date:** 2026-02-10
**Type:** New Feature
**Component:** Issue Management System
**Branch:** t1030
**Impact:** User Experience, Workflow Efficiency

## Summary

New interactive dashboard for community management (GDC) agents that displays open issues assigned to the current user, grouped by Category and Subcategory, with counts split into three temporal columns: Overdue, Today, and Future. Each count is a clickable link that opens the existing issue list with the appropriate filters pre-applied. Access is controlled by a dedicated permission.

## Motivation

GDC agents needed a quick overview of their assigned workload without manually filtering the issue list each time. The console provides an at-a-glance view of what needs attention now (overdue), what's due today, and what's coming up, organized by the issue categories they work with.

## Key Features Implemented

### 1. Community Console View

**File:** `support/views/all_views.py`

New `CommunityConsoleView` (inherits from `TemplateView`, `PermissionRequiredMixin`, `LoginRequiredMixin`, `BreadcrumbsMixin`) that:

- Queries open issues assigned to the current user (`closing_date__isnull=True`)
- Excludes issues in terminal state (`ISSUE_STATUS_FINISHED_LIST` from settings)
- Groups issues by Category → Subcategory using database aggregation (`Count` with `Q` filters)
- Counts Overdue (`date < today`), Today (`date == today`), and Future (`date > today`) for each group
- Passes structured data and date references to the template

### 2. Interactive Dashboard Template

**File:** `support/templates/community_console.html`

- **Summary cards** at the top showing grand totals for Overdue (red), Today (yellow), Future (green), and Total (gray)
- **Collapsible category cards** (accordion-style) with expand/collapse all buttons
- **Subcategory table** within each card: Subcategory | Overdue | Today | Future | Total
- **Clickable counts** that link to `IssueListView` with pre-applied filters (category, subcategory, date range, assigned_to, exclude_finished)
- **Color-coded badges**: red for overdue, yellow for today, green for future
- **Real-time search bar** (JavaScript) to filter categories/subcategories by name
- **Instructions card** at the bottom explaining how dates are determined and how to interact with the console

### 3. Custom Permission

**File:** `support/models.py`

Added `can_access_community_console` permission to the `Issue` model's `Meta.permissions`, controlling who can access the console.

### 4. `has_perm` Template Filter

**File:** `core/templatetags/core_tags.py`

New template filter for cleaner permission checks in templates, used instead of `in_group` for more flexible access control:

```html
{% if request.user|has_perm:"support.can_access_community_console" %}
```

### 5. Sidebar Menu Item

**File:** `templates/components/_sidebar.html`

New "Community console" menu item with `fas fa-users` icon, visible only to users with the `can_access_community_console` permission.

### 6. `exclude_finished` Filter for IssueListView

**File:** `support/filters.py`

New `BooleanFilter` with checkbox widget added to `IssueFilter`. When checked, excludes issues whose status slug is in `settings.ISSUE_STATUS_FINISHED_LIST`. This filter is:

- Passed automatically (`&exclude_finished=true`) by all console links for consistency
- Available as a standalone checkbox in the issue list filter form for any user

**File:** `support/templates/list_issues.html`

Added the "Exclude finished" checkbox to the filter form, next to the issue count callout.

## Bug Fixes

### Fix: `None` Passed as Query Parameter

**Root cause:** When an issue has no subcategory, `sub_category__id` is `None`. The template rendered `sub_category=None` literally in the URL. Django-filters v23.4 with `strict=True` invalidates the form when it encounters an invalid value for a `ModelChoiceFilter`, returning an **empty queryset**. This is why results only appeared after pressing "Filter" manually (which resubmits without the invalid param).

**Fix:** Changed all template links to use `{% if sub.id %}&sub_category={{ sub.id }}{% endif %}` — the parameter is only included when it has a real value.

## Technical Details

### Files Created

- `support/templates/community_console.html` — Dashboard template
- `support/migrations/0033_add_community_console_permission.py` — Migration for the new permission

### Files Modified

- `support/models.py` — Added `can_access_community_console` permission to `Issue.Meta`
- `support/views/all_views.py` — Added `CommunityConsoleView`
- `support/urls.py` — Added URL pattern for the console
- `support/filters.py` — Added `exclude_finished` filter and `filter_exclude_finished` method
- `support/templates/list_issues.html` — Added "Exclude finished" checkbox
- `templates/components/_sidebar.html` — Added permission-gated menu item
- `core/templatetags/core_tags.py` — Added `has_perm` template filter

### Database Impact

- **One migration required:** Adds the `can_access_community_console` permission to the `Issue` model
- After migrating, the permission must be assigned to the appropriate users/groups via Django admin

### Performance Considerations

- Uses database-level aggregation (`Count` with `Q` filters) — no N+1 queries
- `select_related('sub_category', 'status')` for efficient joins
- Single query with `.values().annotate()` for all grouping and counting

## Migration Notes

1. Run `python manage.py migrate support` to create the new permission
2. Assign the `support.can_access_community_console` permission to users or groups that need access to the GDC console
3. The `ISSUE_STATUS_FINISHED_LIST` setting must be defined in your settings for terminal-state exclusion to work

## Testing Recommendations

### Manual Testing

1. **Permission check:** Verify the console is only accessible to users with `can_access_community_console`
2. **Data accuracy:** Verify overdue/today/future counts match the actual issues
3. **Terminal state exclusion:** Verify finished/resolved issues don't appear in the console
4. **Link navigation:** Click each count and verify the issue list shows the correct filtered results
5. **No subcategory:** Verify issues without a subcategory don't cause "None" in URLs
6. **Search filter:** Type in the search bar and verify categories/subcategories filter in real time
7. **Expand/Collapse:** Test the expand all, collapse all, and individual card toggle
8. **Exclude finished checkbox:** Verify the checkbox works in the issue list independently
9. **Sidebar visibility:** Verify the menu item only appears for permitted users

## Related Components

- **Issue Model:** `support/models.py`
- **Issue List View:** `support/views/all_views.py` — `IssueListView`
- **Issue Filter:** `support/filters.py` — `IssueFilter`
- **Settings:** `ISSUE_STATUS_FINISHED_LIST` — Defines terminal statuses
