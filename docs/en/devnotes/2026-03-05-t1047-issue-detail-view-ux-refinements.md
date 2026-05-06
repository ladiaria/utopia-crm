# Issue Detail View: UX Refinements and Compactness Improvements

**Date:** 2026-03-05
**Type:** UI/UX Enhancement
**Component:** Issue Management System
**Impact:** User Experience, Usability, Visual Design
**Issue:** t1047

## Summary

Following user feedback on the t1044 redesign, this update refines the Issue Detail View with a more compact, less colorful design focused on maximizing visible content and minimizing scrolling. Key improvements include removing the activities sidebar, reordering sections to prioritize the form, reducing visual noise, implementing auto-expanding textareas, and adding intelligent notes collapsing.

## Changes

### 1. Removed Activities Sidebar

**Rationale:** Users reported not using the activities functionality, and the sidebar consumed valuable horizontal space.

- **Removed entire right column** (activities list + activity modal)
- **Full-width layout** — form now uses the entire screen width
- **Cleaned up view context** — removed `activities`, `activity_form`, and `invoice_list` from `IssueDetailView.get_context_data()`
- **Performance benefit** — eliminates unnecessary database queries for activities and invoices

**Files Modified:**

- `support/templates/view_issue.html` — removed activities sidebar and modal HTML
- `support/views/all_views.py` — removed activity_form initialization and context data

### 2. Reordered Sections for Better Workflow

**New Order (top to bottom):**

1. **Header badges** — Category, Subcategory, Status (compact, muted colors)
2. **Debt alert** (invoicing issues only) — yellow bar with "View invoices" link
3. **Classification** — Subcategory + Resolution
4. **Status & Assignment** — Status, Assigned to, Next action date, Copies, Envelope
5. **Progress notes** — Large textarea for main progress tracking
6. **Answer 1 / Answer 2** — 4/8 column split for better proportions
7. **Contact info** — Compact single-line display at bottom
8. **Notes** — Collapsible section at the very bottom

**Rationale:** Users wanted to see the form/progress immediately upon opening an issue, with contact information accessible but not taking up prime screen real estate.

### 3. Less Colorful, More Compact Design

**Visual Changes:**

- **Removed colored section backgrounds** — replaced `background-color: #f8f9fa` sections with simple border separators
- **Muted badge colors** — changed from `badge-pill badge-primary/info/secondary` to `badge-dark/badge-secondary`
- **Removed most icons** — eliminated FontAwesome icons from section titles and labels
- **Smaller typography:**
  - Labels: `0.7rem` (was `0.75rem`)
  - Form labels: `0.75rem` (was default)
  - Form controls: `0.85rem` with `padding: 0.25rem 0.5rem`
  - Section titles: `0.7rem` (was `0.8rem`)
- **Tighter spacing:**
  - Form groups: `margin-bottom: 0.4rem` (was `0.75rem`)
  - Section padding: `0.5rem 0` (was `0.75rem 1rem`)
  - Card margins: `0.5rem` (was default)

**CSS Classes:**

```css
.issue-section { border-bottom: 1px solid #e9ecef; padding: 0.5rem 0; }
.form-group { margin-bottom: 0.4rem; }
.form-control { font-size: 0.85rem; padding: 0.25rem 0.5rem; }
```

### 4. Auto-Expanding Textareas

**Implementation:**

- **Progress textarea** — starts at 4 rows (~90px), auto-expands as content is typed
- **Answer 2 textarea** — starts at 2 rows (~44px), auto-expands as content is typed

**JavaScript:**

```javascript
function autoResize(el, minHeight) {
  el.style.height = 'auto';
  el.style.height = Math.max(minHeight, el.scrollHeight) + 'px';
}
```

**Form Widget Changes:**

```python
# support/forms.py - IssueChangeForm and InvoicingIssueChangeForm
"progress": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
"answer_2": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
```

**Benefits:**

- Textareas start compact to show more content above the fold
- Automatically grow to fit content as users type
- Shrink back when content is deleted
- No manual resizing needed

### 5. Collapsible Notes with Hidden Line Count

**Features:**

- Notes collapse to ~2 lines by default if longer
- Shows "Show more (X lines hidden) ▼" toggle when collapsed
- Click to expand/collapse
- Gradient fade effect when collapsed for visual clarity

