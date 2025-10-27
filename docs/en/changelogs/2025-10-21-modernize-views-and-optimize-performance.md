# 2025-10-21: Modernize Views and Optimize Performance

## Summary

Major architectural improvements to the support module, converting function-based views to class-based views, implementing dynamic filtering, optimizing database queries, and enhancing the campaign status system.

## Key Improvements

### 1. Issue Management Views Modernization

#### IssueListView - Converted to FilterView with Dynamic Filtering

**Problem:** Function-based view with static subcategory filtering.

**Solution:** Converted to class-based `FilterView` with dynamic subcategory filtering similar to ActivityTopic/Response pattern.

**File:** `support/views/all_views.py`

**Key Features:**

- Class-based architecture with `BreadcrumbsMixin`
- Dynamic subcategory filtering based on selected category
- Client-side filtering (no AJAX required)
- Category-subcategory mapping passed as JSON to template
- Shows category-specific + general subcategories
- Maintained all filtering and CSV export functionality

**Template:** `support/templates/list_issues.html`

**Changes:**

- Added JavaScript for dynamic subcategory filtering
- Updated to use `filter.form` instead of `issues_filter.form`
- Updated pagination to use `page_obj` (ListView standard)
- Removed ID column, added "View" button with eye icon

**URL:** `support/urls.py` - Updated to use `IssueListView.as_view()`

#### IssueDetailView - Converted to UpdateView

**Problem:** `DetailView` with manual POST handling for edit functionality.

**Solution:** Converted to `UpdateView` for better architectural alignment with dual purpose (display + edit).

**File:** `support/views/all_views.py`

**Benefits:**

- Built-in form handling (validation, saving, error handling)
- Dynamic form classes via `get_form_class()` (InvoicingIssueChangeForm vs IssueChangeForm)
- Cleaner code - eliminated ~20 lines of manual form processing
- Proper redirect handling via `get_success_url()`
- Breadcrumbs navigation: Home > Contacts > [Contact Name] > Issue #[ID]

**Architecture:**

```python
# Dynamic form selection based on issue category
def get_form_class(self):
    if self.object.category in ["I", "M"]:
        return InvoicingIssueChangeForm
    return IssueChangeForm

# Subcategory filtering in get_form()
def get_form(self, form_class=None):
    form = super().get_form(form_class)
    if self.object.category in ["I", "M"]:
        form.fields['subcategory'].queryset = IssueSubcategory.objects.filter(...)
    return form
```

### 2. Campaign Status System Modernization

**Problem:** Mixed use of legacy tuple choices and modern IntegerChoices across models.

**Solution:** Implemented shared `CAMPAIGN_STATUS` IntegerChoices in `core/choices.py`.

**Files Modified:**

- `core/choices.py` - Added centralized `CAMPAIGN_STATUS` IntegerChoices
- `core/models.py` - Updated `ContactCampaignStatus` to use shared choices
- `support/models.py` - Updated `SellerConsoleAction` to use shared choices
- `support/views/seller_console.py` - Updated `process_activity_result()` method

**Key Features:**

- Single source of truth for campaign status definitions
- Type safety with IntegerChoices
- Maintains existing integer values (backward compatible)
- Tracks `last_console_action` for detailed analytics
- Uses `console_action.campaign_status` from database instead of hardcoded mapping

**Status Values:**

```python
class CAMPAIGN_STATUS(IntegerChoices):
    NOT_YET_CONTACTED = 1, _("Not yet contacted")
    CONTACTED = 2, _("Contacted")
    CALLED_COULD_NOT_CONTACT = 3, _("Called - Could not contact")
    # ... etc
```

**Management Command:** `populate_seller_console_actions`

- Creates/updates actions with appropriate campaign status
- Supports both Spanish and English (`--lang=ES|EN`)
- Uses hardcoded English slugs for production compatibility
- Automatic slug generation removed in favor of explicit control

**Architectural Decision:**

