# Seller Console: Scheduled Activity Fixes and Scheduled Activities Page Improvements

**Date:** 2026-03-02
**Type:** Bug Fix, Feature Enhancement, UI Improvement
**Component:** Seller Console, Scheduled Activities Page
**Impact:** Seller Workflow, Campaign Management, User Experience
**Task:** t1037

## Summary

This update fixes three bugs in the seller console's "act" (scheduled activities) mode and significantly improves the Scheduled Activities page with better filtering, visual feedback, and Select2 integration. It also adds proper ordering of contacts in the "new" mode by assignment date.

## Bug Fixes

### 1. `seller_console_action` Not Saved on Activity in "act" Mode

**File:** `support/views/seller_console.py`

**Problem:** When processing a scheduled activity in "act" mode, the existing activity was updated with notes, status, and datetime, but the `seller_console_action` field was never set on it. This meant the action taken by the seller was not recorded on the activity record.

**Root Cause:** The `handle_post_request` method updated the activity fields but missed setting `activity.seller_console_action = seller_console_action` before calling `activity.save()`.

**Fix:** Added `activity.seller_console_action = seller_console_action` to the activity update block in "act" mode.

### 2. Notes Textarea Pre-filled with Scheduled Message

**File:** `support/templates/seller_console.html`

**Problem:** When a seller opened a scheduled activity in the console, the notes textarea was pre-filled with the scheduling message (e.g., "Scheduled for 2026-03-05 10:00"). This forced the seller to manually clear or overwrite it.

**Root Cause:** The template had a conditional that pre-filled the textarea with `{{ console_instance.notes }}` for "act" mode.

**Fix:** Removed the conditional — the textarea is now always blank so the seller writes fresh notes for each action.

### 3. "No Encontrado" / "Llamar más tarde" Drops Contact from "act" Queue

**File:** `support/views/seller_console.py`

**Problem:** When clicking "No encontrado" or "Llamar más tarde" in "act" mode, the contact would disappear from the scheduled activities queue and fall back into the "new" section.

**Root Cause:** The flow was:

1. The existing pending activity was marked as COMPLETED
2. `process_activity_result` set `ccs.status = 3` (CALLED_COULD_NOT_CONTACT)
3. No new pending activity was created (only happened when `KEEP_CONTACTS_IN_CAMPAIGNS_INDEFINITELY` was enabled)
4. Without a pending activity, the contact fell out of the "act" queue (which filters `status="P"`)
5. Since `ccs.status = 3`, the contact appeared in the "new" queue instead (`get_not_contacted` filters `status__in=[1, 3]`)

**Fix:** Two changes:

- In `handle_post_request`: CALL_LATER and NOT_FOUND in "act" mode now always call `register_new_activity`, regardless of the `KEEP_CONTACTS_IN_CAMPAIGNS_INDEFINITELY` setting.
- In `register_new_activity`: Added an early-return path for CALL_LATER/NOT_FOUND in "act" mode that always creates a new pending activity dated using the `SELLER_CONSOLE_CALL_LATER_DAYS` setting (default: 1 day), keeping the contact in the "act" queue.

## Feature Enhancements

### 4. Color-Coded Contacts in "act" Mode

**Files:** `support/views/seller_console.py`, `support/templates/seller_console.html`

**Problem:** The color-coded contact cards (orange for "No encontrado", blue for "Llamar más tarde") and the header badge with action datetime only worked in "new" mode because they relied on `ContactCampaignStatus.last_console_action`, which doesn't exist on `Activity` objects.

**Solution:**

- **Template:** Used Django's `|default` filter to check both fields: `{% with action=instance.last_console_action|default:instance.seller_console_action %}`. This resolves the action from whichever field exists on the instance — `last_console_action` for ContactCampaignStatus in "new" mode, `seller_console_action` for Activity in "act" mode.
- **View:** Added `select_related('seller_console_action')` to both "act" mode querysets to prevent N+1 queries.
- **View:** Updated the `last_action_datetime` context logic to use `getattr` with fallback, checking both `last_console_action` and `seller_console_action`.

### 5. Contact Ordering by Assignment Date in "new" Mode

**File:** `core/models.py`

**Problem:** Contacts in "new" mode had no explicit ordering, falling back to the model's default `Meta.ordering = ["id"]`. This meant contacts assigned later could appear before those assigned earlier.

**Solution:** Added explicit ordering to `get_not_contacted()`:

```python
.order_by(F('date_assigned').asc(nulls_last=True), 'contact__id')
```

This ensures:

