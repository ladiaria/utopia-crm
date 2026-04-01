# Subscription Route Change with Special Route Automation

**Date:** 2026-01-26
**Type:** Feature Enhancement & Automation
**Component:** Logistics Management System
**Impact:** Workflow Efficiency, Issue Tracking, User Experience

## Summary

Comprehensive implementation of a subscription-level route change interface with automatic issue creation for special routes (50-55). This feature allows logistics operators to efficiently change routes for all products in a single subscription while automatically generating logistics issues when products are assigned to special routes that may not be billed.

## Motivation

The logistics team needed a more efficient way to manage route changes for subscriptions:

1. **Subscription-Level Management:** Existing `change_route` view only worked at the route level (all subscriptions on a route), not for individual subscriptions
2. **Manual Issue Creation:** When products were moved to special routes (50-55), operators had to manually create logistics issues to track non-delivery
3. **Poor Discoverability:** Route change functionality wasn't easily accessible from the contact detail page
4. **Limited Search:** Large route lists made it difficult to quickly find specific routes
5. **Missing Automation:** No automatic tracking when products were assigned to special routes

## Key Features Implemented

### 1. Utility Function for Automatic Issue Creation

**File:** `logistics/utils.py`

**Purpose:**
Automatically creates logistics issues when subscription products are assigned to special routes (50-55).

**Implementation:**

```python
def create_issue_for_special_route(subscription, route_number, user=None):
    """
    Creates an Issue when a subscription product is changed to a special route (50-55).

    Args:
        subscription: The Subscription object
        route_number: The route number that was assigned
        user: The user who made the change (optional, will be set as manager)

    Returns:
        Issue object if created, None otherwise
    """
    # Only create issue for special routes (50-55 inclusive)
    if route_number not in range(50, 56):
        return None

    # Get subcategory and status from settings for flexibility
    subcategory_slug = getattr(settings, 'ISSUE_SUBCATEGORY_NOT_DELIVERED', 'not-delivered')
    status_slug = getattr(settings, 'ISSUE_STATUS_UNASSIGNED', 'unassigned')

    # Create issue with logistics category
    issue = Issue.objects.create(
        contact=subscription.contact,
        subscription=subscription,
        category="L",  # Logistics category
        sub_category=subcategory,
        status=status,
        manager=user,
        assigned_to=None,  # Not assigned to anyone
        notes=_("Generated automatically for change of route to special route (route {})").format(route_number),
    )

    return issue
```

**Key Features:**

- Uses settings constants (`ISSUE_SUBCATEGORY_NOT_DELIVERED`, `ISSUE_STATUS_UNASSIGNED`) for flexibility across installations
- Creates unassigned logistics issues for tracking
- Records the user who made the change as the manager
- Auto-generates descriptive notes with route number
- Returns None if route is not special (50-55)

### 2. Subscription Route Change View

**File:** `logistics/views.py`

**View:** `change_subscription_routes(request, subscription_id)`

**Purpose:**
Dedicated view for changing routes on all products within a single subscription.

**Features:**

- Displays all subscription products with current routes
- Allows bulk route changes for all products in one form submission
- Supports label messages and special instructions per product
- Automatically creates issues for special routes (50-55)
- Shows warning messages when issues are created
- Redirects to contact detail page after saving

**Implementation Highlights:**

```python
@login_required
def change_subscription_routes(request, subscription_id):
    subscription = get_object_or_404(Subscription, pk=subscription_id)

    if request.POST:
        issues_created = []
        for name, value in list(request.POST.items()):
            if name.startswith("sp-") and value:
                sp = SubscriptionProduct.objects.get(pk=sp_id)
                new_route = Route.objects.get(number=int(value))

                if sp.route != new_route:
                    sp.route = new_route
                    sp.order = None
                    sp.save()

                    # Create issue if it's a special route (50-55)
                    issue = create_issue_for_special_route(subscription, new_route.number, request.user)
                    if issue:
                        issues_created.append(new_route.number)

        # Show warning if issues were created
        if issues_created:
            messages.warning(request, _("Routes updated. Issues created for special routes: {}"))
```

**User Experience:**

- Clear subscription information display (type, status, dates)
- Warning about special route behavior
- Table showing current routes with dropdown selectors
- Separate sections for label messages and special instructions
- Visual feedback for special route selections

### 3. Enhanced Existing Route Change View

**File:** `logistics/views.py`

**View:** `change_route(request, route_id)`

**Enhancement:**
Updated the existing route-level change view to also use the utility function for automatic issue creation.

**Changes:**

- Added issue creation tracking with `issues_created` list
- Calls `create_issue_for_special_route()` when routes are changed
- Displays warning message listing which special routes created issues
- Maintains all existing functionality

### 4. Modern Template with Select2 Integration

**File:** `logistics/templates/change_subscription_routes.html`

**Features:**

**Visual Design:**

