# 2025-11-04: Choices Modernization and UI Improvements

## Summary

Modernized legacy tuple-based choices to Django's `IntegerChoices` for better type safety and maintainability. Improved subscription and address display layouts for better readability and space efficiency.

## Key Improvements

### 1. Modernize INACTIVITY_REASONS to IntegerChoices

**Problem:** `INACTIVITY_REASONS` was using legacy tuple-based choices, lacking type safety and IDE support.

**Solution:** Converted to `IntegerChoices` class with meaningful constant names and updated all usages.

**Files Modified:**
- `core/choices.py`
- `core/models.py`

#### Changes in `core/choices.py`

**Before:**
```python
INACTIVITY_REASONS = (
    (1, _("Normal end")),
    (2, _("Paused")),
    (3, _("Added products")),
    (4, _("Changed products")),
    (13, _("Debtor")),
    (16, _("Debtor, automatic unsubscription")),
    (99, _("N/A")),
)
```

**After:**
```python
class INACTIVITY_REASONS(IntegerChoices):
    NORMAL_END = 1, _("Normal end")
    PAUSED = 2, _("Paused")
    ADDED_PRODUCTS = 3, _("Added products")
    CHANGED_PRODUCTS = 4, _("Changed products")
    DEBTOR = 13, _("Debtor")
    DEBTOR_AUTOMATIC = 16, _("Debtor, automatic unsubscription")
    NOT_APPLICABLE = 99, _("N/A")
```

#### Changes in `core/models.py`

**Field Definition:**
```python
# Before
inactivity_reason = models.IntegerField(
    choices=INACTIVITY_REASONS, blank=True, null=True, verbose_name=_("Inactivity reason")
)

# After
inactivity_reason = models.IntegerField(
    choices=INACTIVITY_REASONS.choices, blank=True, null=True, verbose_name=_("Inactivity reason")
)
```

**Getter Method:**
```python
# Before
def get_inactivity_reason(self):
    inactivity_reasons = dict(INACTIVITY_REASONS)
    return inactivity_reasons.get(self.inactivity_reason, "N/A")

# After
def get_inactivity_reason(self):
    try:
        return INACTIVITY_REASONS(self.inactivity_reason).label
    except ValueError:
        return "N/A"
```

**Benefits:**
- ✅ **Type Safety**: Better IDE support and validation
- ✅ **Maintainability**: Single source of truth with meaningful constant names
- ✅ **Modern Django**: Uses current best practices for choices
- ✅ **Backward Compatible**: Same integer values, no database changes needed

---

### 2. Modernize UNSUBSCRIPTION_TYPE to IntegerChoices

**Problem:** `UNSUBSCRIPTION_TYPE_CHOICES` was using legacy tuple-based choices.

**Solution:** Converted to `IntegerChoices` class and renamed to `UNSUBSCRIPTION_TYPE` for consistency.

**Files Modified:**
- `core/choices.py`
- `core/models.py`

#### Changes in `core/choices.py`

**Before:**
```python
UNSUBSCRIPTION_TYPE_CHOICES = (
    (1, _("Complete unsubscription")),
    (2, _("Partial unsubscription")),
    (3, _("Product change")),
    (4, _("Added products")),
)
```

**After:**
```python
class UNSUBSCRIPTION_TYPE(IntegerChoices):
    COMPLETE = 1, _("Complete unsubscription")
    PARTIAL = 2, _("Partial unsubscription")
    PRODUCT_CHANGE = 3, _("Product change")
    ADDED_PRODUCTS = 4, _("Added products")
```

#### Changes in `core/models.py`

**Import:**
```python
# Before
from .choices import UNSUBSCRIPTION_TYPE_CHOICES

# After
from .choices import UNSUBSCRIPTION_TYPE
```

**Field Definition:**
```python
# Before
unsubscription_type = models.PositiveSmallIntegerField(
    choices=UNSUBSCRIPTION_TYPE_CHOICES,
    blank=True,
    null=True,
    verbose_name=_("Unsubscription type"),
)

# After
unsubscription_type = models.PositiveSmallIntegerField(
    choices=UNSUBSCRIPTION_TYPE.choices,
    blank=True,
    null=True,
    verbose_name=_("Unsubscription type"),
)
```