1. **`date_assigned` ascending** — earliest-assigned contacts come first
2. **`contact__id` ascending** — tiebreaker for same assignment date (older contacts first)
3. **Nulls last** — contacts without an assigned date go to the end

### 6. Scheduled Activities Page Overhaul

**Files:** `support/filters.py`, `support/views/activities.py`, `support/templates/scheduled_activities.html`

#### 6a. Active Campaigns Only in Filter

The campaign dropdown now only shows active campaigns, ordered by name:

```python
campaign = django_filters.ModelChoiceFilter(
    queryset=Campaign.objects.filter(active=True).order_by('name'),
)
```

#### 6b. Select2 Integration

All three filter dropdowns (Status, Campaign, Console Action) now use Select2 with the Bootstrap 4 theme, providing search and clear functionality. CSS and JS are loaded via the `stylesheets` and `extra_js` template blocks.

#### 6c. Pastel Row Colors

Activities are now color-coded by their date relative to today:

- **Pastel red** (`#fce4e4`) — overdue activities (date < today)
- **Pastel yellow** (`#fff9e6`) — today's activities
- **Pastel blue** (`#e8f4fd`) — future activities

A small color legend is displayed in the table header for reference. The `table-striped` class was removed to allow the pastel colors to show clearly.

#### 6d. Date Range Preset Buttons

Six date range preset buttons replace manual date entry for common use cases:

| Button | Filter | Color |
| -------- | -------- | ------- |
| Past (overdue) | `datetime < today` | Danger (red outline) |
| Today | `datetime = today` | Warning (yellow outline) |
| Future | `datetime > today` | Info (blue outline) |
| Past + Today | `datetime <= today` | Secondary (gray outline) |
| Today + Future | `datetime >= today` | Primary (blue outline) |
| Custom | Shows date_from/date_to fields | Dark outline |

**Behavior:**

- Non-custom presets auto-submit the form on click
- Buttons are toggleable (click again to deselect and auto-submit to clear)
- "Custom" opens date_from/date_to fields with animated slide; requires manual Search click
- Active state persists after form submission via `request.GET.date_range`

#### 6e. Visual Separation of Date Sections

Added an `<hr>` separator and changed the icon from `fa-calendar-alt` to `fa-file-contract` for the subscription end date fields, making them visually distinct from the activity date filters above.

## Technical Details

### Files Modified

1. **`support/views/seller_console.py`**
   - Fixed: `seller_console_action` now saved on activity in "act" mode
   - Fixed: CALL_LATER/NOT_FOUND in "act" mode always creates new pending activity
   - Added: `select_related('seller_console_action')` on "act" mode querysets
   - Updated: `last_action_datetime` logic handles both "new" and "act" modes

2. **`support/templates/seller_console.html`**
   - Fixed: Notes textarea always blank (removed `{{ console_instance.notes }}` pre-fill)
   - Updated: Contact card colors use `|default` to check both `last_console_action` and `seller_console_action`
   - Updated: Header badge uses same `|default` pattern

3. **`core/models.py`**
   - Added: `F` import for ordering expressions
   - Added: `.order_by(F('date_assigned').asc(nulls_last=True), 'contact__id')` to `get_not_contacted()`

4. **`support/filters.py`**
   - Added: `ACTIVITY_DATE_CHOICES` tuple with 6 preset options
   - Added: `date_range` ChoiceFilter with HiddenInput widget and `filter_by_date_range` method
   - Added: `date_from` and `date_to` filters for custom date ranges
   - Updated: Campaign filter queryset to active campaigns only

5. **`support/views/activities.py`**
   - Added: `date` import
   - Added: `today` to context for template row color comparisons

6. **`support/templates/scheduled_activities.html`**
   - Added: Select2 CSS/JS includes
   - Added: Pastel row color CSS classes (`.row-overdue`, `.row-today`, `.row-future`)
   - Added: Date range preset button group with auto-submit
   - Added: Custom date fields (hidden by default, shown when "Custom" selected)
   - Added: Color legend in table header
   - Added: `<hr>` separator and distinct icon for subscription date fields
   - Added: Select2 initialization JavaScript
   - Removed: `table-striped` to allow pastel colors to show

### Database Impact

- **No migrations required** — all changes are view/template/filter level
- The `F('date_assigned')` ordering uses an existing indexed field

### Performance Considerations

- `select_related('seller_console_action')` on "act" querysets prevents N+1 queries when rendering contact cards
- Date range filtering happens at database level via django_filters
- Select2 loads client-side with no additional server requests