- Clean card-based layout with prominent warnings
- Subscription information summary
- Responsive table with clear column headers
- Color-coded special route indicators

**Select2 Integration:**

- Uses local admin-lte Select2 plugin (not CDN)
- Type-to-search functionality for quick route finding
- Custom formatting for special routes (50-55):
  - Warning triangle icon (⚠️) in dropdown
  - Bold text with warning color
  - Visual distinction from regular routes

**Real-time Feedback:**

- JavaScript highlights rows when special routes are selected
- Inline alerts: "Special route - Issue will be created"
- Table row turns yellow when special route is chosen
- Maintains highlighting on page load for pre-selected routes

**Implementation:**

```javascript
$('select[name^="sp-"]').select2({
  theme: 'bootstrap4',
  width: '100%',
  placeholder: "{% trans 'Select route' %}",
  allowClear: true,
  templateResult: formatRouteOption,
  templateSelection: formatRouteSelection
});

function formatRouteOption(route) {
  var routeNumber = parseInt($(route.element).val());
  var $route = $('<span>' + route.text + '</span>');

  if (routeNumber >= 50 && routeNumber <= 55) {
    $route.prepend('<i class="fas fa-exclamation-triangle text-warning mr-1"></i>');
    $route.addClass('font-weight-bold text-warning');
  }

  return $route;
}
```

### 5. URL Configuration

**File:** `logistics/urls.py`

**Added Route:**

```python
re_path(r'^change_subscription_routes/(\d+)/$', change_subscription_routes, name='change_subscription_routes'),
```

**Pattern:** `/logistics/change_subscription_routes/<subscription_id>/`

### 6. UI Integration in Contact Detail

**File:** `support/templates/contact_detail/tabs/includes/_subscription_card.html`

**Enhancement:**
Added "Change Routes" button to subscription card footer.

**Features:**

- Visible to Support, Managers, and Logistics groups
- Uses outline-primary styling with route icon
- Positioned alongside other subscription actions
- Direct link to route change interface

**Implementation:**

```html
{% if request.user|in_group:"Support" or request.user|in_group:"Managers" or request.user|in_group:"Logistics" %}
  <a href="{% url "change_subscription_routes" subscription.id %}"
     class="btn btn-sm btn-outline-primary mb-1">
    <i class="fas fa-route"></i> {% trans "Change Routes" %}
  </a>
{% endif %}
```

## Settings Configuration

**File:** `settings.py`

**New Constants:**

```python
# Issue subcategory for special route automation
ISSUE_SUBCATEGORY_NOT_DELIVERED = "not-delivered"

# Issue status for unassigned issues
ISSUE_STATUS_UNASSIGNED = "unassigned"
```

**Purpose:**

- Allows local settings to override with Spanish versions
- Provides flexibility for different installations
- Maintains consistency across the application

## Technical Implementation Details

### Database Queries Optimization

**Subscription Products Query:**

```python
subscription_products = (
    SubscriptionProduct.objects.filter(subscription=subscription)
    .exclude(product__digital=True)
    .select_related("product", "address", "route")
    .order_by("product__name")
)
```

**Benefits:**

- Uses `select_related()` to avoid N+1 queries
- Excludes digital products (no physical delivery)
- Orders by product name for consistent display

### Form Processing

**Route Change Logic:**

```python
if sp.route != new_route:  # Only update if route actually changed
    sp.route = new_route
    sp.order = None  # Reset order when route changes
    sp.special_instructions = request.POST.get("instructions-{}".format(sp_id), None)
    sp.label_message = request.POST.get("message-{}".format(sp_id), None)
    sp.save()
```

**Benefits:**

- Checks for actual changes before saving
- Resets order to None when route changes (will be reordered later)
- Preserves special instructions and label messages
- Efficient database updates

### Error Handling

**Graceful Degradation:**

- Returns None if subcategory doesn't exist (doesn't break the route change)
- Returns None if status doesn't exist (doesn't break the route change)
- Shows error messages for invalid routes
- Continues processing other products if one fails

## User Experience Improvements

### Before This Change

**Route Changes:**

- Had to use route-level view (change all subscriptions on a route)
- No easy access from contact detail page
- Manual issue creation for special routes
- Difficult to find specific routes in long lists

**Issue Tracking:**

- Manual creation of logistics issues
- Inconsistent issue creation (often forgotten)
- No automatic linking to subscription

### After This Change

**Route Changes:**

- ✅ Subscription-level route changes from contact detail
- ✅ One-click access via "Change Routes" button
- ✅ Automatic issue creation for special routes
- ✅ Type-to-search route selection with Select2
- ✅ Visual warnings for special routes
- ✅ Real-time feedback during selection

**Issue Tracking:**

- ✅ Automatic issue creation for special routes (50-55)
- ✅ Consistent tracking with proper categorization
- ✅ Automatic linking to subscription and contact
- ✅ Clear audit trail (user recorded as manager)

