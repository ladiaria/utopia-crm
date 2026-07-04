# Subscription Reactivation Feature

**Date:** 2025-12-18
**Ticket:** t990
**Type:** Feature Enhancement
**Component:** Subscriptions, Activities, Core Models
**Impact:** Subscription Management, Activity Tracking, Data Preservation

## Summary

Implemented a comprehensive subscription reactivation feature that allows staff to reactivate subscriptions that were previously unsubscribed using the `book_unsubscription` method. The feature includes a confirmation screen, complete data preservation in Activity metadata, failproof data recovery, and a new Activity detail view for auditing. Additionally, enhanced the Activity model with a metadata JSONField for structured data storage and improved activity type handling throughout the system.

## Features Implemented

### 1. Subscription Reactivation View

**File:** `support/views/subscriptions.py`

Created `reactivate_subscription` view with the following capabilities:

- **Validation**: Only allows reactivation of complete unsubscriptions (`unsubscription_type=1`)
- **30-Day Time Limit**: Reactivation only allowed within 30 days of `unsubscription_date` to prevent reactivating very old subscriptions
- **Prevents Invalid Reactivations**: Blocks reactivation of partial unsubscriptions and product changes (which create new subscriptions)
- **Smart Data Lookup**: Searches for unsubscription data in Activity metadata first, then falls back to legacy notes format for backward compatibility
- **Failproof Data Recovery**: If no unsubscription activity exists, automatically creates one from the current subscription state before reactivation
- **Complete Field Reversal**: Clears all unsubscription-related fields:
  - `end_date`
  - `unsubscription_reason`
  - `unsubscription_channel`
  - `unsubscription_addendum`
  - `unsubscription_type`
  - `unsubscription_date`
  - `unsubscription_manager`
  - `unsubscription_products` (ManyToMany relationship)
- **Billing Date Adjustment**: If `next_billing` is in the past, automatically adjusts it to tomorrow to prevent unwanted retroactive invoices
- **Activity Logging**: Creates reactivation Activity with metadata linking back to original unsubscription

### 2. Reactivation Confirmation Template

**File:** `support/templates/reactivate_subscription.html`

Created a comprehensive confirmation screen that displays:

- Current subscription details (contact, products, end date, reason)
- Original unsubscription information (date, manager, reason, channel, addendum)
- Link to original unsubscription Activity for full audit trail
- Clear warnings about what reactivation will do
- Information about which subscription types can be reactivated

### 3. Activity Metadata Field

**File:** `core/models.py`

Added `metadata` JSONField to the Activity model:

```python
metadata = models.JSONField(
    blank=True,
    null=True,
    verbose_name=_("Metadata"),
    help_text=_("Structured data for storing additional activity information")
)
```

**Benefits:**

- Proper structured data storage instead of JSON strings in notes field
- Supports any type of metadata (unsubscription, reactivation, etc.)
- Allows for complex queries using Django's JSONField lookups
- Maintains human-readable notes field for display purposes

**Migration:** `core/migrations/0113_add_activity_metadata.py`

### 4. Enhanced Unsubscription Data Storage

**File:** `support/views/subscriptions.py`

Updated `book_unsubscription` to store complete unsubscription data:

**Metadata stored:**

- `type`: "unsubscription"
- `subscription_id`
- `end_date`
- `unsubscription_reason`
- `unsubscription_channel`
- `unsubscription_addendum`
- `unsubscription_type`
- `unsubscription_date`
- `unsubscription_manager_id`
- `unsubscription_manager_name`
- `unsubscription_products` (list of product IDs)

**Human-readable notes:**

```text
Complete unsubscription booked for 2025-12-20.
Reason: Economic issues
Products: Digital, Print
Manager: John Doe
```

### 5. Activity Detail View

**Files:**

- `support/views/activities.py` - `ActivityDetailView`
- `support/templates/activities/activity_detail.html`
- `support/urls.py` - URL pattern: `/activity/<id>/`

Created a dedicated view for viewing activity details with:

- Complete activity information display
- **Special metadata handling:**
  - **Unsubscription metadata**: Formatted table showing subscription details, dates, manager, reason, channel, addendum
  - **Reactivation metadata**: Shows reactivation info with link to original unsubscription activity
  - **Generic metadata**: Pretty-printed JSON for other metadata types
- Warning indicator for fallback activities created during reactivation
- Breadcrumb navigation
- Links to related contacts, issues, and activities

### 6. Activity Type System Improvements

**File:** `core/choices.py`

Enhanced the activity type system to make "Internal" (N) a required system type:

