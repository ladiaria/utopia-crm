# Address Merge Functionality

**Date:** 2026-01-19
**Type:** Feature Implementation
**Component:** Logistics, Address Management
**Impact:** Data Quality, User Experience, Contact Management

## Summary

Implemented a comprehensive address merge system that allows users with proper permissions to identify and merge duplicate addresses. The feature includes intelligent similarity detection, user-friendly dropdown selection, field-by-field comparison, and automatic transfer of related objects (subscription products, issues, and scheduled tasks).

## Motivation

Duplicate addresses in the system create several problems:

1. **Data inconsistency:** Multiple addresses for the same physical location
2. **Reporting inaccuracy:** Subscription products, issues, and tasks scattered across duplicate addresses
3. **User confusion:** Staff unsure which address to use for deliveries or communications
4. **Manual cleanup difficulty:** No built-in tool to safely merge duplicate addresses

Previously, users had to:

- Manually update all related objects (subscription products, issues, tasks) to point to one address
- Delete the duplicate address through the admin interface
- Risk data loss if relationships weren't properly transferred
- Spend significant time on manual data cleanup

This workflow was error-prone, time-consuming, and required database-level knowledge.

## Implementation

### 1. Address Model Enhancement

**File:** `core/models.py`

Added `merge_other_address_into_this()` method to the Address model:

```python
def merge_other_address_into_this(
    self,
    source: "Address",
    address_1: str = None,
    address_2: str = None,
    city: str = None,
    email: str = None,
    address_type: str = None,
    notes: str = None,
    default: bool = None,
    name: str = None,
    state_id: int = None,
    country_id: int = None,
    city_fk_id: int = None,
    latitude: float = None,
    longitude: float = None,
    google_maps_url: str = None,
) -> list:
```

**Key Features:**

- **Field-by-field override:** Allows manual selection of which field values to keep
- **Related object transfer:** Automatically moves all subscription products, issues, and scheduled tasks
- **Notes merging:** Combines notes from both addresses with audit trail
- **Source deletion:** Safely deletes source address after successful merge
- **Error handling:** Returns list of errors if merge fails

**Related Objects Transferred:**

1. **SubscriptionProducts:** `source.subscriptionproduct_set.update(address=self)`
2. **Issues:** `source.issue_set.update(address=self)`
3. **ScheduledTasks:** `source.scheduledtask_set.update(address=self)`

### 2. Permission System

**File:** `core/models.py`

Added custom permission to Address model:

```python
class Meta:
    verbose_name = _("address")
    verbose_name_plural = _("addresses")
    permissions = [
        ("can_merge_addresses", _("Can merge addresses")),
    ]
```

**Access Control:**

- Only users with `core.can_merge_addresses` permission can access merge functionality
- Permission check enforced at view level with `@permission_required` decorator
- Prevents unauthorized users from merging addresses

### 3. Class-Based Views

**File:** `logistics/views.py`

Implemented two CBVs with BreadcrumbsMixin for proper navigation:

#### MergeCompareAddressesView (TemplateView)

**Dual-mode operation:**

**Mode 1 - Contact-based selection (with contact_id):**

- Shows dropdown menus with all addresses for a specific contact
- Displays descriptive address information (ID, street, city, state, country)
- JavaScript validation prevents selecting the same address twice

**Mode 2 - Direct comparison (with address_1 and address_2):**

- Displays side-by-side comparison of two addresses
- Color-coded rows (green = matching, yellow = different)
- Shows counts of related objects for each address
- Calculates similarity score using difflib.SequenceMatcher

**Similarity Detection:**

```python
# Normalize strings for comparison
addr1_normalized = address1.address_1.lower().strip()
addr2_normalized = address2.address_1.lower().strip()

# Calculate similarity ratio (0.0 to 1.0)
similarity_ratio = SequenceMatcher(None, addr1_normalized, addr2_normalized).ratio()

# Show warning if similarity is below 40%
if similarity_ratio < 0.4:
    show_similarity_warning = True
```

**Examples:**