**Getter Method:**
```python
# Before
def get_unsubscription_type(self):
    unsubscription_types = dict(UNSUBSCRIPTION_TYPE_CHOICES)
    return unsubscription_types.get(self.unsubscription_type, "N/A")

# After
def get_unsubscription_type(self):
    try:
        return UNSUBSCRIPTION_TYPE(self.unsubscription_type).label
    except ValueError:
        return "N/A"
```

**Benefits:**
- ✅ **Consistency**: Follows same pattern as other IntegerChoices in codebase
- ✅ **Cleaner Code**: Eliminates dict() conversions
- ✅ **Better Error Handling**: Explicit ValueError catching
- ✅ **No Migration Required**: Integer values remain unchanged

---

### 3. Improve Subscription Product Display Layout

**Problem:** Product names and addresses were displayed on separate lines, wasting vertical space. Small text and badges made information hard to read.

**Solution:** Redesigned layout to display products and addresses on the same line using flexbox, with proper alignment and full-size text.

**File Modified:** `support/templates/contact_detail/tabs/includes/_subscription_card.html`

#### Changes

**Before:**
```html
<div class="mb-2 pb-2">
  <div class="d-flex justify-content-between">
    <div>
      {% include "contact_detail/tabs/includes/_subscription_icons.html" with sp=sp %}
      <strong>{{ sp.product.name }}</strong>
      {% if sp.label_contact %}
        <p>({{ sp.label_contact.get_full_name }})</p>
      {% endif %}
    </div>
  </div>
  <p><i class="fas fa-map-marker-alt"></i> {{ sp.address.address_1|default:"N/A" }}
    {% if sp.route %}
      ({% trans "Route" %}: {{ sp.route.number }})
    {% endif %}
  </p>
</div>
```

**After:**
```html
<div class="mb-2 pb-2 {% if not forloop.last %}border-bottom{% endif %}">
  <div class="d-flex align-items-baseline">
    <div style="min-width: 200px; flex-shrink: 0;">
      {% include "contact_detail/tabs/includes/_subscription_icons.html" with sp=sp %}
      <strong>{{ sp.product.name }}</strong>
      {% if sp.label_contact %}
        <small class="text-muted">({{ sp.label_contact.get_full_name }})</small>
      {% endif %}
    </div>
    <div style="flex: 1;">
      <i class="fas fa-map-marker-alt"></i> {{ sp.address.address_1|default:"N/A" }}
      {% if sp.route %}
        ({% trans "Route" %}: {{ sp.route.number }})
      {% endif %}
    </div>
  </div>
</div>
```

**Improvements:**
- ✅ **Space Efficient**: Product and address on same line
- ✅ **Vertical Alignment**: All addresses start at same horizontal position
- ✅ **Better Readability**: Removed muted text from addresses, removed small badges
- ✅ **Table-like Layout**: Fixed-width product column with flexible address column
- ✅ **User-Friendly**: Route displayed as plain text in parentheses instead of tiny badges

---

### 4. Improve Address Display in Overview Tab

**Problem:** Addresses in the overview tab used small text that was hard to read.

**Solution:** Removed `<small>` tags and increased spacing for better readability.

**File Modified:** `support/templates/contact_detail/tabs/_overview.html`

#### Changes

**Before:**
```html
{% if address.address_1 %}
  <div class="mb-1 pl-3">
    <small>
      {{ address.address_1|default:"-" }}
      {% if georef_activated %}
        <!-- georef icons -->
      {% endif %}
    </small>
  </div>
{% else %}
  <div class="mb-1 pl-3">
    <small>{% trans "No address specified" %}</small>
  </div>
{% endif %}
```

