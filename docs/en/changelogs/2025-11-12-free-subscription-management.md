# Free Subscription Management System

**Date:** 2025-11-12
**Type:** Feature Enhancement
**Component:** Subscription Management
**Impact:** Manager Workflow, Free Subscription Handling

## Summary

Implemented a complete free subscription management system with dedicated views, forms, and templates for creating and updating free subscriptions. This feature provides managers with a streamlined interface to manage free subscriptions independently from the campaign-based promotional subscription workflow used by sellers.

## Motivation

Previously, the system lacked a dedicated interface for managing free subscriptions (type "F"). Managers needed to use the admin interface or adapt promotional subscription workflows, which were designed for seller campaigns and included unnecessary campaign-related logic. This created several issues:

1. **No Dedicated Workflow:** Free subscriptions required using admin interface or promotional forms not designed for this purpose
2. **Missing Required Field:** The `free_subscription_requested_by` field (HR, Advertisement, Management) had no UI for setting it
3. **Permission Confusion:** No clear permission-based access control for free subscription management
4. **Campaign Logic Overhead:** Promotional views included campaign, seller, and activity logic irrelevant to free subscriptions

## Implementation

### 1. New Form: `FreeSubscriptionForm`

Created a dedicated form for free subscription management in `support/forms.py`:

**Key Features:**

- Based on `EmailValidationForm` for email uniqueness validation
- Includes all contact fields (name, last_name, phone, mobile, email, notes)
- **Required field:** `free_subscription_requested_by` dropdown with choices:
  - HR (Human Resources)
  - AD (Advertisement)
  - MA (Management)
- Start date and end date fields (end date is mandatory)
- Default address selection
- Email validation to prevent duplicates across contacts

```python
class FreeSubscriptionForm(EmailValidationForm):
    """Form for creating and updating free subscriptions."""
    # Contact fields
    name = forms.CharField(...)
    last_name = forms.CharField(...)
    phone = PhoneNumberField(...)
    mobile = PhoneNumberField(...)
    email = forms.EmailField(...)
    notes = forms.CharField(...)

    # Subscription fields
    start_date = forms.DateField(...)
    end_date = forms.DateField(required=True)
    default_address = forms.ModelChoiceField(...)

    # Free subscription specific field
    free_subscription_requested_by = forms.ChoiceField(required=True)
```

### 2. Shared Mixin: `FreeSubscriptionMixin`

Created a mixin to share common functionality between create and update views:

**Responsibilities:**

- **Permission Check:** Verifies user has `core.can_add_free_subscription` permission
- **Form Customization:** Sets address queryset and passes contact to form
- **Contact Updates:** `update_contact_data()` method updates contact info if changed
- **Product Management:** `add_products_to_subscription()` handles adding products to subscription

```python
class FreeSubscriptionMixin:
    def test_func(self):
        """Check if user has permission to add free subscriptions."""
        return self.request.user.has_perm('core.can_add_free_subscription')

    def update_contact_data(self, form):
        """Update contact information if changed."""
        # Updates name, last_name, phone, mobile, email, notes

    def add_products_to_subscription(self, subscription):
        """Add products to the subscription based on POST data."""
        # Handles product selection with address, copies, messages, instructions
```

### 3. Create View: `CreateFreeSubscriptionView`

Implemented a FormView for creating new free subscriptions:

**Architecture:**

- Inherits from: `FreeSubscriptionMixin`, `BreadcrumbsMixin`, `FormView`
- **No Campaign Logic:** Completely standalone, no campaign/seller/activity parameters
- **Permission-Based:** Requires `can_add_free_subscription` permission
- **Manager-Focused:** Designed for managers, not sellers

**Key Features:**

- Pre-populates form with contact information
- Default start date: today
- Default end date: 5 business days from today
- Creates subscription with `type="F"` (Free)
- Sets `free_subscription_requested_by` field
- Supports multiple products with addresses, copies, messages, and instructions
- Includes breadcrumbs navigation
- Success message and redirect to contact detail page

**URL Pattern:**

```python
path('contact/<int:contact_id>/create-free-subscription/',
     create_free_subscription,
     name='create_free_subscription')
```

### 4. Update View: `UpdateFreeSubscriptionView`

Implemented a FormView for updating existing free subscriptions:

**Architecture:**

