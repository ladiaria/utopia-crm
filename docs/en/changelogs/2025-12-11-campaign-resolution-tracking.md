# Campaign Resolution Tracking in Seller Console

**Date:** 2025-12-11
**Type:** Feature Enhancement, Data Tracking
**Component:** Seller Console, Campaign Management
**Impact:** Campaign Analytics, Reporting
**Task:** t982

## Summary

Enhanced the seller console to properly track campaign resolutions by adding a `campaign_resolution` field to the `SellerConsoleAction` model. This ensures that when sellers take actions (e.g., "not interested", "do not call", "logistics"), the system now records both the campaign status and the specific resolution reason, enabling comprehensive campaign outcome tracking and analytics.

## Motivation

The seller console was only partially tracking campaign outcomes:

1. **Incomplete tracking:** Only `campaign_status` was being set (e.g., ENDED_WITH_CONTACT), but `campaign_resolution` remained null
2. **Missing resolution data:** The `campaign_resolution` field was only set by `mark_as_sale` (to "S2"), but never set for decline/no-contact actions
3. **Limited analytics:** Without resolution data, it was impossible to analyze why campaigns ended (not interested vs. do not call vs. logistics, etc.)
4. **Inconsistent data:** The `resolution_reason` dropdown was being saved, but the primary `campaign_resolution` field was not

This made it difficult to generate meaningful reports on campaign outcomes and understand why contacts were declining or unreachable.

## Implementation

### 1. Added `campaign_resolution` Field to `SellerConsoleAction` Model

**File:** `support/models.py`

Added a new field to store which campaign resolution should be set when each action is performed:

```python
class SellerConsoleAction(models.Model):
    # ... existing fields ...
    campaign_resolution = models.CharField(
        max_length=2,
        choices=CAMPAIGN_RESOLUTION_CHOICES,
        null=True,
        blank=True,
        help_text=_("Campaign resolution to set when this action is performed"),
    )
```

**Resolution Codes Mapping:**

- `NI` - Not interested
- `DN` - Do not call anymore
- `LO` - Logistics
- `AS` - Already a subscriber
- `EP` - Error in promotion
- `UN` - Cannot find contact
- `CW` - Close without contact
- `SC` - Scheduled
- `CL` - Call later

### 2. Updated `process_activity_result` Method

**File:** `support/views/seller_console.py`

Enhanced the method to set `campaign_resolution` from the action:

```python
def process_activity_result(self, contact, campaign, seller, seller_console_action, notes):
    # ... existing code ...

    # Use the campaign_status from the action if it's set
    if seller_console_action.campaign_status:
        ccs.status = seller_console_action.campaign_status

    # Use the campaign_resolution from the action if it's set
    if seller_console_action.campaign_resolution:
        ccs.campaign_resolution = seller_console_action.campaign_resolution

    return ccs
```

### 3. Enhanced Management Command

**File:** `core/management/commands/populate_seller_console_actions.py`

Updated the command to populate `campaign_resolution` values for each action:

**Changes:**

- Expanded tuple structure from 4-tuple to 5-tuple: `(action_type, slug, action_name, campaign_status, campaign_resolution)`
- Added resolution codes for each action
- Updated output to display both status and resolution

**Action Mappings:**

| Action | Slug | Campaign Status | Campaign Resolution |
|--------|------|----------------|-------------------|
| Llamar más tarde | `call-later` | CALLED_COULD_NOT_CONTACT (3) | CL |
| Mover a la mañana | `move-morning` | SWITCH_TO_MORNING (6) | None |
| Mover a la tarde | `move-afternoon` | SWITCH_TO_AFTERNOON (7) | None |
| No interesado | `not-interested` | ENDED_WITH_CONTACT (4) | NI |
| No llamar | `do-not-call` | ENDED_WITH_CONTACT (4) | DN |
| Logística | `logistics` | ENDED_WITH_CONTACT (4) | LO |
| Ya suscrito | `already-subscriber` | ENDED_WITH_CONTACT (4) | AS |
| Error en promoción | `error-promotion` | ENDED_WITHOUT_CONTACT (5) | EP |
| No contactable | `uncontactable` | ENDED_WITHOUT_CONTACT (5) | UN |
| Cerrar sin contacto | `close-without-contact` | ENDED_WITHOUT_CONTACT (5) | CW |
| Agendar | `schedule` | CONTACTED (2) | SC |

**Note:** Morning/afternoon moves have no resolution since they're still pending actions.

### 4. Fixed Seller Console Template Structure

**File:** `support/templates/seller_console.html`

Fixed critical HTML structure issues that were preventing form submission:

**Issues Fixed:**

1. **Missing form closing tag:** The `<form>` tag opened at line 256 but never closed properly
2. **Orphan closing div:** Extra `</div>` tag with no matching opening tag
3. **Broken form submission:** The `campaign_resolution_reason` field was not being submitted due to malformed HTML

**Changes:**

- Added proper `</form>` closing tag after all form inputs and buttons
- Removed orphan `</div>` tag
- Fixed indentation and nesting of sidebar column

