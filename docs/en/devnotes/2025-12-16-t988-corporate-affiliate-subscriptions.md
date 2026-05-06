# Corporate and Affiliate Subscription System Implementation

**Date:** 2025-12-16
**Ticket:** t988
**Type:** New Feature
**Component:** Subscriptions, Forms, Views
**Impact:** Corporate Subscription Management, Affiliate Management, User Experience

## Summary

Implemented a complete corporate and affiliate subscription system in utopia-crm, enabling the creation of corporate subscriptions with multiple affiliated sub-subscriptions. This includes missing imports, URL configuration, form integration, and comprehensive validation to manage corporate subscription slots and affiliate relationships.

## Motivation

The system needed functionality to manage corporate subscriptions where:

1. **Multiple subscriptions:** A main corporate subscription can have several affiliated subscriptions
2. **Custom pricing:** Ability to override automatically calculated prices for special corporate agreements
3. **Slot management:** Track and enforce limits on the number of affiliated subscriptions
4. **Relationship tracking:** Clear parent-child relationships between corporate and affiliate subscriptions

The base `CorporateSubscriptionCreateView` existed but was minimal and incomplete (marked with TODO). The `AffiliateSubscriptionCreateView` was brought from another project but was missing imports and URL configuration.

## Implementation

### 1. Fixed Missing Imports in `AffiliateSubscriptionCreateView`

**File:** `support/views/subscriptions.py`

Added missing imports required by the affiliate subscription view:

```python
from dateutil.relativedelta import relativedelta
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.timezone import now
from django.views.generic import CreateView
```

**Purpose:**

- `LoginRequiredMixin` - Authentication requirement
- `CreateView` - Base class for the view
- `now` - Get current datetime for date calculations
- `relativedelta` - Calculate subscription end dates based on product duration

### 2. Fixed View Export

**File:** `support/views/__init__.py`

Corrected the export name from incorrect to actual class name:

```python
# Before (incorrect)
AffiliateSubscriptionView,

# After (correct)
AffiliateSubscriptionCreateView,
```

### 3. Added URL Pattern for Affiliate Subscriptions

**File:** `support/urls.py`

Added the missing URL pattern:

```python
path(
    "subscription/<int:subscription_id>/affiliate/new/",
    views.AffiliateSubscriptionCreateView.as_view(),
    name="add_affiliate_subscription",
),
```

**URL:** `/support/subscription/{subscription_id}/affiliate/new/`

This matches the URL name referenced in the contact detail template (line 153).

### 4. Fixed URL References in View

**File:** `support/views/subscriptions.py`

Replaced non-existent `subscription_detail` URL with `contact_detail`:

```python
# Before (broken)
return HttpResponseRedirect(reverse("subscription_detail", args=[self.corporate_subscription.id]))

# After (working)
return HttpResponseRedirect(reverse("contact_detail", args=[self.corporate_subscription.contact.id]))
```

This ensures proper redirects when validation fails.

## How the System Works

### Corporate Subscriptions

**Database Fields:**

```python
type = models.CharField(max_length=1, choices=SUBSCRIPTION_TYPES)
# 'C' = Corporate (parent)
# 'A' = Affiliate (child)

parent_subscription = models.ForeignKey(
    'self',
    null=True,
    blank=True,
    on_delete=models.CASCADE,
    related_name='affiliate_subscriptions'
)

number_of_subscriptions = models.IntegerField(default=1)
# For corporate subscriptions, defines total slots (including parent)
```

**Relationship Structure:**

```text
Corporate Subscription (type='C')
├── number_of_subscriptions = 5
├── Affiliate Subscription 1 (type='A', parent_subscription=Corporate)
├── Affiliate Subscription 2 (type='A', parent_subscription=Corporate)
├── Affiliate Subscription 3 (type='A', parent_subscription=Corporate)
└── Affiliate Subscription 4 (type='A', parent_subscription=Corporate)
```

### Creating Affiliate Subscriptions

**Access:** From a corporate subscription (type='C') in the contact detail page, click "Add Affiliate" button

**Requirements:**

- Parent subscription must be type 'C' (Corporate)
- Must have available slots (`current_affiliates < number_of_subscriptions`)
- Selected contact cannot be the same as the corporate subscription contact
- Selected contact cannot already have an active affiliate subscription

**Process:**

