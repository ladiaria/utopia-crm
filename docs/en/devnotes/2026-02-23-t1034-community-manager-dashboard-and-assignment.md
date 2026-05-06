# Community Manager Dashboard, Issue Assignment, and Team Overview

**Date:** 2026-02-23
**Type:** New Feature
**Component:** Issue Management System (GDC)
**Branch:** t1034
**Impact:** Workflow Efficiency, Team Management, Issue Distribution

## Summary

New set of views for GDC (Community Management) managers that enables them to:

1. **Dashboard** — See all subcategories with unassigned issue counts, broken down by overdue/today/future.
2. **Assignment** — Assign unassigned issues from a subcategory to GDC team members using a round-robin algorithm.
3. **Team Overview** — Monitor all GDC users' assigned issue workloads with collapsible per-category/subcategory breakdowns.

Access is controlled by a new dedicated permission `can_manage_community_console`.

## Motivation

GDC managers needed a centralized way to:

- See which subcategories have unassigned issues piling up
- Distribute those issues fairly among team members
- Monitor each team member's workload at a glance
- Drill down into per-category/subcategory detail per user

Previously, managers had to manually query the issue list and assign issues one by one, with no visibility into team workload distribution.

## Key Features Implemented

### 1. New Permission: `can_manage_community_console`

**Files:** `support/models.py`, `support/migrations/0034_add_community_manager_permission.py`

Added a new permission to `Issue.Meta.permissions` that controls access to all three manager views. A migration creates this permission in the database.

### 2. Community Manager Dashboard View

**Files:** `support/views/all_views.py`, `support/templates/community_manager_dashboard.html`

`CommunityManagerDashboardView` (inherits `TemplateView`, `PermissionRequiredMixin`, `LoginRequiredMixin`, `BreadcrumbsMixin`):

- Queries open issues that are **unassigned** (`assigned_to__isnull=True`, `closing_date__isnull=True`)
- Excludes issues in terminal statuses (`ISSUE_STATUS_FINISHED_LIST`)
- Groups by Category → Subcategory using database aggregation (`Count` with `Q` filters)
- Counts Overdue, Today, Future, and Total for each group
- **Summary cards** at the top showing grand totals, clearly labeled as *"(unassigned)"*
- **Total unassigned card** includes note: *"(includes issues without next action date)"*
- **Collapsible category cards** with expand/collapse all functionality
- **Subcategory table** with clickable counts linking to filtered issue list
- **"Assign" link** per subcategory navigating to the assignment view
- **Real-time search bar** (JavaScript) to filter categories/subcategories by name
- Link to **Team Overview** in the header

### 3. Community Manager Assignment View

**Files:** `support/views/all_views.py`, `support/templates/community_manager_assign.html`

`CommunityManagerAssignView` (inherits `TemplateView`, `PermissionRequiredMixin`, `LoginRequiredMixin`, `BreadcrumbsMixin`):

- Shows unassigned issues for a specific subcategory
- **Summary cards** showing unassigned overdue/today/future/total, all labeled *"(Unassigned)"*
- **Info alert** when issues lack a next action date, explaining they'll get tomorrow's date upon assignment
- **Team member table** showing each GDC user with:
  - Current total open issues (with note: *"includes without date"*)
  - Overdue / Today / Future breakdown of their current workload
  - Input field to specify how many issues to assign
- **Round-robin assignment algorithm** distributes oldest unassigned issues evenly among selected users
- On assignment:
  - Sets `assigned_to` to the selected user
  - Keeps the issue's current status unchanged
  - Sets `next_action_date` to tomorrow if null or in the past
- **Client-side validation** ensures total assigned doesn't exceed available issues
- Success message after assignment with redirect back to dashboard

### 4. Community Manager Team Overview View

**Files:** `support/views/all_views.py`, `support/templates/community_manager_overview.html`

`CommunityManagerOverviewView` (inherits `TemplateView`, `PermissionRequiredMixin`, `LoginRequiredMixin`, `BreadcrumbsMixin`):