This ensures that when users select a resolution reason from the dropdown and click an action button, all form data (including `campaign_resolution_reason`) is properly submitted.

## Database Changes

### Migration: `support/migrations/0031_sellerconsoleaction_campaign_resolution_and_more.py`

**Changes:**

- Added `campaign_resolution` field to `SellerConsoleAction` model
- Field is nullable and optional for backward compatibility
- Uses `CAMPAIGN_RESOLUTION_CHOICES` for validation

## Data Flow

When a seller takes an action in the seller console:

1. **User clicks action button** (e.g., "No interesado")
2. **Form submits** with:
   - `result` = action slug (e.g., "not-interested")
   - `campaign_resolution_reason` = optional dropdown value
   - `notes` = activity notes
3. **`handle_post_request` processes:**
   - Looks up `SellerConsoleAction` by slug
   - Calls `process_activity_result`
4. **`process_activity_result` sets:**
   - `ccs.status` = `seller_console_action.campaign_status` (e.g., 4 = ENDED_WITH_CONTACT)
   - `ccs.campaign_resolution` = `seller_console_action.campaign_resolution` (e.g., "NI")
   - `ccs.resolution_reason` = from dropdown (if selected)
   - `ccs.last_console_action` = the action object
5. **`ccs.save()`** persists all tracking data

## Complete Tracking

The system now tracks three levels of campaign outcome information:

1. **`campaign_status`** (integer): High-level status (contacted, ended with contact, ended without contact, etc.)
2. **`campaign_resolution`** (2-char code): Specific outcome reason (NI, DN, LO, AS, EP, UN, CW, SC, CL)
3. **`resolution_reason`** (integer): Optional detailed reason from dropdown (project-specific)
4. **`last_console_action`** (FK): Which button was pressed

## Benefits

### 1. Complete Campaign Analytics

- Track exactly why campaigns ended (not interested vs. do not call vs. logistics)
- Analyze patterns in contact responses
- Generate detailed outcome reports

### 2. Better Reporting

- Campaign statistics now show complete resolution data
- Managers can see breakdown of decline reasons
- Export data includes all resolution information

### 3. Data Consistency

- All seller console actions now set appropriate resolutions
- No more null `campaign_resolution` fields for declined contacts
- Consistent data structure across all campaigns

### 4. Improved Form Submission

- Fixed HTML structure ensures all form data is submitted
- Resolution reason dropdown now works correctly
- No more lost form data due to malformed HTML

## Usage

### For Developers

**Running the management command:**

```bash
python manage.py populate_seller_console_actions
```

This will update all existing `SellerConsoleAction` records with appropriate `campaign_resolution` values.

### For Managers

Campaign statistics and reports now include complete resolution data:

- View why contacts declined (not interested, do not call, logistics, etc.)
- Analyze campaign effectiveness by resolution type
- Export detailed outcome data for analysis

### For Sellers

No changes to workflow - sellers continue using the same buttons, but now the system tracks complete outcome information automatically.

## Testing

### Verification Steps

1. **Check action configuration:**

   ```python
   from support.models import SellerConsoleAction
   actions = SellerConsoleAction.objects.all()
   for action in actions:
       print(f"{action.slug}: status={action.campaign_status}, resolution={action.campaign_resolution}")
   ```

2. **Test seller console:**
   - Open seller console for any campaign
   - Click "No interesado" button
   - Verify in database:

     ```sql
     SELECT status, campaign_resolution, resolution_reason, last_console_action_id
     FROM core_contactcampaignstatus
     WHERE contact_id = <contact_id> AND campaign_id = <campaign_id>;
     ```

   - Should show: `status=4, campaign_resolution='NI'`

3. **Check campaign statistics:**
   - View campaign statistics detail page
   - Verify resolution data is displayed
   - Export CSV and check resolution column

## Files Modified

- `support/models.py` - Added `campaign_resolution` field
- `support/views/seller_console.py` - Updated `process_activity_result` method
- `core/management/commands/populate_seller_console_actions.py` - Enhanced with resolution mapping
- `support/templates/seller_console.html` - Fixed HTML structure
- `support/migrations/0031_sellerconsoleaction_campaign_resolution_and_more.py` - Database migration

## Backward Compatibility

- Existing `SellerConsoleAction` records are automatically updated by the management command
- Nullable field ensures no issues with existing data
- Old code continues to work (just doesn't set resolution)
- No breaking changes to API or views

## Future Enhancements

Potential improvements for future iterations:

1. **Resolution analytics dashboard:** Dedicated view showing resolution breakdowns
2. **Resolution-based filtering:** Filter campaigns by resolution type
3. **Automated reports:** Scheduled reports showing resolution trends
4. **Resolution recommendations:** Suggest actions based on contact history

## Related Issues

- Fixes incomplete campaign outcome tracking
- Resolves null `campaign_resolution` fields for declined contacts
- Addresses form submission issues in seller console template

## Notes

- The `resolution_reason` field (dropdown) is separate and optional - it provides additional project-specific detail
- Morning/afternoon moves intentionally have no resolution since they're pending actions, not final outcomes
- The management command is idempotent and safe to run multiple times
