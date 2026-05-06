# Seller Console Revamp: "No Encontrado" Button and Layout Rearrangement

**Date:** 2026-02-27
**Type:** Feature Enhancement, UI Improvement
**Component:** Seller Console, Campaign Management
**Impact:** Seller Workflow, Campaign Tracking
**Task:** t1037

## Summary

Revamped the seller console with a new "No encontrado" (Not Found) button and rearranged button layout. The new button allows sellers to mark contacts they couldn't reach, advancing to the next contact while keeping the marked contact in the campaign for retry. Contacts previously marked as "No encontrado" or "Llamar más tarde" are visually distinguished with color-coded badges and contact list indicators, giving sellers immediate context about each contact's history.

## Motivation

Sellers needed a way to indicate that a contact was not found/unreachable without removing them from the campaign. Previously, the only options were:

1. **"Llamar más tarde"** — marks as "call later" but doesn't semantically distinguish between "I'll call later" and "I couldn't find them"
2. **"No contactable"** / **"Cerrar sin contacto"** — these end the campaign for the contact entirely

The client requested: *"No encontrado (se pasa al próximo cliente y se marca con un color diferente)"* — a button that advances to the next contact and visually marks the current one with a different color.

Additionally, the button layout was rearranged per client request: red (declined) buttons moved to the left, yellow (pending) buttons in the middle, and green (success) buttons on the right.

## Implementation

### 1. New `NOT_FOUND` Action Type

**File:** `support/models.py`

Added a new action type to `SellerConsoleAction.ACTION_TYPES`:

```python
class ACTION_TYPES(models.TextChoices):
    SUCCESS = "S", _("Success")
    DECLINED = "D", _("Declined")
    PENDING = "P", _("Pending")
    NO_CONTACT = "N", _("No contact")
    SCHEDULED = "C", _("Scheduled")
    CALL_LATER = "L", _("Call later")
    NOT_FOUND = "F", _("Not found")  # New
```

### 2. New Campaign Resolution Code

**File:** `core/choices.py`

Added `NF` (Not Found) to `CAMPAIGN_RESOLUTION_CHOICES`:

```python
("NF", _("Not found")),
```

This is distinct from `UN` (Cannot find contact) which ends the campaign. `NF` keeps the contact in the campaign for retry.

### 3. Management Command Update

**File:** `core/management/commands/populate_seller_console_actions.py`

Added the new action to the `action_types_and_names` tuple:

| Action | Slug | Campaign Status | Campaign Resolution |
| -------- | ------ | ---------------- | ------------------- |
| No encontrado | `not-found` | CALLED_COULD_NOT_CONTACT (3) | NF |

**Key design decision:** Uses `CALLED_COULD_NOT_CONTACT` (status 3) — the same status as "call-later". This ensures the contact stays in the campaign queue because `get_not_contacted()` filters by `status__in=[1, 3]`.

### 4. Offset Increment for NOT_FOUND

**File:** `support/views/seller_console.py`

Updated `handle_post_request` to advance to the next contact for NOT_FOUND actions, alongside CALL_LATER:

```python
if seller_console_action.action_type in (
    SellerConsoleAction.ACTION_TYPES.CALL_LATER,
    SellerConsoleAction.ACTION_TYPES.NOT_FOUND,
):
    offset = int(offset) + 1
```

### 5. Last Action Datetime in Context

**File:** `support/views/seller_console.py`

Added `last_action_datetime` to the template context by querying the most recent Activity matching the contact's last console action. This provides the exact date and time when the "No encontrado" or "Llamar más tarde" action was performed:

```python
last_action_datetime = None
if hasattr(console_instance, 'last_console_action') and console_instance.last_console_action:
    last_action_activity = Activity.objects.filter(
        contact=contact,
        campaign=campaign,
        seller_console_action=console_instance.last_console_action,
    ).order_by('-datetime').first()
    if last_action_activity:
        last_action_datetime = last_action_activity.datetime
```

### 6. Optimized Query with `select_related`

**File:** `support/views/seller_console.py`

Added `select_related('last_console_action')` to `get_console_instances` for the "new" category to avoid N+1 queries when rendering the contacts list with color differentiation.

### 7. Template Rearrangement and Visual Indicators

**File:** `support/templates/seller_console.html`

**Button Layout Rearranged:**

| Left Column | Middle Column | Right Column |
| ------------- | ------------- | ------------- |
| Red — Declined/No Contact | Yellow — Pending | Green — Sales & Schedule |
| No interesado | Llamar más tarde | Send promo / Sell |
| No llamar | **No encontrado** (new) | Edit subscription |
| Logística | Mover a la mañana | Add product |
| Ya suscrito | Mover a la tarde | Change product |
| Error en promoción | | Schedule |
| No contactable | | |
| Cerrar sin contacto | | |