**After:**
```html
{% if address.address_1 %}
  <div class="mb-2 pl-3">
    {{ address.address_1|default:"-" }}
    {% if georef_activated %}
      {% if address.needs_georef %}
        <i class="fas fa-times-circle text-danger ml-1" title="{% trans "Needs georeferencing" %}"></i>
      {% elif not address.verified %}
        <a href="{% url "normalizar_direccion" contact.id address.id %}" class="btn btn-xs btn-info ml-1">
          <i class="fas fa-map-marked-alt"></i> {% trans "Normalize" %}
        </a>
      {% else %}
        <i class="fas fa-check-circle text-success ml-1" title="{% trans "Verified" %}"></i>
      {% endif %}
    {% endif %}
  </div>
{% else %}
  <div class="mb-2 pl-3">
    {% trans "No address specified" %}
  </div>
{% endif %}
```

**Improvements:**
- ✅ **Full-Size Text**: Removed `<small>` tags for better readability
- ✅ **Better Spacing**: Changed from `mb-1` to `mb-2` for more breathing room
- ✅ **Consistent Icons**: Added `ml-1` margin to georef icons for better spacing
- ✅ **User-Friendly**: Easier to read addresses at a glance

**Note:** Routes are not displayed in the overview tab because they are associated with SubscriptionProducts, not directly with addresses. Route information is properly displayed in the Subscriptions tab where subscription context is available.

---

### 5. Add Product Ordering to get_subscriptionproducts Method

**Problem:** Subscription products were not consistently ordered, making it harder to scan product lists.

**Solution:** Added ordering by billing priority and product ID to ensure consistent display order.

**File Modified:** `core/models.py`

#### Changes

**Before:**
```python
def get_subscriptionproducts(self, without_discounts=False):
    qs = SubscriptionProduct.objects.filter(subscription=self).select_related("product")
    if without_discounts:
        qs = qs.exclude(product__type="D")
    return qs
```

**After:**
```python
def get_subscriptionproducts(self, without_discounts=False):
    qs = (
        SubscriptionProduct.objects.filter(subscription=self)
        .select_related("product")
        .order_by("product__billing_priority", "product_id")
    )
    if without_discounts:
        qs = qs.exclude(product__type="D")
    return qs
```

**Benefits:**
- ✅ **Consistent Ordering**: Products always appear in the same order
- ✅ **Logical Grouping**: Ordered by billing priority first, then by product ID
- ✅ **Better UX**: Users see products in predictable, meaningful order

---

## Technical Impact

### Database Changes
- **None**: All changes are backward compatible with existing data

### API Changes
- **None**: All changes are internal implementation improvements

### Breaking Changes
- **None**: All changes maintain backward compatibility

### Performance Impact
- **Neutral to Positive**: IntegerChoices provide slightly better performance than dict() conversions
- **Positive**: Product ordering is done at database level, which is efficient

---

## Testing Recommendations

1. **Verify IntegerChoices Migration:**
   - Check that all inactivity reasons display correctly
   - Verify unsubscription types show proper labels
   - Test edge cases with invalid/null values

2. **Test UI Layouts:**
   - View subscription cards with multiple products
   - Check product/address alignment with varying product name lengths
   - Verify route display in subscriptions tab
   - Test address display in overview tab
   - Check responsive behavior on different screen sizes

3. **Verify Product Ordering:**
   - View subscriptions with multiple products
   - Confirm products appear in consistent order
   - Test with products of different billing priorities

---

## Migration Notes

No database migrations required. All changes are code-level improvements that work with existing data structures.

---

## Future Considerations

1. **Additional Choices to Modernize:**
   - Consider converting other tuple-based choices to IntegerChoices/TextChoices
   - Examples: `EDUCATION_CHOICES`, `FREQUENCY_CHOICES`, `PRIORITY_CHOICES`, etc.

2. **UI Consistency:**
   - Apply similar layout improvements to other list views
   - Consider standardizing product/address display patterns across all templates

3. **Route Information:**
   - Consider adding route information to Address model if needed for overview display
   - Alternatively, enhance overview to show subscription-specific addresses with routes
