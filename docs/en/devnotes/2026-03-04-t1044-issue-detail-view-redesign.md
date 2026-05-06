# Issue Detail View Redesign & UX Improvements

**Date:** 2026-03-04
**Type:** UI/UX Enhancement, Performance Optimization
**Component:** Issue Management System
**Impact:** User Experience, Performance, Accessibility
**Issue:** t1044

## Summary

Complete redesign of the Issue Detail View (`view_issue.html`) with a modern, compact layout, elimination of the broken invoice modal, N+1 query optimization in `NewIssueView`, and improved user display across all issue forms. The changes reduce scrolling, give prominence to important information (notes, debt), and show full user names alongside usernames throughout the issue management system.

## Changes

### 1. Issue Detail View Template Redesign

**File:** `support/templates/view_issue.html`

The entire template was redesigned for a cleaner, more organized layout:

- **Removed the broken invoice modal** — Replaced with a direct link to the contact's invoices tab (`contact_detail#invoices`) that opens in a new tab. The link clearly indicates "(new tab)" to set user expectations.
- **Labeled badges for Category, Subcategory, and Status** — Each badge in the card header now has a text label (e.g., "Category:", "Subcategory:", "Status:") and uses larger `badge-pill` styling for better readability.
- **Compact multi-column details card** — Contact info, dates, phone numbers, and "Created by" are displayed in a single row instead of a vertical definition list, significantly reducing vertical space.
- **Prominent notes section** — Notes are now displayed in a highlighted yellow-bordered box at the bottom of the details card, making them immediately visible.
- **Debt alert for invoicing issues** — Debt information is shown in a warm yellow alert box with the amount, overdue count, and a clear "View invoices" button linking to the contact's invoices tab in a new tab.
- **"No debt" positive feedback** — When a contact has no debt, a green success message is shown instead of just omitting the section.
- **Reorganized form with grouped sections:**
  - **Status & Assignment** (top) — Status, Assigned to, Next action date, Copies, and Envelope all in one row. `assigned_to` was moved from the bottom to the top of the form to reduce scrolling.
  - **Classification** — Subcategory and Resolution side by side.
  - **Progress Notes** — Progress textarea with Answer 1 and Answer 2 side by side.
- **Improved activities sidebar** — Compact activity cards with color-coded direction icons (green for incoming, blue for outgoing), status badges, scrollable container (max 600px), and an empty state message.
- **Related items displayed in a compact grid** — Subscription product, product, address, and subscription shown in columns instead of a vertical list.

### 2. Full Name Display for Users

**File:** `support/forms.py`

Created a reusable `UserFullNameChoiceField` that shows users as "Full Name (username)" instead of just "username":

```python
class UserFullNameChoiceField(forms.ModelChoiceField):
    """ModelChoiceField that displays users as 'Full Name (username)'"""
    def label_from_instance(self, obj):
        full_name = obj.get_full_name()
        if full_name:
            return f"{full_name} ({obj.username})"
        return obj.username
```

Applied to the `assigned_to` field in all three issue forms:

- **`IssueStartForm`** — New issue creation form
- **`IssueChangeForm`** — Issue edit form (non-invoicing categories)
- **`InvoicingIssueChangeForm`** — Issue edit form (invoicing/collections categories)

The "Created by" field in the template also now shows "Full Name (username)" format.

### 3. N+1 Query Optimization in NewIssueView

**File:** `support/views/all_views.py`

- **Prefetched contact relations** — `get_contact()` now uses `prefetch_related` for addresses and a nested `Prefetch` for active subscriptions with their products, eliminating repeated queries when rendering form dropdowns.
- **Optimized form querysets** — `get_form()` builds subscription and subscription product querysets from prefetched data with `select_related('contact')` and `select_related('product', 'subscription__contact', 'address')` to prevent N+1 queries triggered by `__str__` methods.
- **Cached subcategory resolutions** — The subcategory-to-resolution mapping is now cached at the class level to avoid repeated queries across requests.
- **Cached status lookup** — `get_initial()` caches the "new" status lookup to avoid redundant queries.
- **Default assigned_to** — The `assigned_to` field is now initialized to the currently logged-in user (users can change or remove it).

### 4. Ladiaria Extension Compatibility

**File:** `utopia_crm_ladiaria/templates/view_issue.html` (unchanged)

The `{% block issue_additional_actions %}` block remains in the same logical position (next to the Update button), so the ladiaria extension template that adds "Ofrecer Retención" and "Procesar Baja" buttons continues to work without any changes.

## Files Modified

- **`support/templates/view_issue.html`** — Complete template redesign
- **`support/forms.py`** — Added `UserFullNameChoiceField`, applied to `assigned_to` in 3 forms
- **`support/views/all_views.py`** — N+1 query optimization in `NewIssueView`, added `Prefetch` import

## Design Decisions

### Why remove the invoice modal?

The modal was broken (didn't properly display invoices) and provided a poor user experience. Linking directly to the contact's invoices tab in a new tab gives users the full invoice management interface with sorting, filtering, and download capabilities. The "(new tab)" indicator sets correct expectations.

### Why lift assigned_to to the top?

The `assigned_to` field was at the very bottom of a long form, requiring significant scrolling. As one of the most frequently changed fields (along with status), it makes sense to place it in the first section alongside status and next action date.

### Why show full names?

The default Django User `__str__` returns just the username (e.g., "jperez"), which is not immediately recognizable in organizations with many users. Showing "Juan Perez (jperez)" provides instant identification while keeping the username for technical reference.

### Why use a reusable field class?

`UserFullNameChoiceField` can be used anywhere in the system that needs to display user dropdowns with full names, maintaining consistency without code duplication.

## Deployment Notes

- No migrations required
- No new dependencies
- Template-only changes are immediately visible after deployment
- Form changes affect all issue creation and editing workflows