**Contact List Color Coding (collapsed contacts card):**

| Color | Meaning | Bootstrap Class |
| ------- | --------- | ---------------- |
| Orange/Warning | Contact marked as "No encontrado" | `btn-warning text-dark` + question-circle icon |
| Blue/Info | Contact marked as "Llamar más tarde" | `btn-info` |
| Gray | Untouched contact | `btn-secondary` |
| Blue/Primary | Currently active contact | `btn-primary` |

**Badge on Contact Card Header:**

When viewing a contact previously marked as "No encontrado" or "Llamar más tarde", a badge appears next to the contact's name showing the action and timestamp:

- 🟠 `ⓘ No encontrado — 27/02/2026 14:35`
- 🔵 `🕐 Llamar más tarde — 27/02/2026 10:20`

## Database Changes

### Migration: `core/migrations/0117_add_not_found_campaign_resolution.py`

- Altered `campaign_resolution` field on `ContactCampaignStatus` to include new `NF` choice

### Migration: `support/migrations/0035_add_not_found_action_type.py`

- Altered `action_type` field on `SellerConsoleAction` to include new `F` (Not Found) choice
- Altered `campaign_resolution` field on `SellerConsoleAction` to include new `NF` choice

## Data Flow

When a seller clicks "No encontrado":

1. **Form submits** with `result = "not-found"`
2. **`handle_post_request`** looks up `SellerConsoleAction` with slug `not-found`
3. **`process_activity_result`** updates `ContactCampaignStatus`:
   - `ccs.status = 3` (CALLED_COULD_NOT_CONTACT) — keeps contact in queue
   - `ccs.campaign_resolution = "NF"` — tracks as "Not found"
   - `ccs.last_console_action = not-found action` — for color differentiation
4. **Activity created** with `seller_console_action` reference
5. **Offset incremented** by 1 — seller advances to next contact
6. **On next visit**, the contact shows with orange color in the contacts list and a badge with timestamp in the card header

## Benefits

### For Sellers

- **Clear visual feedback**: Instantly see which contacts were previously marked as "not found" or "call later"
- **Non-destructive**: Contacts stay in the campaign for retry
- **Timestamp visibility**: Know exactly when the last action happened without digging into activities
- **Better layout**: Red (negative) actions on the left, yellow (pending) in the middle, green (positive) on the right — more intuitive flow

### For Managers

- **Better tracking**: `NF` resolution code distinguishes "not found" from "call later" (`CL`) in reports
- **Campaign analytics**: Can analyze how many contacts are unreachable vs. pending callback

## Usage

### Deployment Steps

```bash
python manage.py migrate
python manage.py populate_seller_console_actions
```

### Usage for Sellers

A new yellow "No encontrado" button appears in the middle column. Click it when you call a contact but can't reach them. The contact will:

- Move you to the next contact in the list
- Stay in the campaign (shown in orange when you expand the contacts card)
- Show an orange badge with the date/time next to their name when you revisit them

## Files Modified

- `support/models.py` — Added `NOT_FOUND = "F"` to `SellerConsoleAction.ACTION_TYPES`
- `core/choices.py` — Added `("NF", _("Not found"))` to `CAMPAIGN_RESOLUTION_CHOICES`
- `core/management/commands/populate_seller_console_actions.py` — Added `not-found` action entry
- `support/views/seller_console.py` — NOT_FOUND offset increment, `select_related`, `last_action_datetime` context
- `support/templates/seller_console.html` — Button rearrangement, new button, color coding, header badge
- `core/migrations/0117_add_not_found_campaign_resolution.py` — Campaign resolution migration
- `support/migrations/0035_add_not_found_action_type.py` — Action type migration

## Backward Compatibility

- Existing `SellerConsoleAction` records are unaffected
- New action is created by the management command
- Nullable fields ensure no issues with existing data
- Contacts without `last_console_action` display normally (gray/secondary)
- Django templates silently handle missing attributes for "act" category instances

## Notes

- The `NOT_FOUND` action type is intentionally separate from `CALL_LATER` despite sharing the same `campaign_status` (3). This allows distinct visual treatment and analytics tracking.
- The `NF` resolution code is distinct from `UN` (Cannot find contact): `UN` ends the campaign, `NF` keeps the contact for retry.
- The management command is idempotent — safe to run multiple times.
