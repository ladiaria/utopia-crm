# Retention Discount Management System

**Date:** 2025-12-01
**Type:** Feature Enhancement
**Component:** Subscription Management
**Impact:** Manager Workflow, Retention Strategy

## Summary

Implemented a complete retention discount management system that allows managers to offer retention discounts to subscribers who are considering cancellation. The feature provides a dedicated view for adding retention discount products to subscriptions, creating a new subscription with discounts while properly marking the old subscription with retention-specific unsubscription reasons.

## Motivation

Previously, the system lacked a dedicated workflow for offering retention discounts to subscribers. When a subscriber wanted to cancel, managers had no streamlined way to:

1. **Offer Retention Discounts:** No dedicated interface to add retention-specific discount products
2. **Track Retention Attempts:** No way to distinguish retention-based subscription changes from other types
3. **Categorize Discounts:** No field to categorize discount products by purpose (retention, promotion, staff, other)
4. **Maintain Audit Trail:** No clear indication that a subscription change was due to a retention offer

This led to:

- Manual workarounds using generic discount products
- Unclear reporting on retention success rates
- Difficulty tracking which discounts were offered for retention purposes
- Inconsistent handling of retention scenarios

## Implementation

### 1. New Model Field: `Product.discount_category`

Added a new field to categorize discount products in `core/models.py`:

**Field Definition:**

```python
class Product(models.Model):
    class DiscountCategoryChoices(models.TextChoices):
        """Choices for the discount category field"""
        RETENTION = "R", _("Retention")
        PROMOTION = "P", _("Promotion")
        STAFF = "S", _("Staff")
        OTHER = "O", _("Other")

    discount_category = models.CharField(
        max_length=1,
        choices=DiscountCategoryChoices.choices,
        verbose_name=_("Discount category"),
        null=True,
        blank=True,
        help_text=_("Category of the discount. Mandatory if the product type is discount."),
    )
```

**Key Features:**

- **Optional Field:** Can be null/blank for non-discount products
- **Four Categories:** Retention, Promotion, Staff, Other
- **Admin Integration:** Added to Product admin fieldset for easy management
- **Help Text:** Clear guidance on when to use this field

**Migration:**

Created migration `0111_product_discount_category.py` to add the field to existing database.

### 2. New Unsubscription Types

Enhanced `Subscription` model with retention-specific choices:

**Existing Enhancements:**

```python
class Subscription(models.Model):
    class InactivityReasonChoices(models.IntegerChoices):
        # ... existing choices ...
        RETENTION = 17, _("Retention")

    class UnsubscriptionTypeChoices(models.IntegerChoices):
        # ... existing choices ...
        RETENTION = 5, _("Retention")
```

These choices were already defined in the model and are now utilized by the retention discount workflow.

### 3. New Form: `RetentionDiscountForm`

Created a dedicated form for retention discount management in `support/forms.py`:

**Key Features:**

```python
class RetentionDiscountForm(forms.ModelForm):
    """Form for adding retention discounts to a subscription"""
    start_date = forms.DateField(
        required=True,
        label=_("Start date for new subscription"),
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": "datepicker form-control", "autocomplete": "off"}),
    )

    class Meta:
        model = Subscription
        fields = (
            "start_date",
            "unsubscription_addendum",
        )
```

- **Start Date:** When the new subscription with discounts will begin
- **Unsubscription Addendum:** Optional notes about the retention offer
- **Simple Design:** Minimal fields focused on the retention workflow

### 4. New View: `add_retention_discount`

Implemented a function-based view for adding retention discounts:

**Architecture:**

- **Permission:** Requires `@staff_member_required` decorator
- **Workflow:** Similar to `book_additional_product` but focused on retention
- **Redirect:** Returns to contact detail page (not edit subscription)

**Key Features:**

```python
@staff_member_required
def add_retention_discount(request, subscription_id):
    """
    View for adding retention discounts to a subscription.
    Creates a new subscription with retention discount products starting on a specified date.
    Sets the old subscription's unsubscription type and reason to RETENTION.
    """
```

**Product Filtering:**

```python
retention_products = Product.objects.filter(
    type__in=["D", "P", "A"],  # Discount, Percentage discount, Advanced discount
    discount_category="R",  # RETENTION
    active=True
)
```

Only shows products that are:

- Discount types (D, P, or A)
- Categorized as RETENTION
- Currently active

**Subscription Creation:**