```python
def get_activity_types():
    """
    Returns activity types with 'Internal' (N) always included as a required system type.

    The 'Internal' type is used for system-generated activities (unsubscriptions,
    reactivations, etc.) and must always be available regardless of custom activity types.
    """
    internal_type = ("N", _("Internal"))
    custom_types = getattr(settings, "CUSTOM_ACTIVITY_TYPES", DEFAULT_ACTIVITY_TYPES)

    if internal_type not in custom_types:
        return custom_types + (internal_type,)
    return custom_types
```

**Changes:**

- Removed "Internal" from `DEFAULT_ACTIVITY_TYPES`
- Made `get_activity_types()` always include Internal type
- Updated all system-generated activities to use `activity_type="N"` instead of `"C"`
- Added comprehensive documentation explaining why Internal is required

### 7. Activity Type Display Fix

**File:** `core/models.py`

Added `get_activity_type_display()` method to Activity model:

```python
def get_activity_type_display(self):
    """
    Returns the display name for the activity type.
    This method is needed because activity_type uses a dynamic function get_activity_types()
    instead of static choices, so Django's automatic get_FOO_display doesn't work.
    """
    activity_types = dict(get_activity_types())
    return activity_types.get(self.activity_type, "N/A")
```

**Fixed templates:**

- `support/templates/contact_detail/tabs/_activities.html`
- `support/templates/contact_detail/tabs/includes/_activity_modal.html`

### 8. Subscription Model Enhancement

**File:** `core/models.py`

Added `can_be_reactivated()` method to Subscription model:

```python
def can_be_reactivated(self):
    """
    Check if this subscription can be reactivated.

    Requirements:
    - Must have an end_date (be unsubscribed)
    - Must be a complete unsubscription (unsubscription_type == 1)
    - Must be within 30 days of unsubscription_date
    """
```

This method encapsulates all reactivation business rules in one place, making it easy to:

- Use in templates to control button visibility
- Maintain consistent validation logic across the application
- Update business rules in a single location

### 9. UI Integration

**Files:**

- `support/templates/contact_detail/tabs/includes/_subscription_card.html`
- `support/templates/contact_detail/tabs/includes/_overview_subscription_list_item.html`

Added "Reactivate" buttons that:

- Only appear when `subscription.can_be_reactivated()` returns True (includes 30-day check)
- Replace the "Unsubscribe" button when applicable
- Use green color scheme with redo icon
- Link to the reactivation confirmation screen
- Automatically hide after 30 days from unsubscription date

### 9. URL Routing

**File:** `support/urls.py`

Added new URL patterns:

- `/reactivate_subscription/<subscription_id>/` - Reactivation confirmation and processing
- `/activity/<pk>/` - Activity detail view

## Technical Details

### Data Flow

1. **Unsubscription:**
   - User books unsubscription via `book_unsubscription`
   - System creates Activity with type "N" (Internal)
   - Metadata stores all unsubscription details
   - Notes field contains human-readable summary

2. **Reactivation:**
   - User clicks "Reactivate" button on subscription
   - System validates subscription can be reactivated
   - System looks up unsubscription Activity (metadata first, then legacy format)
   - If no Activity found, creates fallback Activity from current subscription state
   - Confirmation screen shows all stored data
   - Upon confirmation:
     - All unsubscription fields cleared
     - New Activity created with reactivation metadata
     - Success message displayed

### Backward Compatibility

- **Legacy Format Support**: System can read old activities that stored JSON in notes field
- **Graceful Degradation**: If no unsubscription activity exists, system creates one before reactivation
- **Existing Activities**: All existing activities continue to work normally

### Security & Validation

- **Staff-only access**: `@staff_member_required` decorator on all views
- **Type validation**: Only complete unsubscriptions can be reactivated
- **State validation**: Subscription must have `end_date` to be reactivated
- **Confirmation required**: Two-step process prevents accidental reactivations

## Database Changes

### Migration: `core/migrations/0113_add_activity_metadata.py`

- Added `metadata` JSONField to `Activity` model
- Added `metadata` JSONField to `HistoricalActivity` model
- Updated `inactivity_reason` choices on `Subscription` and `HistoricalSubscription`
- Updated `unsubscription_type` choices on `Subscription` and `HistoricalSubscription`

## Benefits

### For Users

- **Easy Reactivation**: Simple button-click process to reactivate subscriptions
- **Clear Information**: All unsubscription details visible before reactivating
- **Audit Trail**: Complete history preserved in Activity records
- **Prevents Errors**: Validation ensures only appropriate subscriptions can be reactivated

### For Administrators

- **Data Preservation**: All unsubscription data stored in structured format
- **Activity Detail View**: Can inspect any activity's metadata and details
- **Failproof**: System handles missing data gracefully
- **Backward Compatible**: Works with existing data

### For Developers