**JavaScript:**

```javascript
var totalLines = Math.round($notesContent.prop('scrollHeight') / lineHeight);
var hiddenLines = Math.max(0, totalLines - 2);
var showMoreText = 'Show more (' + hiddenLines + ' lines hidden) ▼';
```

**Rationale:** Notes can be very long; collapsing them saves vertical space while still making them accessible with one click.

### 6. Answer 1 / Answer 2 Alignment Fix

**Before:** Both fields used `col-md-6` (50/50 split), causing blank space under Answer 1 (dropdown) when Answer 2 (textarea) was tall.

**After:** Answer 1 uses `col-md-4`, Answer 2 uses `col-md-8` (33/67 split).

**Rationale:** Answer 1 is typically a dropdown (short), Answer 2 is a textarea (taller). The 4/8 split gives Answer 2 more horizontal space and eliminates awkward blank space.

### 7. Normalized Choices.js Select Heights

**Problem:** Choices.js library (used for Subcategory and Assigned to) rendered selects taller than native HTML selects, creating visual inconsistency.

**Solution:**

```css
.choices .choices__inner {
  min-height: auto;
  padding: 0.25rem 0.5rem;
  font-size: 0.85rem;
}
```

**Result:** Choices.js selects now match the height and padding of native `<select>` elements.

### 8. White Text on SIP "Llamar" Buttons

**Problem:** The SIP filter outputs `<a class="button btn-primary">` links, but the text was black (poor contrast on blue background).

**Solution:**

```css
a.btn-primary, .button.btn-primary { color: #fff !important; }
```

**Result:** All primary buttons/links now have white text for proper contrast.

### 9. Compact Contact Information Display

**Layout:** Single-line row with contact name, start date, phone, created by, and product in columns.

**Additional row (if applicable):** Address and subscription information.

**Styling:**

```css
.compact-info { font-size: 0.8rem; }
```

**Rationale:** Contact info is important but secondary to the form. Displaying it compactly at the bottom keeps it accessible without consuming prime vertical space.

## Files Modified

- **`support/templates/view_issue.html`** — Complete template rewrite: removed sidebar, reordered sections, added auto-resize JS, collapsible notes, compact styling
- **`support/forms.py`** — Added `rows=4` to progress, `rows=2` to answer_2 in `IssueChangeForm` and `InvoicingIssueChangeForm`
- **`support/views/all_views.py`** — Removed activity_form, activities, and invoice_list from context

## Design Decisions

### Why remove the activities sidebar?

User feedback indicated the activities functionality was not being used, and the sidebar consumed ~33% of horizontal space. Removing it allows the form to use the full screen width, showing more content and reducing horizontal scrolling on smaller screens.

### Why reorder sections (form before contact info)?

Users wanted to see the progress textarea and form fields immediately upon opening an issue. Contact information is still accessible but moved to the bottom since it changes less frequently than the form fields.

### Why auto-expanding textareas instead of fixed heights?

Auto-expanding textareas provide the best of both worlds: they start compact (showing more content above the fold) but grow automatically to fit content as users type. This eliminates the need for scrollbars within textareas and reduces manual resizing.

### Why collapse notes by default?

Notes can be very long (multiple paragraphs), and they're typically read once when the issue is created but not edited frequently. Collapsing them to 2 lines saves significant vertical space while keeping them one click away.

### Why the 4/8 split for Answer 1/Answer 2?

Answer 1 is typically a dropdown (short height), while Answer 2 is a textarea (taller). A 50/50 split created awkward blank space under Answer 1. The 4/8 split gives Answer 2 more horizontal space (useful for longer text) and eliminates the visual imbalance.

## Ladiaria Compatibility

The `{% block issue_additional_actions %}` block remains in the same position (next to the Update button), so the ladiaria extension template that adds "Ofrecer Retención" and "Procesar Baja" buttons continues to work without modification.

## Deployment Notes

- No migrations required
- No new dependencies
- Template and form changes are immediately visible after deployment
- All existing functionality preserved (breadcrumbs, form validation, subcategory filtering, etc.)
- Performance improvement from removing unnecessary context queries