- **English slugs** (internal identifiers): `schedule`, `call-later`, `not-interested`
- **Spanish display names** (user-facing): "Agendar", "Llamar más tarde", "No interesado"
- **Template compatibility**: `data-result` attributes match database slugs
- **Production compatible**: Matches existing slugs in production databases

### 3. SellerConsoleView Simplification

**Problem:** Duplicate `SellerConsoleAction` lookup code with inconsistent error handling.

**Solution:** Created unified helper method for all action lookups.

**File:** `support/views/seller_console.py`

**Implementation:**

```python
def get_seller_console_action(self, result_slug, required=True):
    """Get SellerConsoleAction by slug with unified error handling"""
    try:
        return SellerConsoleAction.objects.get(slug=result_slug, is_active=True)
    except SellerConsoleAction.DoesNotExist:
        if required:
            messages.error(self.request, _("Invalid action: {action}"))
            return None
        else:
            messages.warning(self.request, _("Invalid action slug: {action}"))
            return None
```

**Benefits:**

- DRY principle - single source of truth
- Consistent filtering by `is_active=True`
- Unified error handling and messaging
- Flexible `required` parameter for different scenarios
- Eliminated variable naming inconsistencies

### 4. Contact Assignment - Round-Robin Distribution

**Problem:** Sequential assignment gave all priority contacts to first seller.

**Solution:** Implemented round-robin distribution algorithm in `AssignSellerView`.

**File:** `support/views/seller_console.py`

**Behavior Change:**

- **Old:** Assigns all contacts for first seller, then second, etc. (50, 50, 50)
- **New:** Assigns contacts one-by-one in rotation (1, 1, 1 repeated 50 times)

**Implementation:**

```python
def _create_round_robin_assignment_queue(self, sellers, contacts_per_seller):
    """
    Creates a round-robin assignment queue ensuring equal distribution
    of high-priority contacts when prioritization is enabled.
    """
    assignment_queue = []
    for i in range(contacts_per_seller):
        for seller in sellers:
            assignment_queue.append(seller)
    return assignment_queue
```

**Benefits:**

- Equal distribution of high-priority contacts
- Fair workload distribution when prioritization by end date is enabled

### 5. Performance Optimization - ContactListView CSV Export

**Problem:** N+1 queries causing production timeouts on large contact exports.

**Solution:** Implemented bulk data prefetching and database annotations.

**File:** `support/views/contacts.py`

**Optimizations:**

1. **Bulk Data Prefetching:**
   - Added `get_optimized_queryset_for_csv()` method
   - Prefetches active subscriptions with products and addresses
   - Prefetches recent activities

2. **Database Annotations:**
   - `has_active_subs` annotation using `Exists()`
   - `last_activity_date` annotation using `Max()`
   - Eliminates expensive method calls in CSV loop

3. **Memory Efficiency:**
   - Uses `iterator(chunk_size=1000)` for large datasets
   - Prevents memory issues with large exports

**Performance Impact:**

```python
# Before: N+1 queries
for contact in self.get_queryset().all():
    contact.get_active_subscriptionproducts()  # DB query per contact
    contact.has_active_subscription()          # DB query per contact
    contact.last_activity()                    # DB query per contact

# After: Bulk prefetching
contacts = self.get_optimized_queryset_for_csv()
for contact in contacts.iterator(chunk_size=1000):
    contact.active_subscriptions              # Prefetched data
    contact.has_active_subs                   # Annotated field
    contact.last_activity_date                # Annotated field
```

**Expected Results:**

- Eliminates 3-4 database queries per contact
- Significantly reduces export time
- Prevents CloudFlare/nginx timeouts

### 6. Dynamic Activity Response Filtering

**Problem:** ActivityResponse dropdown showed all responses regardless of selected ActivityTopic.

**Solution:** Implemented client-side filtering without AJAX.

**File:** `support/views/activities.py` (ActivityCreateView)

**Implementation:**

- Backend passes topic-response relationships as JSON
- JavaScript filters response dropdown based on topic selection
- Shows topic-specific + general responses (marked as "General")
- All data loaded on page load, filtered client-side

**Benefits:**