- Shows all active users with `can_access_community_console` permission
- **Summary cards** showing team-wide totals, labeled *"(assigned)"*
- **Total card** includes note: *"(includes issues without next action date)"*
- **Team members table** with:
  - Overdue / Today / Future / Total columns with clickable counts linking to filtered issue list
  - **Distribution progress bar** showing visual proportion of overdue (red), today (yellow), future (green)
  - **Collapsible per-user breakdown** — click a user row to expand/collapse their per-category and subcategory detail
    - Category rows with folder icon and subtotals
    - Subcategory rows indented with tag icon
    - All breakdown rows show overdue/today/future/total aligned with header columns
- **Grand totals footer row**
- **Legend card** explaining columns and interactions, including note about issues without next action date

### 5. Sidebar Integration

**File:** `templates/components/_sidebar.html`

Added a new sidebar menu entry "Community manager" visible only to users with the `can_manage_community_console` permission, linking to the dashboard.

### 6. URL Routes

**File:** `support/urls.py`

Three new URL patterns:

- `community-manager/` → `CommunityManagerDashboardView` (name: `community_manager_dashboard`)
- `community-manager/assign/<int:subcategory_id>/` → `CommunityManagerAssignView` (name: `community_manager_assign`)
- `community-manager/overview/` → `CommunityManagerOverviewView` (name: `community_manager_overview`)

## UX Clarity Improvements

Throughout all views, special attention was paid to making the numbers unambiguous:

- **Dashboard cards**: Labeled "Overdue (unassigned)", "Today (unassigned)", "Future (unassigned)", "Total unassigned"
- **Assign view cards**: Labeled with "(Unassigned)" suffix
- **Overview cards**: Labeled "Overdue (assigned)", "Today (assigned)", "Future (assigned)", "Total assigned to team"
- **All total cards**: Include small text "(includes issues without next action date)"
- **Assign view table header**: "Current total open issues" with "(includes without date)" subtitle
- **Overview legend**: Explains that Total may be higher than Overdue + Today + Future because some issues don't have a next action date

## Technical Details

### Files Modified

1. **`support/models.py`** — Added `can_manage_community_console` permission to `Issue.Meta.permissions`
2. **`support/views/all_views.py`** — Added three new class-based views (~370 lines)
3. **`support/urls.py`** — Added imports and three URL patterns
4. **`templates/components/_sidebar.html`** — Added sidebar entry with permission check

### Files Created

1. **`support/migrations/0034_add_community_manager_permission.py`** — Migration for new permission
2. **`support/templates/community_manager_dashboard.html`** — Dashboard template
3. **`support/templates/community_manager_assign.html`** — Assignment form template
4. **`support/templates/community_manager_overview.html`** — Team overview template

### Database Impact

- **One migration required** — Adds the `can_manage_community_console` permission
- **No schema changes** — Uses existing Issue model fields
- **Assignment updates** — Sets `assigned_to`, `status`, and `next_action_date` on issues

### Settings Dependencies

- `ISSUE_STATUS_FINISHED_LIST` — List of status slugs considered terminal/finished

## Testing Recommendations

### Manual Testing

1. **Permission check**: Verify only users with `can_manage_community_console` can access the views
2. **Dashboard**: Verify unassigned issue counts match reality per subcategory
3. **Assignment**: Assign issues to multiple users, verify round-robin distribution
4. **Next action date**: Verify issues without dates get tomorrow's date after assignment
5. **Team overview**: Verify per-user counts, expand/collapse breakdown, clickable links
6. **Sidebar**: Verify menu entry appears only for authorized users

### Edge Cases

1. No unassigned issues for a subcategory
2. No GDC users configured
3. Assigning more issues than available (should be prevented by validation)
4. Issues with null next_action_date
5. All issues already assigned

## Related Components

- **CommunityConsoleView** (`support/views/all_views.py`) — Individual user's console (existing)
- **IssueListView** (`support/views/all_views.py`) — Issue list with filtering (linked from all views)
- **AssignSellerView** (`support/views/all_views.py`) — Round-robin algorithm reference