- Inherits from: `FreeSubscriptionMixin`, `BreadcrumbsMixin`, `FormView`
- **Uses FormView, not UpdateView:** Since `FreeSubscriptionForm` is not a ModelForm
- **Simple Update Logic:** Pre-populates form with existing subscription data

**Key Features:**

- Shows all offerable products (not just existing ones)
- Pre-checks and pre-fills existing products with green background
- Shows unchecked products with gray background (can add new products)
- Updates subscription dates and `free_subscription_requested_by` field
- Maintains existing product configurations
- Success message and redirect to contact detail page

**URL Pattern:**

```python
path('subscription/<int:subscription_id>/update-free-subscription/',
     update_free_subscription,
     name='update_free_subscription')
```

### 5. Template: `free_subscription_form.html`

Created a comprehensive template based on `seller_console_start_promo.html`:

**Features:**

- Works for both create and update operations (uses `is_update` context variable)
- Displays `free_subscription_requested_by` dropdown as required field
- Product selection with checkboxes
- For each product:
  - Address dropdown
  - Copies input
  - Message input (optional)
  - Special instructions input (optional)
- Address management:
  - "New address" button (opens in new tab)
  - "Reload addresses" button (AJAX refresh)
- Visual feedback:
  - Green background for selected products
  - Gray background for unselected products
  - Dynamic color changes on checkbox toggle
- Form validation with clear error messages
- Cancel button returns to contact detail page

**Update Mode Behavior:**

```django
{% for product in offerable_products %}
  {# Check if product exists in subscription #}
  {% if product in existing_products %}
    {# Show checked with green background and pre-filled values #}
  {% else %}
    {# Show unchecked with gray background and default values #}
  {% endif %}
{% endfor %}
```

### 6. UI Integration

Added "Create free subscription" buttons to contact detail pages:

**Locations:**

1. **Overview Tab** (`_overview.html`):

   ```django
   {% if perms.core.can_add_free_subscription %}
     <a href="{% url "create_free_subscription" contact.id %}" class="btn btn-primary">
       <i class="fas fa-plus-circle"></i> {% trans "Create free subscription" %}
     </a>
   {% endif %}
   ```

2. **Subscriptions Tab** (`_subscriptions.html`):
   - Same button placement with permission check

3. **Subscription Cards** (`_subscription_card.html`):

   ```django
   {% elif subscription.type == "F" %}
     {% if request.user|in_group:"Managers" %}
       <a href="{% url "update_free_subscription" subscription.id %}" class="btn btn-sm btn-primary">
         <i class="fas fa-edit"></i> {% trans "Update Free Subscription" %}
       </a>
     {% endif %}
   {% endif %}
   ```

4. **Overview Subscription List** (`_overview_subscription_list_item.html`):
   - Similar update button for free subscriptions in overview list

## Key Differences from Promotional Subscriptions

| Feature | Promotional Subscriptions | Free Subscriptions |
|---------|--------------------------|-------------------|
| **Permission** | `is_staff` | `can_add_free_subscription` |
| **User Role** | Sellers | Managers |
| **Campaign Logic** | Required (campaign, seller, activity) | None (standalone) |
| **Subscription Type** | "P" (Promotional) | "F" (Free) |
| **Required Fields** | End date | End date + `free_subscription_requested_by` |
| **URL Parameters** | `act`, `new`, `offset`, `url` | Only `contact_id` or `subscription_id` |
| **Base View** | FormView | FormView (both create and update) |
| **Workflow** | Campaign-driven | Manager-initiated |

## Technical Details

### Form Architecture Decision

**Why not ModelForm?**

`FreeSubscriptionForm` is a regular `Form`, not a `ModelForm`, because:

1. Updates both `Contact` and `Subscription` models
2. Handles product relationships separately
3. Needs custom validation logic
4. Similar pattern to existing `NewPromoForm`

**UpdateView vs FormView:**

Initially attempted `UpdateView` for `UpdateFreeSubscriptionView`, but this caused issues:

- `UpdateView` expects a `ModelForm` and passes `instance` parameter
- Regular `Form` classes don't accept `instance` parameter
- Solution: Use `FormView` for both create and update views
- Manual handling of subscription updates in `form_valid()`

### Permission Model

Uses existing `Subscription` model permission:

```python
class Subscription(models.Model):
    class Meta:
        permissions = [
            ("can_add_free_subscription", _("Can add free subscription")),
            ("can_add_corporate_subscription", _("Can add corporate subscription")),
        ]
```

### Product Management

Products are handled via POST data parsing:

```python
for key, value in self.request.POST.items():
    if key.startswith("check"):
        product_id = key.split("-")[1]
        # Get address, copies, message, instructions
        subscription.add_product(...)
```

## Benefits

### For Managers

- **Dedicated Interface:** Purpose-built UI for free subscription management
- **Clear Workflow:** No confusion with campaign-based promotional flows
- **Required Fields:** Ensures `free_subscription_requested_by` is always set
- **Full Control:** Can add/update products, addresses, and subscription details

### For System

- **Permission-Based:** Clear access control via `can_add_free_subscription`
- **Data Integrity:** Email validation prevents duplicates
- **Audit Trail:** `free_subscription_requested_by` tracks subscription source
- **Maintainable:** Shared mixin reduces code duplication

### For Users

- **Intuitive UI:** Similar to promotional subscription forms but simplified
- **Visual Feedback:** Color-coded product selection (green = selected, gray = available)
- **Flexible Updates:** Can add new products or modify existing ones
- **Clear Navigation:** Breadcrumbs and cancel buttons for easy navigation

## Files Modified

### New Files

- `support/templates/free_subscription_form.html` - Template for create/update forms

### Modified Files

- `support/forms.py` - Added `FreeSubscriptionForm`
- `support/views/subscriptions.py` - Added `FreeSubscriptionMixin`, `CreateFreeSubscriptionView`, `UpdateFreeSubscriptionView`
- `support/views/__init__.py` - Exported new views
- `support/urls.py` - Added URL patterns for create and update views
- `support/templates/contact_detail/tabs/_overview.html` - Added create button
- `support/templates/contact_detail/tabs/_subscriptions.html` - Added create button
- `support/templates/contact_detail/tabs/includes/_subscription_card.html` - Added update button for type "F"
- `support/templates/contact_detail/tabs/includes/_overview_subscription_list_item.html` - Added update button

## Usage

### Creating a Free Subscription

1. Navigate to contact detail page
2. Click "Create free subscription" button (requires `can_add_free_subscription` permission)
3. Fill in contact information (pre-populated)
4. Set start and end dates
5. **Select reason:** Choose from HR, Advertisement, or Management
6. Select products with checkboxes
7. Configure address, copies, message, and instructions for each product
8. Click "Create"

### Updating a Free Subscription

1. Navigate to contact detail page
2. Find the free subscription in the subscriptions list
3. Click "Update Free Subscription" button (Managers only)
4. Modify dates or `free_subscription_requested_by` if needed
5. Add/remove products by checking/unchecking boxes
6. Update product configurations as needed
7. Click "Update"

## Future Enhancements

Potential improvements for future iterations:

1. **Bulk Operations:** Create multiple free subscriptions at once
2. **Templates:** Save common free subscription configurations
3. **Reporting:** Analytics on free subscription usage by source (HR/AD/MA)
4. **Expiration Alerts:** Notifications when free subscriptions are about to expire
5. **Approval Workflow:** Optional approval process for free subscriptions
6. **Budget Tracking:** Track cost of free subscriptions by department

## Testing Recommendations

1. **Permission Testing:**
   - Verify only users with `can_add_free_subscription` can access views
   - Test button visibility based on permissions

2. **Form Validation:**
   - Test email uniqueness validation
   - Verify `free_subscription_requested_by` is required
   - Test end date requirement

3. **Product Management:**
   - Create subscription with multiple products
   - Update subscription to add/remove products
   - Verify product configurations are preserved

4. **UI Testing:**
   - Test address reload functionality
   - Verify product checkbox color changes
   - Test breadcrumbs navigation

5. **Edge Cases:**
   - Contact with no addresses
   - Subscription with no products
   - Updating subscription dates to past dates

## Migration Notes

No database migrations required. The feature uses existing:

- `Subscription` model with `type="F"` and `free_subscription_requested_by` field
- `SubscriptionProduct` model for product relationships
- `can_add_free_subscription` permission (already defined)

## Backward Compatibility

Fully backward compatible:

- Existing free subscriptions continue to work
- No changes to existing promotional subscription workflows
- Admin interface remains functional for free subscriptions
- All existing permissions and models unchanged