- "Liber Arce 3177" vs "liber arse 3177" → ~90% similar (no warning)
- "Jujuy 1236" vs "Rivera 1246" → ~30% similar (warning shown)

**Breadcrumbs:**

- Step 1 (with contact): Home → Contact list → [Contact Name] → Merge addresses
- Step 2 (comparing): Home → Contact list → [Contact Name] → Merge addresses (if addresses have contact)
- Direct access: Home → Merge addresses

#### ProcessMergeAddressesView (View)

**POST handler for executing the merge:**

- Validates address IDs from form submission
- Extracts field selections from POST data
- Handles coordinate format conversion (comma to dot decimal separator)
- Executes merge via model method
- Provides success/error feedback via Django messages
- Redirects to contact detail page or merge page

**Coordinate Handling:**

```python
# Convert latitude/longitude, handling both comma and dot as decimal separator
if new_latitude and new_latitude != "":
    new_latitude = float(new_latitude.replace(',', '.'))
```

### 4. Enhanced Template

**File:** `logistics/templates/merge_compare_addresses.html`

**Step 1 - Address Selection:**

**Contact-based flow:**

- Info banner showing contact name and ID
- Two dropdown menus with descriptive address options
- JavaScript duplicate detection with warning message
- Cancel button (returns to contact detail)
- Compare button (proceeds to step 2)

**Manual ID flow:**

- Number inputs for address IDs
- Cancel button (returns to home)
- Compare button (proceeds to step 2)

**Step 2 - Comparison & Merge:**

**Similarity Warning:**

```html
{% if show_similarity_warning %}
  <div class="alert alert-warning alert-dismissible fade show" role="alert">
    <h5><i class="fas fa-exclamation-triangle"></i> {% trans "Warning: Addresses appear to be very different" %}</h5>
    <p class="mb-0">
      {% trans "The street addresses you are merging appear to be significantly different" %} ({{ similarity_percentage }}% {% trans "similar" %}).
      {% trans "Please verify you have selected the correct addresses before proceeding. Merging unrelated addresses cannot be undone." %}
    </p>
  </div>
{% endif %}
```

**Comparison Table:**

- **Color-coded rows:** Green for matching values, yellow for differences
- **Field labels with helper text:** Descriptive explanations for each field
- **Dropdown selectors:** Choose which value to keep for each field
- **Related object counts:** Shows subscription products, issues, and tasks for each address
- **Special handling:** Coordinates, notes, boolean fields have custom UI

**Helper Text Examples:**

- Address 1: "Street address"
- Address 2: "Apartment, suite, etc."
- Name: "Reference name for this address. It can reference the person or the address itself."
- State: "State/Province/Department"
- Coordinates: "GPS coordinates (lat, long)"

**Action Buttons:**

- Cancel button (returns to contact detail or merge page)
- Execute merge button (red, danger styling)

**Information Section:**

- Important information alert at bottom
- Explains merge behavior and consequences
- Warns that action cannot be undone

### 5. URL Configuration

**File:** `logistics/urls.py`

Added two URL patterns:

```python
path("merge_addresses/", MergeCompareAddressesView.as_view(), name="merge_compare_addresses"),
path("process_merge_addresses/", ProcessMergeAddressesView.as_view(), name="process_merge_addresses"),
```

### 6. Contact Overview Integration

**File:** `support/templates/contact_detail/tabs/_overview.html`

Added merge button in addresses section:

```html
<div class="d-flex justify-content-between align-items-center mb-2">
  <h6 class="text-muted mb-0"><i class="fas fa-map-marker-alt"></i> {% trans "Addresses" %}</h6>
  {% if addresses|length > 1 and perms.core.can_merge_addresses %}
    <a href="{% url 'merge_compare_addresses' %}?contact_id={{ contact.id }}" class="btn btn-xs btn-warning" title="{% trans "Merge duplicate addresses" %}">
      <i class="fas fa-compress-arrows-alt"></i> {% trans "Merge" %}
    </a>
  {% endif %}
</div>
```

**Button Behavior:**