- Real-time filtering without server requests
- User-friendly with clear visual feedback
- Handles responses with and without topics gracefully

### 7. CSV Delimiter Detection Utility

**Problem:** Regional differences in CSV formats (Colombia uses semicolon, Uruguay/US uses comma).

**Solution:** Created reusable `detect_csv_delimiter()` function.

**File:** `core/utils.py`

**Implementation:**

- Uses Python's `csv.Sniffer` for intelligent detection
- Falls back to character counting if Sniffer fails
- Analyzes first 1024 characters for performance
- Automatically resets file pointer after analysis

**Usage:**

```python
from core.utils import detect_csv_delimiter

delimiter = detect_csv_delimiter(file_content)
csv_reader = csv.DictReader(file_content, delimiter=delimiter)
```

**Applied In:**

- `CheckForExistingContactsView` - Email-only contact matching
- Downloadable CSV template feature
- Enhanced user experience with delimiter detection feedback

## Impact

### Backward Compatibility

- ✅ All changes maintain existing functionality
- ✅ Database schema unchanged (same integer values for campaign status)
- ✅ URL patterns preserved with backward compatibility aliases
- ✅ Template updates maintain all existing features

### Performance Improvements

- ✅ Eliminated N+1 queries in CSV exports
- ✅ Client-side filtering reduces server load
- ✅ Bulk prefetching for large datasets
- ✅ Memory-efficient iterators for exports

### Code Quality

- ✅ Modern Django best practices (class-based views, IntegerChoices)
- ✅ DRY principle applied throughout
- ✅ Consistent error handling and messaging
- ✅ Type safety with IntegerChoices
- ✅ Reusable utilities (CSV delimiter detection)

### User Experience

- ✅ Dynamic filtering for better usability
- ✅ Breadcrumbs navigation for clear context
- ✅ Fair contact distribution with round-robin
- ✅ Faster CSV exports without timeouts
- ✅ Regional CSV format support

## Files Modified

### Views

1. `support/views/all_views.py` - IssueListView and IssueDetailView conversions
2. `support/views/seller_console.py` - SellerConsoleView simplification, round-robin assignment
3. `support/views/contacts.py` - ContactListView CSV export optimization, CheckForExistingContactsView enhancements
4. `support/views/activities.py` - ActivityCreateView dynamic filtering

### Models

1. `core/choices.py` - Added CAMPAIGN_STATUS IntegerChoices
2. `core/models.py` - Updated ContactCampaignStatus
3. `support/models.py` - Updated SellerConsoleAction

### Templates

1. `support/templates/list_issues.html` - Dynamic subcategory filtering, UI improvements
2. `support/templates/issue_detail.html` - UpdateView compatibility
3. `support/templates/activity_create.html` - Dynamic response filtering

### Utilities

1. `core/utils.py` - Added detect_csv_delimiter() function

### URLs

1. `support/urls.py` - Updated to use class-based views

### Management Commands

1. `support/management/commands/populate_seller_console_actions.py` - Enhanced with hardcoded English slugs

## Testing Recommendations

1. **Issue Management:**
   - Test dynamic subcategory filtering in issue list
   - Verify issue detail view form submissions
   - Test CSV export functionality

2. **Campaign Status:**
   - Run `python manage.py populate_seller_console_actions --lang=ES`
   - Verify campaign status tracking in seller console
   - Test activity result processing

3. **Contact Assignment:**
   - Test round-robin distribution with multiple sellers
   - Verify priority contact distribution

4. **CSV Export:**
   - Test large contact exports (1000+ contacts)
   - Monitor database query count
   - Verify export completion without timeouts

5. **CSV Import:**
   - Test with both comma and semicolon delimited files
   - Verify delimiter detection feedback
   - Test template download feature

## Migration Notes

- No database migrations required
- Existing data fully compatible
- Management command should be run to update SellerConsoleAction records:

  ```bash
  python manage.py populate_seller_console_actions --lang=ES
  ```

- Clear browser cache if JavaScript filtering doesn't work immediately
