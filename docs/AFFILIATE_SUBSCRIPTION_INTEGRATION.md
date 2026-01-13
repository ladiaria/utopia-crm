# Affiliate Subscription Integration

## Overview

Integrated the `AffiliateSubscriptionCreateView` to allow adding affiliate subscriptions to corporate subscriptions. This enables creating multiple sub-subscriptions linked to a main corporate subscription.

## Changes Made

### 1. **Added Missing Imports** (`support/views/subscriptions.py`)

Added the following imports required by `AffiliateSubscriptionCreateView`:

```python
from dateutil.relativedelta import relativedelta
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.timezone import now
from django.views.generic import CreateView
```

### 2. **Fixed View Export** (`support/views/__init__.py`)

Changed the export from incorrect name to correct class name:

```python
# Before
AffiliateSubscriptionView,

# After
AffiliateSubscriptionCreateView,
```

### 3. **Added URL Pattern** (`support/urls.py`)

Added the URL pattern for creating affiliate subscriptions:

```python
path(
    "subscription/<int:subscription_id>/affiliate/new/",
    views.AffiliateSubscriptionCreateView.as_view(),
    name="add_affiliate_subscription",
),
```

**URL:** `/support/subscription/{subscription_id}/affiliate/new/`

### 4. **Fixed URL References in View**

Replaced non-existent `subscription_detail` URL with `contact_detail`:

```python
# Before
return HttpResponseRedirect(reverse("subscription_detail", args=[self.corporate_subscription.id]))

# After
return HttpResponseRedirect(reverse("contact_detail", args=[self.corporate_subscription.contact.id]))
```

## How It Works

### Creating Affiliate Subscriptions

1. **Access Point:** From a corporate subscription (type='C') in the contact detail page, click "Add Affiliate" button
2. **Requirements:**
   - Parent subscription must be type 'C' (Corporate)
   - Must have available slots (`current_affiliates < number_of_subscriptions`)
   - Selected contact cannot be the same as the corporate subscription contact
   - Selected contact cannot already have an active affiliate subscription

3. **Process:**
   - View displays available slots and current affiliates
   - User searches for a contact using HTMX search
   - Dates are pre-filled based on the product's duration
   - On submit, creates a new subscription with:
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

```django
{% if subscription.type == "C" %}
  <a href="{% url "add_affiliate_subscription" subscription.id %}"
     class="btn btn-sm btn-success mr-1 mb-1">
    <i class="fas fa-user-plus"></i> {% trans "Add Affiliate" %}
  </a>
{% endif %}
```

## Database Structure

### Subscription Model Fields Used

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

### Relationships

```text
Corporate Subscription (type='C')
├── number_of_subscriptions = 5
├── Affiliate Subscription 1 (type='A', parent_subscription=Corporate)
├── Affiliate Subscription 2 (type='A', parent_subscription=Corporate)
├── Affiliate Subscription 3 (type='A', parent_subscription=Corporate)
└── Affiliate Subscription 4 (type='A', parent_subscription=Corporate)
```

## Form: AffiliateSubscriptionForm

Located in `support/forms.py`:

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

## Related Views

- **Corporate Subscription Creation:** `CorporateSubscriptionCreateView` (creates the parent)
- **Affiliate Subscription Creation:** `AffiliateSubscriptionCreateView` (creates children)
- **Contact Detail:** Shows both corporate and affiliate subscriptions with navigation

## Next Steps (Optional)

Consider implementing:

1. **Bulk Affiliate Creation:** Create multiple affiliates at once via CSV
2. **Affiliate Management View:** List/edit all affiliates for a corporate subscription
3. **Affiliate Transfer:** Move affiliate from one corporate subscription to another
4. **Affiliate Notifications:** Email affiliates when added to corporate subscription