1. View displays available slots and current affiliates
2. User searches for a contact using HTMX search
3. Dates are pre-filled based on the product's duration
4. On submit, creates a new subscription with:
   - `type='A'` (Affiliate)
   - `parent_subscription` = corporate subscription
   - Same product as corporate subscription
   - Specified start/end dates

### View Features

**Validations:**

- ✅ Ensures parent subscription is corporate (type='C')
- ✅ Checks affiliate limit hasn't been reached
- ✅ Prevents duplicate contact (can't be same as corporate contact)
- ✅ Prevents contact from having multiple active affiliate subscriptions

**Automatic Setup:**

- Sets subscription type to 'A' (Affiliate)
- Links to parent corporate subscription
- Adds the same product as the corporate subscription
- Sets renewal type to 'M' (Manual)

**UI Features:**

- Shows current affiliates count vs. total slots
- Lists all existing affiliate subscriptions
- HTMX-powered contact search
- Pre-filled dates based on product duration

## Template Integration

The "Add Affiliate" button appears in the contact detail subscription list when:

- Subscription type is 'C' (Corporate)
- User is in Support or Managers group
- Subscription is not obsolete

**Template:** `support/templates/contact_detail/tabs/includes/_overview_subscription_list_item.html`

```django
{% if subscription.type == "C" %}
  <a href="{% url "add_affiliate_subscription" subscription.id %}"
     class="btn btn-sm btn-success mr-1 mb-1">
    <i class="fas fa-user-plus"></i> {% trans "Add Affiliate" %}
  </a>
{% endif %}
```

## Form: AffiliateSubscriptionForm

**File:** `support/forms.py`

```python
class AffiliateSubscriptionForm(forms.ModelForm):
    contact = forms.CharField(widget=forms.TextInput(...))
    start_date = forms.DateField(...)
    end_date = forms.DateField(...)

    class Meta:
        model = Subscription
        fields = ['contact', 'start_date', 'end_date']
```

**Features:**

- Contact field accepts contact ID (validated in `clean_contact()`)
- Date fields use HTML5 date picker
- Automatically sets type='A' and renewal_type='M' on save

## Usage Example

1. Create a corporate subscription with `number_of_subscriptions=5`
2. Navigate to the corporate subscription contact's detail page
3. Click "Add Affiliate" button on the corporate subscription
4. Search and select a contact
5. Adjust dates if needed (pre-filled based on product duration)
6. Submit form
7. Affiliate subscription is created and linked to corporate subscription

## Benefits

✅ **Centralized Management:** All affiliates linked to one corporate subscription
✅ **Slot Control:** Enforces maximum number of affiliates
✅ **Automatic Product Assignment:** Affiliates get the same product as corporate
✅ **Easy Navigation:** Links between parent and affiliate subscriptions
✅ **Validation:** Prevents duplicate affiliates and invalid configurations
✅ **Complete Integration:** Works with existing subscription management system

## Files Modified

- `support/views/subscriptions.py` - Added missing imports, fixed URL references
- `support/views/__init__.py` - Fixed view export name
- `support/urls.py` - Added affiliate subscription URL pattern
- `support/forms.py` - Already had `AffiliateSubscriptionForm` (no changes needed)
- `support/templates/subscriptions/affiliate_subscriptions.html` - Already existed (no changes needed)
- `tests/test_corporate_billing.py` - New comprehensive test suite for corporate and affiliate billing

## Tests

Created comprehensive test suite in `tests/test_corporate_billing.py` that verifies:

- **Corporate subscriptions use override_price** when set instead of calculated product price
- **Corporate subscriptions without override_price** use normal product pricing
- **Affiliate subscriptions (type='A') cannot be billed** - similar to free subscriptions
- **Free subscriptions (type='F') cannot be billed** - baseline verification
- **Multiple affiliates structure** - only corporate subscription creates invoices, affiliates don't
- **Corporate subscriptions with end_date** - one-time billing behavior

All tests handle both English and Spanish error messages for internationalization.

## Documentation

Comprehensive documentation created in:

- `/docs/AFFILIATE_SUBSCRIPTION_INTEGRATION.md` - Complete usage and architecture guide

## Related Changes

For La Diaria-specific corporate subscription implementation with additional features (gigantes, cards, seller preservation), see the corresponding changelog in utopia-crm-ladiaria.