- **Structured Metadata**: JSONField allows complex queries and proper data types
- **Extensible**: Metadata pattern can be used for other features
- **Type Safety**: Activity type system ensures Internal type always available
- **Clean Code**: Separation of structured data (metadata) and display text (notes)

## Testing Recommendations

1. **Unsubscribe and Reactivate:**
   - Create a subscription
   - Unsubscribe it completely with reason, channel, and addendum
   - Verify Activity is created with metadata
   - Reactivate the subscription
   - Verify all fields are cleared and reactivation Activity is created

2. **Validation Tests:**
   - Try to reactivate an active subscription (should fail)
   - Try to reactivate a partial unsubscription (should fail)
   - Try to reactivate a product change (should fail)

3. **Failproof Test:**
   - Create an unsubscribed subscription without an Activity
   - Attempt reactivation
   - Verify system creates fallback Activity before reactivating

4. **Activity Detail View:**
   - View unsubscription Activity - verify metadata displays correctly
   - View reactivation Activity - verify link to original unsubscription works
   - View regular Activity - verify it displays normally

5. **Activity Type Display:**
   - Check contact detail activities tab
   - Open activity modal
   - Verify activity types display correctly (especially "Internal")

## Future Improvements

### Short-term Enhancements

1. **Reactivation Reason Field:**
   - Add optional reason field for why subscription is being reactivated
   - Store in reactivation Activity metadata
   - Display in Activity detail view

2. **Bulk Reactivation:**
   - Allow selecting multiple subscriptions for reactivation
   - Useful for campaigns or special promotions
   - Include confirmation screen with list of subscriptions

3. **Reactivation Notifications:**
   - Email notification to customer when subscription is reactivated
   - Configurable email template
   - Option to include welcome back message or special offer

4. **Reactivation Statistics:**
   - Dashboard showing reactivation rates
   - Filter by reason, time period, product
   - Compare with unsubscription statistics

### Medium-term Enhancements

1. **Automated Reactivation Workflows:**
   - Allow customers to self-reactivate through customer portal
   - Configurable rules for which subscriptions can be self-reactivated
   - Approval workflow for certain cases

2. **Reactivation Campaigns:**
   - Target contacts with unsubscribed subscriptions
   - Track campaign effectiveness
   - Special pricing or offers for reactivations

3. **Enhanced Activity Metadata:**
   - Add metadata to more activity types (calls, emails, etc.)
   - Create metadata templates for common activity types
   - Allow custom metadata fields per activity type

4. **Activity Timeline View:**
   - Visual timeline of all activities for a contact
   - Filter by activity type, metadata type, date range
   - Export timeline to PDF or CSV

### Long-term Enhancements

1. **Subscription Lifecycle Analytics:**
   - Track full lifecycle: creation → active → unsubscribed → reactivated
   - Identify patterns in subscription behavior
   - Predict likelihood of reactivation
   - ML-based recommendations for retention strategies

2. **Advanced Metadata Querying:**
   - Build query interface for searching activities by metadata
   - Create saved searches and reports
   - API endpoints for metadata queries

3. **Metadata Versioning:**
   - Track changes to activity metadata over time
   - Show history of metadata updates
   - Useful for audit and compliance

4. **Integration with External Systems:**
   - Sync reactivation events with CRM systems
   - Trigger webhooks on reactivation
   - Export reactivation data to analytics platforms

## Files Modified

### Core Application

- `core/models.py` - Added metadata field, get_activity_type_display method
- `core/choices.py` - Enhanced get_activity_types to always include Internal type
- `core/migrations/0113_add_activity_metadata.py` - Database migration

### Support Application - Views

- `support/views/subscriptions.py` - Added reactivate_subscription, enhanced book_unsubscription
- `support/views/activities.py` - Added ActivityDetailView
- `support/views/__init__.py` - Added imports for new views

### Support Application - Templates

- `support/templates/reactivate_subscription.html` - New reactivation confirmation template
- `support/templates/activities/activity_detail.html` - New activity detail template
- `support/templates/contact_detail/tabs/includes/_subscription_card.html` - Added reactivate button
- `support/templates/contact_detail/tabs/includes/_overview_subscription_list_item.html` - Added reactivate button
- `support/templates/contact_detail/tabs/includes/_activity_modal.html` - Fixed activity type display

### Support Application - URLs

- `support/urls.py` - Added URL patterns for reactivation and activity detail

## Notes

- All system-generated activities now use activity_type="N" (Internal) for semantic correctness
- The metadata field pattern can be extended to other features requiring structured data storage
- Activity detail view provides a centralized place to inspect any activity's complete information
- The failproof mechanism ensures data is never lost even if original unsubscription activity is missing