1. **Sets End Date:** Old subscription gets end date set to new subscription's start date
2. **Creates New Subscription:** Copies all details from old subscription
3. **Copies Products:** All existing products are copied to new subscription with original metadata
4. **Adds Discounts:** Selected retention discount products are added
5. **Sets Retention Status:**

   ```python
   old_subscription.inactivity_reason = Subscription.InactivityReasonChoices.RETENTION
   old_subscription.unsubscription_type = Subscription.UnsubscriptionTypeChoices.RETENTION
   old_subscription.unsubscription_date = date.today()
   old_subscription.unsubscription_manager = request.user
   ```

**Metadata Preservation:**

```python
# Copy all products from old subscription
for sp in old_subscription.subscriptionproduct_set.all():
    new_sp = new_subscription.add_product(
        product=sp.product,
        address=sp.address,
        copies=sp.copies,
        message=sp.label_message,
        instructions=sp.special_instructions,
        seller_id=sp.seller_id,  # Preserves original seller
    )
    new_sp.original_datetime = sp.original_datetime
    if logistics_is_installed():
        if sp.route:
            new_sp.route = sp.route
        if sp.order:
            new_sp.order = sp.order
    new_sp.save()
```

### 5. Template: `add_retention_discount.html`

Created a comprehensive template based on `book_additional_product.html`:

**Features:**

- **Current Products Display:** Shows all products in current subscription
- **Retention Product Selection:** Checkboxes for available retention discounts
- **Product Pricing:** Displays price for each discount product
- **Date Selection:** Start date picker for new subscription
- **Unsubscription Notes:** Optional addendum field
- **JavaScript Validation:** Requires at least one product to be selected
- **Visual Feedback:** Disabled submit button until product is selected
- **Error Handling:** Clear error messages for validation failures

**JavaScript Validation:**

```javascript
function activateSend() {
    var disable = false;

    if ($(".enable-product:checked").length == 0) {
        disable = true;
        $("#custom_error_message").text("Select at least one retention discount to continue");
    } else {
        disable = false;
    }

    if (disable == false) {
        $("#send_form").removeAttr("disabled");
        $("#custom_error_message").text("");
    } else {
        $("#send_form").attr("disabled", "disabled");
    }
}
```

**No Products Handling:**

```django
{% if retention_products %}
  {# Show product checkboxes #}
{% else %}
  <div class="alert alert-warning">
    {% trans "No retention discount products available. Please create retention discount products first." %}
  </div>
{% endif %}
```

### 6. New Permission: `can_offer_retention`

Added a new permission to control access to retention discount functionality:

**Permission Definition:**

```python
class Subscription(models.Model):
    class Meta:
        permissions = [
            ("can_add_free_subscription", _("Can add free subscription")),
            ("can_add_corporate_subscription", _("Can add corporate subscription")),
            ("can_offer_retention", _("Can offer retention")),
        ]
```

**Usage in Templates:**

```django
{% if perms.core.can_offer_retention and not subscription.is_obsolete %}
  <a href="{% url "add_retention_discount" subscription.id %}"
     class="btn btn-sm btn-primary mr-1 mb-1">
    <i class="fas fa-plus-circle"></i> {% trans "Offer retention" %}
  </a>
{% endif %}
```

### 7. UI Integration

Added "Offer retention" buttons to contact detail pages:

#### Location: Promotional Subscriptions

In `_overview_subscription_list_item.html`:

```django
{% if subscription.type == "P" %}
  {% if request.user|in_group:"Managers" %}
    {# Existing manager buttons #}
  {% endif %}
  {% if perms.core.can_offer_retention and not subscription.is_obsolete %}
    <a href="{% url "add_retention_discount" subscription.id %}"
       class="btn btn-sm btn-primary mr-1 mb-1">
      <i class="fas fa-plus-circle"></i> {% trans "Offer retention" %}
    </a>
  {% endif %}
{% endif %}
```

**Key Conditions:**

- Only shown for promotional subscriptions (type "P")
- User must have `can_offer_retention` permission
- Subscription must not be obsolete (not replaced by another subscription)

**Obsolete Subscription Indicator:**

Added visual indicator for replaced subscriptions:

```django
{% if subscription.is_obsolete %}
  <div class="alert alert-warning py-1 px-2 mb-2">
    <small><i class="fas fa-exchange-alt"></i> {% trans "Replaced by subscription" %} #{{ subscription.get_updated_subscription.id }}</small>
  </div>
{% endif %}
```

### 8. URL Configuration

Added URL pattern in `support/urls.py`:

**Pattern:**

```python
path("add_retention_discount/<int:subscription_id>/",
     add_retention_discount,
     name="add_retention_discount")
```

**Modernization:**

Also converted related URL patterns from `re_path` to `path` for consistency:

```python
# Before
re_path(r"^additional_product/(\d+)/$", book_additional_product, name="additional_product")

# After
path("additional_product/<int:subscription_id>/", book_additional_product, name="additional_product")
```

## Key Differences from Other Subscription Workflows

| Feature | Add Product | Product Change | Retention Discount |
|---------|-------------|----------------|-------------------|
| **Permission** | `staff_member_required` | `staff_member_required` | `staff_member_required` + `can_offer_retention` |
| **Product Filter** | Offerable subscriptions | Offerable subscriptions | Retention discounts only |
| **Unsubscription Type** | ADDED_PRODUCTS | CHANGED_PRODUCTS | RETENTION |
| **Inactivity Reason** | ADDED_PRODUCTS | CHANGED_PRODUCTS | RETENTION |
| **Redirect Target** | Edit subscription | Edit subscription | Contact detail |
| **Sales Record** | Yes (partial sale) | No | No |
| **Primary Use Case** | Add new products | Change products | Offer retention discounts |

## Benefits

### For Managers

- **Dedicated Workflow:** Purpose-built UI for offering retention discounts
- **Clear Categorization:** Easily identify which products are for retention
- **Audit Trail:** Clear tracking of retention attempts in subscription history
- **Quick Access:** Button directly on promotional subscription cards
- **Simplified Process:** No need to navigate through multiple screens

### For Reporting

- **Retention Tracking:** Can query subscriptions with `unsubscription_type=RETENTION`
- **Success Metrics:** Track how many retention offers were accepted
- **Discount Analysis:** Identify which retention discounts are most effective
- **Revenue Impact:** Calculate cost of retention discounts vs. lost subscriptions

### For System

- **Data Integrity:** Proper categorization of subscription changes
- **Permission Control:** Fine-grained access via `can_offer_retention` permission
- **Consistent Workflow:** Follows established patterns from other subscription views
- **Maintainable:** Reuses existing subscription creation logic

## Usage

### Setting Up Retention Discount Products

1. Navigate to Django admin → Products
2. Create or edit a discount product (type D, P, or A)
3. Set **Discount category** to "Retention"
4. Set product as **Active**
5. Configure pricing and other product details

### Offering a Retention Discount

1. Navigate to contact detail page
2. Find the promotional subscription in the subscriptions list
3. Click "Offer retention" button (requires `can_offer_retention` permission)
4. Review current products in the subscription
5. Select one or more retention discount products
6. Set the start date for the new subscription
7. Optionally add notes in the unsubscription addendum
8. Click "Send"
9. System creates new subscription with discounts
10. Old subscription is marked with retention status
11. Redirected to contact detail page

### Viewing Retention History

**In Contact Detail:**

- Obsolete subscriptions show "Replaced by subscription #X" alert
- New subscription shows all products including retention discounts

**In Admin:**

- Filter subscriptions by `unsubscription_type=RETENTION`
- View `unsubscription_addendum` for retention notes
- Check `unsubscription_manager` to see who offered the discount

## Technical Details

### Product Filtering Logic

The view filters products using three criteria:

```python
retention_products = Product.objects.filter(
    type__in=["D", "P", "A"],  # Must be a discount type
    discount_category="R",      # Must be categorized as retention
    active=True                 # Must be currently active
)
```

**Why Three Discount Types?**

- **D (Discount):** Fixed amount discounts
- **P (Percentage discount):** Percentage-based discounts
- **A (Advanced discount):** Complex discount rules

All three can be used for retention purposes depending on the business strategy.

### Subscription Relationship

The new subscription maintains a relationship to the old one:

```python
new_subscription = Subscription.objects.create(
    # ... other fields ...
    updated_from=old_subscription,  # Links to previous subscription
)
```

This creates a chain of subscriptions that can be traced through the system.

### Seller Preservation

Unlike some other subscription workflows, retention discounts preserve the original seller:

```python
seller_id=sp.seller_id,  # Maintains original seller for commission tracking
```

This ensures sellers don't lose commission when a retention discount is offered.

### No Sales Record

Retention discounts do **not** create a `SalesRecord` because:

1. It's not a new sale, it's a retention effort
2. The discount reduces revenue rather than adding it
3. Tracking is done via `unsubscription_type` instead

## Files Modified

### New Files

- `support/templates/add_retention_discount.html` - Template for retention discount form
- `core/migrations/0111_product_discount_category.py` - Migration for new field

### Modified Files

- `core/models.py` - Added `discount_category` field to Product model, added `can_offer_retention` permission
- `core/admin.py` - Added `discount_category` to Product admin fieldset
- `support/forms.py` - Added `RetentionDiscountForm`
- `support/views/subscriptions.py` - Added `add_retention_discount` view
- `support/views/__init__.py` - Exported `add_retention_discount` view
- `support/urls.py` - Added URL pattern and modernized related patterns
- `support/templates/contact_detail/tabs/includes/_overview_subscription_list_item.html` - Added "Offer retention" button and obsolete subscription indicator