## Workflow Example

### Typical Use Case

1. **Operator accesses contact detail page**
   - Views subscription with products on various routes

2. **Clicks "Change Routes" button**
   - Opens dedicated route change interface
   - Sees all subscription products with current routes

3. **Changes route for a product**
   - Types route number in Select2 dropdown (e.g., "51")
   - Sees warning icon and yellow highlight
   - Alert appears: "Special route - Issue will be created"

4. **Submits form**
   - Routes are updated
   - Issue automatically created for route 51
   - Warning message: "Routes updated. Issues created for special routes: 51"
   - Redirected to contact detail page

5. **Issue is tracked**
   - Logistics issue appears in issue list
   - Category: Logistics
   - Subcategory: not-delivered
   - Status: unassigned
   - Notes: "Generated automatically for change of route to special route (route 51)"

## Benefits

### Operational Efficiency

1. **Time Savings:**
   - No manual issue creation for special routes
   - Quick route lookup with type-to-search
   - Bulk changes for all products in subscription

2. **Error Reduction:**
   - Automatic issue creation prevents forgotten tracking
   - Visual warnings prevent accidental special route assignments
   - Consistent issue categorization

3. **Better Tracking:**
   - All special route changes automatically tracked
   - Clear audit trail with user attribution
   - Linked to subscription for context

### User Experience

1. **Discoverability:**
   - Prominent button in subscription card
   - Clear navigation path
   - Intuitive interface

2. **Visual Feedback:**
   - Warning icons for special routes
   - Color-coded selections
   - Real-time alerts

3. **Efficiency:**
   - Type-to-search for quick route finding
   - Bulk updates in single form
   - Direct access from contact detail

## Files Modified

### New Files

- `logistics/utils.py` - Utility function for issue creation
- `logistics/templates/change_subscription_routes.html` - Route change interface

### Modified Files

- `logistics/views.py` - Added `change_subscription_routes` view, enhanced `change_route`
- `logistics/urls.py` - Added URL pattern for new view
- `support/templates/contact_detail/tabs/includes/_subscription_card.html` - Added button
- `settings.py` - Added configuration constants

## Testing Recommendations

### Manual Testing

1. **Route Change Functionality:**
   - Change routes for subscription products
   - Verify routes are updated correctly
   - Check order is reset to None

2. **Special Route Automation:**
   - Change route to 50-55 range
   - Verify issue is created automatically
   - Check issue has correct category, subcategory, status
   - Verify notes contain route number

3. **Select2 Integration:**
   - Type route numbers to search
   - Verify dropdown filters correctly
   - Check special routes show warning icons
   - Test selection and clearing

4. **Visual Feedback:**
   - Select special route (50-55)
   - Verify row highlights yellow
   - Check alert message appears
   - Verify warning persists on page load

5. **Permissions:**
   - Test with Support, Managers, Logistics groups
   - Verify button appears for authorized users
   - Test with unauthorized users (button should not appear)

### Edge Cases

1. **No Route Change:**
   - Select same route as current
   - Verify no unnecessary updates

2. **Missing Subcategory/Status:**
   - Test with missing database records
   - Verify graceful degradation (no error)

3. **Multiple Special Routes:**
   - Change multiple products to different special routes
   - Verify all issues are created
   - Check warning message lists all routes

4. **Digital Products:**
   - Verify digital products are excluded from interface

## Future Enhancements

### Potential Improvements

1. **Bulk Route Assignment:**
   - "Apply to all" button to set same route for all products
   - Route templates for common configurations

2. **Route History:**
   - Track route change history
   - Show previous routes in interface

3. **Advanced Filtering:**
   - Filter products by current route
   - Show only products needing route changes

4. **Issue Preview:**
   - Show preview of issue that will be created
   - Allow customization before creation

5. **Route Recommendations:**
   - Suggest routes based on address
   - Show nearby routes for consideration

## Migration Notes

### For Existing Installations

1. **Settings Configuration:**
   - Add `ISSUE_SUBCATEGORY_NOT_DELIVERED` to local_settings.py
   - Add `ISSUE_STATUS_UNASSIGNED` to local_settings.py
   - Override with Spanish versions if needed

2. **Database Requirements:**
   - Ensure "not-delivered" (or localized) subcategory exists
   - Ensure "unassigned" (or localized) status exists
   - No migrations required

3. **Permissions:**
   - Verify Support, Managers, Logistics groups exist
   - Adjust group checks in template if needed

## Conclusion

This implementation provides a comprehensive solution for subscription-level route management with intelligent automation for special route tracking. The combination of efficient UI, automatic issue creation, and clear visual feedback significantly improves the logistics workflow while reducing manual work and potential errors.

The use of settings constants ensures flexibility across different installations, and the Select2 integration provides a modern, user-friendly interface for quick route selection. The automatic issue creation ensures that all special route assignments are properly tracked without requiring manual intervention from operators.