- Only appears when contact has 2+ addresses
- Only visible to users with `can_merge_addresses` permission
- Passes contact_id to trigger dropdown selection mode
- Warning color (yellow) indicates potentially destructive action

## Technical Details

### Similarity Algorithm

Uses Python's built-in `difflib.SequenceMatcher`:

```python
from difflib import SequenceMatcher

similarity_ratio = SequenceMatcher(None, addr1_normalized, addr2_normalized).ratio()
```

**Threshold:** 40% similarity

- Below 40%: Warning displayed
- Above 40%: No warning (likely typos or minor differences)

**Normalization:**

- Convert to lowercase
- Strip whitespace
- Compare character sequences

### Field Override Logic

All address fields can be individually selected:

- **Text fields:** address_1, address_2, city, email, name, google_maps_url
- **Foreign keys:** state_id, country_id, city_fk_id
- **Coordinates:** latitude, longitude (with comma/dot handling)
- **Boolean:** default
- **Choice field:** address_type
- **Text area:** notes (with merge option)

### Notes Merging

Three options for notes:

1. **Automatic merge:** Combines both sets of notes with audit trail
2. **Keep address 1 notes:** Uses only first address notes
3. **Keep address 2 notes:** Uses only second address notes

**Automatic merge format:**

```text
Combined from [source_id] at [date]
[target notes]

Notes imported from [source_id]
[source notes]
```

### Related Object Transfer

**Database operations:**

```python
# Transfer subscription products
source.subscriptionproduct_set.update(address=self)

# Transfer issues
source.issue_set.update(address=self)

# Transfer scheduled tasks
source.scheduledtask_set.update(address=self)
```

**Atomic operation:**

- All transfers happen in single transaction
- If any fails, entire merge rolls back
- Source address only deleted after successful transfer

## Benefits

### 1. Data Quality Improvement

- **Eliminate duplicates:** Clean up duplicate address records
- **Consolidate relationships:** All related objects in one place
- **Accurate reporting:** Correct counts for subscription products, issues, and tasks
- **Consistent data:** Single source of truth for each physical address

### 2. User Experience

- **Intuitive interface:** Dropdown selection with descriptive options
- **Visual feedback:** Color-coded comparison table
- **Safety features:** Similarity warnings, duplicate prevention
- **Clear navigation:** Breadcrumbs and cancel buttons at every step
- **Helpful guidance:** Field descriptions and instructions

### 3. Workflow Efficiency

- **One-click access:** Merge button in contact overview
- **Guided process:** Two-step workflow with clear progression
- **Batch operations:** Select fields to keep in single action
- **Automatic cleanup:** Related objects transferred automatically

### 4. Safety & Reliability

- **Permission-based:** Only authorized users can merge
- **Similarity detection:** Warns about very different addresses
- **Duplicate prevention:** JavaScript validation in selection
- **Audit trail:** Notes include merge history
- **Error handling:** Comprehensive error reporting

## Usage

### For Users with Permission

**Access via Contact Overview:**

1. Navigate to contact detail page
2. Scroll to Addresses section
3. Click "Merge" button (appears when contact has 2+ addresses)
4. Select two addresses from dropdowns
5. Click "Compare addresses"
6. Review side-by-side comparison
7. Select which values to keep for each field
8. Choose which address to keep
9. Click "Execute merge"

**Direct Access:**

1. Navigate to `/logistics/merge_addresses/`
2. Enter two address IDs manually
3. Click "Compare addresses"
4. Follow steps 6-9 above

### Similarity Warning Interpretation

**High similarity (>60%):** Likely typos or minor differences

- Example: "Liber Arce 3177" vs "liber arse 3177"
- Safe to proceed with merge

**Medium similarity (40-60%):** Review carefully

- May be same location with different formatting
- Verify before proceeding

**Low similarity (<40%):** Warning displayed

- Example: "Jujuy 1236" vs "Rivera 1246"
- Likely different addresses
- Double-check before merging

### Field Selection Strategy

**Recommended approach:**