## Reporting Queries

### Find All Retention Attempts

```python
retention_subscriptions = Subscription.objects.filter(
    unsubscription_type=Subscription.UnsubscriptionTypeChoices.RETENTION
)
```

### Calculate Retention Success Rate

```python
from django.db.models import Count

retention_attempts = Subscription.objects.filter(
    unsubscription_type=Subscription.UnsubscriptionTypeChoices.RETENTION
).count()

successful_retentions = Subscription.objects.filter(
    updated_from__unsubscription_type=Subscription.UnsubscriptionTypeChoices.RETENTION,
    active=True
).count()

success_rate = (successful_retentions / retention_attempts) * 100
```

### Most Used Retention Discounts

```python
from django.db.models import Count

Product.objects.filter(
    discount_category=Product.DiscountCategoryChoices.RETENTION,
    subscriptionproduct__subscription__updated_from__unsubscription_type=Subscription.UnsubscriptionTypeChoices.RETENTION
).annotate(
    usage_count=Count('subscriptionproduct')
).order_by('-usage_count')
```

## Future Enhancements

Potential improvements for future iterations:

1. **Automated Retention Offers:** Trigger retention discount offers based on subscription status
2. **A/B Testing:** Test different retention discount strategies
3. **Retention Dashboard:** Visual analytics on retention success rates
4. **Discount Recommendations:** AI-powered suggestions for which discounts to offer
5. **Multi-Step Retention:** Escalating discount offers for multiple retention attempts
6. **Retention Templates:** Pre-configured discount packages for common scenarios
7. **Approval Workflow:** Optional approval process for high-value retention discounts
8. **Customer Communication:** Automated emails when retention discounts are offered

## Testing Recommendations

1. **Permission Testing:**
   - Verify only users with `can_offer_retention` can see the button
   - Test that staff members can access the view
   - Verify non-staff users are redirected

2. **Product Filtering:**
   - Create products with different discount categories
   - Verify only retention products appear in the form
   - Test with no retention products available

3. **Subscription Creation:**
   - Verify new subscription copies all products correctly
   - Test that seller information is preserved
   - Verify logistics data (routes, orders) is maintained
   - Check that original_datetime is preserved

4. **Status Updates:**
   - Verify old subscription gets RETENTION status
   - Check that unsubscription_date is set correctly
   - Verify unsubscription_manager is recorded

5. **UI Testing:**
   - Test button visibility on different subscription types
   - Verify button is hidden for obsolete subscriptions
   - Test JavaScript validation for product selection
   - Verify redirect to contact detail page

6. **Edge Cases:**
   - Subscription with no products
   - Multiple retention discount products selected
   - Start date in the past
   - Start date far in the future

## Migration Notes

**Required Migration:**

```bash
python manage.py migrate core 0111_product_discount_category
```

This adds the `discount_category` field to the Product model.

**Permission Setup:**

After migration, grant the `can_offer_retention` permission to appropriate user groups:

```python
from django.contrib.auth.models import Group, Permission

managers_group = Group.objects.get(name='Managers')
retention_permission = Permission.objects.get(codename='can_offer_retention')
managers_group.permissions.add(retention_permission)
```

## Backward Compatibility

Fully backward compatible:

- Existing products continue to work (discount_category is nullable)
- Existing subscriptions are unaffected
- No changes to existing subscription workflows
- Admin interface remains functional
- All existing permissions and models unchanged
- New permission is optional (feature gracefully degrades if not granted)

## Security Considerations

1. **Permission-Based Access:** Only users with `can_offer_retention` permission can offer discounts
2. **Staff Requirement:** View requires `@staff_member_required` decorator
3. **Audit Trail:** All retention offers are logged with manager and timestamp
4. **No Direct Database Access:** All operations go through Django ORM
5. **CSRF Protection:** Form includes CSRF token for security

## Performance Considerations

- **Efficient Queries:** Uses `filter()` with indexed fields (type, active)
- **No N+1 Queries:** Products are fetched in a single query
- **Minimal Database Writes:** Only creates necessary records
- **Transaction Safety:** Uses Django's default transaction handling

## Conclusion

The retention discount management system provides a complete, purpose-built workflow for offering retention discounts to subscribers. By properly categorizing discount products and tracking retention attempts through dedicated unsubscription types, the system enables better reporting, clearer audit trails, and more effective retention strategies.