1. **Review color coding:** Green = same, yellow = different
2. **Check related object counts:** Consider which address has more data
3. **Verify coordinates:** Ensure correct geolocation is kept
4. **Merge notes:** Use automatic merge to preserve all information
5. **Select primary address:** Choose address with more complete data

## Testing

### Verification Steps

1. **Test permission system:**
   - Log in as user without permission
   - Verify merge button doesn't appear
   - Verify direct URL access is denied

2. **Test contact-based flow:**
   - Navigate to contact with 2+ addresses
   - Click merge button
   - Verify dropdowns show all addresses
   - Try selecting same address twice
   - Verify warning appears and button disables

3. **Test similarity detection:**
   - Compare very similar addresses
   - Verify no warning appears
   - Compare very different addresses
   - Verify warning appears with percentage

4. **Test field selection:**
   - Select different values for each field
   - Execute merge
   - Verify correct values were kept

5. **Test related object transfer:**
   - Note subscription product counts before merge
   - Execute merge
   - Verify all products transferred to target address
   - Repeat for issues and scheduled tasks

6. **Test coordinate handling:**
   - Merge addresses with comma decimal separators
   - Verify coordinates saved correctly
   - Check georef_point is updated

7. **Test breadcrumbs:**
   - Verify breadcrumbs show contact context
   - Test navigation via breadcrumb links
   - Verify breadcrumbs update between steps

8. **Test cancel buttons:**
   - Click cancel in step 1
   - Verify returns to contact detail
   - Click cancel in step 2
   - Verify returns to appropriate page

## Files Modified

### Core Models

- `core/models.py` - Added merge_other_address_into_this() method and can_merge_addresses permission

### Logistics Views

- `logistics/views.py` - Added MergeCompareAddressesView and ProcessMergeAddressesView with BreadcrumbsMixin

### Logistics Templates

- `logistics/templates/merge_compare_addresses.html` - New template for address merge UI

### Logistics URLs

- `logistics/urls.py` - Added URL patterns for merge views

### Support Templates

- `support/templates/contact_detail/tabs/_overview.html` - Added merge button to addresses section

## Database Impact

**No schema changes required** - uses existing Address model fields and relationships:

- Address model already has all necessary fields
- Related models (SubscriptionProduct, Issue, ScheduledTask) already have ForeignKey to Address
- Permission added via Meta.permissions (creates database entry on migration)

**Migration needed:**

```bash
python manage.py makemigrations
python manage.py migrate
```

This creates the `can_merge_addresses` permission in the database.

## Backward Compatibility

- All existing address functionality preserved
- No breaking changes to Address model API
- Merge functionality is opt-in (requires permission)
- Existing addresses unaffected
- Related object relationships unchanged

## Security Considerations

1. **Permission-based access:** Only users with `can_merge_addresses` can access
2. **CSRF protection:** All forms include CSRF tokens
3. **Input validation:** Address IDs validated before processing
4. **Error handling:** Graceful failure with user-friendly messages
5. **Audit trail:** Merge history recorded in notes

## Future Enhancements

Potential improvements for future iterations:

1. **Bulk merge:** Merge multiple address pairs in single operation
2. **Auto-detection:** Suggest potential duplicates based on similarity
3. **Merge history:** Dedicated table to track all merges
4. **Undo functionality:** Ability to reverse a merge within time window
5. **Advanced similarity:** Use address parsing libraries for better detection
6. **Merge preview:** Show what will happen before executing
7. **Batch cleanup:** Find and merge all duplicates for a contact
8. **API endpoint:** Programmatic access to merge functionality

## Notes

- Similarity detection uses difflib.SequenceMatcher (built-in Python library)
- Coordinate conversion handles both comma and dot decimal separators
- Template uses Bootstrap 4 for responsive design
- All text is translatable using Django's i18n system
- BreadcrumbsMixin provides consistent navigation across the application
- Cancel buttons intelligently redirect based on context

## Related Features

- Contact management and detail views
- Address georeferencing system
- Subscription product management
- Issue tracking system
- Scheduled task management
- Permission system and user roles
