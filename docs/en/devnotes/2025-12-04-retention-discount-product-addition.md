# Retention Discount Enhancement: Product Addition Support

**Date:** 2025-12-04
**Type:** Feature Enhancement
**Component:** Subscription Management, Retention System
**Impact:** Manager Workflow, Retention Strategy

## Summary

Enhanced the retention discount system to support adding new subscription products during the retention process, in addition to the existing ability to add discounts and remove products. This makes the retention workflow more flexible by allowing customers to change their subscription products while accepting retention discounts.

## Motivation

The existing retention discount system (implemented 2025-12-01) allowed managers to:

- Add retention discounts
- Remove existing products

However, in real retention scenarios, customers often want to **change products** rather than just receive discounts. For example:

- **Downgrade scenario:** Customer with 5-day subscription wants to switch to 3-day + discount
- **Product switch:** Customer wants to change from print to digital + discount
- **Upgrade with discount:** Customer wants to add products with a retention discount

Previously, managers had to:

1. Use the retention discount view (limited to discounts + removals)
2. Then separately use product_change view to add products
3. This required two separate workflows and was confusing

## Implementation

### 1. View Enhancement: `add_retention_discount`

**File:** `support/views/subscriptions.py`

#### A. Removed Target Product Filtering

**Before:**

```python
# Only showed discounts for specific products in the subscription
retention_products = Product.objects.filter(
    type__in=["D", "P", "A"],
    discount_category="R",
    active=True
).exclude(
    id__in=existing_discount_ids
).filter(
    Q(target_product_id__in=all_target_product_ids) | Q(target_product__isnull=True)
)
```

**After:**

```python
# Shows ALL available retention discounts
retention_products = (
    Product.objects.filter(type__in=["D", "P", "A"], discount_category="R", active=True)
    .exclude(id__in=existing_discount_ids)
)
```

**Rationale:**

- More flexible for special retention cases
- Managers can offer any available retention discount
- Customer needs may not match the predefined target_product relationships

#### B. Added Offerable Products

```python
# Get subscription products that the customer doesn't have yet
offerable_products = Product.objects.filter(offerable=True, type="S").exclude(
    id__in=old_subscription.products.values_list("id")
)
```

#### C. Enhanced POST Processing

**New product addition handling:**

```python
# Get new products to add
new_products_ids_list = []
for key in request.POST.keys():
    if key.startswith("activateproduct-"):
        product_id = key.split("-")[1]
        new_products_ids_list.append(product_id)

# Get seller for new products
seller_id = request.user.seller_set.first().id if request.user.seller_set.exists() else None

# Add new subscription products
for product_id in new_products_ids_list:
    product = Product.objects.get(pk=product_id)
    if product not in new_subscription.products.all():
        new_subscription.add_product(
            product=product,
            seller_id=seller_id,
            address=None,
        )
```

**Key Features:**

- Tracks seller for commission purposes
- Preserves seller information for new products
- Allows address configuration in next step

#### D. Improved Validation

**Before:**

```python
# Could not remove all products
if len(subscription_products_to_remove) >= len(subscription_products):
    messages.error(request, "Cannot remove all subscription products")
```

**After:**

```python
# Can remove all products IF adding new ones
if len(subscription_products_to_remove) >= len(subscription_products) and not new_products_ids_list:
    messages.error(
        request,
        "You cannot remove all subscription products without adding new ones. "
        "At least one subscription product must remain (discounts alone are not enough)."
    )
```

**Validation Logic:**

```python
# Validate that at least one action is being taken
if not selected_discount_ids and not products_to_remove and not new_products_ids_list:
    messages.error(
        request,
        "Please select at least one retention discount, add new products, "
        "or mark products to remove"
    )
```

#### E. Redirect to Edit Subscription

**Before:**

```python
# Redirected to contact detail
return HttpResponseRedirect(
    reverse("contact_detail", args=[old_subscription.contact.id])
)
```

**After:**

```python
# Redirects to edit subscription page to configure addresses
url = reverse("edit_subscription", args=[new_subscription.contact.id, new_subscription.id])
url_params = ""
if request.GET.get("url", None):
    url_params += f"&url={request.GET['url']}"
if request.GET.get("offset", None):
    url_params += f"&offset={request.GET['offset']}"
if request.GET.get("new", None):
    url_params += f"&new={request.GET['new']}"
if request.GET.get("act", None):
    url_params += f"&act={request.GET['act']}"
if url_params.startswith("&"):
    url_params = "?" + url_params[1:]

return HttpResponseRedirect(url + url_params)
```

**Benefits:**

- Allows address configuration for new products
- Consistent with `product_change` workflow
- Preserves seller console navigation parameters
- Enables final review before activating subscription

### 2. Template Enhancement: `add_retention_discount.html`

**File:** `support/templates/add_retention_discount.html`

#### A. New Product Addition Section

```html
<div class="form-group">
  <label>{% trans "Add these products" %} ({% trans "optional" %})</label>
  {% if offerable_products %}
    {% for product in offerable_products %}
      <div class="form-check">
        <input id="activateproduct-{{ product.id }}"
               class="enable-product form-check-input"
               type="checkbox"
               name="activateproduct-{{ product.id }}">
        <label class="form-check-label" for="activateproduct-{{ product.id }}">
          {{ product.name }}
          {% if product.price %}({{ product.price }}){% endif %}
        </label>
      </div>
    {% endfor %}
  {% else %}
    <p class="text-muted">
      <small>{% trans "No additional products available (customer already has all offerable products)" %}</small>
    </p>
  {% endif %}
</div>
```

#### B. Updated Instructions

**Enhanced instructions to include:**

1. Select retention discounts
2. **Add new products (optional)** ← NEW
3. Remove products (optional)
4. Set start date
5. Add petition channel and notes

**Important notes updated:**

- "You must select at least one retention discount, add new products, OR mark products to remove"
- "You cannot remove all subscription products without adding new ones"
- "Adding new products is optional and useful when the customer wants to change their subscription during retention"

#### C. Enhanced JavaScript Validation

```javascript
function activateSend() {
  var hasRetentionDiscount = $(".enable-discount:checked").length > 0;
  var hasNewProducts = $(".enable-product:checked").length > 0;
  var hasProductRemoval = $(".remove-product:checked").length > 0;

  var totalSubscriptionProducts = $(".remove-product[data-product-type='S']").length;
  var removedSubscriptionProducts = $(".remove-product[data-product-type='S']:checked").length;
  var addedSubscriptionProducts = $(".enable-product:checked").length;

  // Allow removing all products IF adding new ones
  if (removedSubscriptionProducts >= totalSubscriptionProducts &&
      totalSubscriptionProducts > 0 &&
      addedSubscriptionProducts === 0) {
    disable = true;
    $("#custom_error_message").text("Cannot remove all subscription products without adding new ones");
  }
  // Require at least one action
  else if (!hasRetentionDiscount && !hasProductRemoval && !hasNewProducts) {
    disable = true;
    $("#custom_error_message").text("Select at least one retention discount, add new products, or mark products to remove");
  }
}
```

**CSS Class Separation:**

- Discounts: `enable-discount` (changed from `enable-product`)
- New products: `enable-product`
- Improves code clarity and maintainability

## Use Cases

### Scenario 1: Product Change with Discount

**Customer situation:**

- Current: 5-day print subscription ($100/month)
- Wants: 3-day print + 50% discount ($35/month)

**Manager workflow:**

1. Open retention discount view
2. Remove: Monday and Tuesday products
3. Add: 50% retention discount
4. Set start date
5. Submit → Redirects to edit subscription
6. Configure addresses for remaining products
7. Activate subscription

### Scenario 2: Upgrade with Retention Discount

**Customer situation:**

- Current: Digital only ($20/month)
- Wants: Digital + Monday print + discount ($30/month)

**Manager workflow:**

1. Open retention discount view
2. Keep: Digital product
3. Add: Monday print product
4. Add: 30% retention discount
5. Set start date
6. Submit → Redirects to edit subscription
7. Configure address for Monday print
8. Activate subscription

### Scenario 3: Downgrade with Product Switch

**Customer situation:**

- Current: 5-day print ($100/month)
- Wants: Digital only + 50% discount for 3 months ($10/month)

**Manager workflow:**

1. Open retention discount view
2. Remove: All print products
3. Add: Digital product
4. Add: 50% retention discount (3 months)
5. Set start date
6. Submit → Redirects to edit subscription
7. Review and activate

### Scenario 4: Traditional Discount Only (Original Behavior)

**Customer situation:**

- Current: 3-day print ($60/month)
- Wants: Same products + 20% discount ($48/month)

**Manager workflow:**

1. Open retention discount view
2. Keep: All existing products
3. Add: 20% retention discount
4. Set start date
5. Submit → Redirects to edit subscription
6. Review and activate

## Technical Details

### Variable Naming

- `selected_discount_ids`: IDs of retention discounts to add
- `new_products_ids_list`: IDs of new subscription products to add
- `products_to_remove`: Products marked for removal

### Seller Tracking

```python
seller_id = request.user.seller_set.first().id if request.user.seller_set.exists() else None
```

- New products are assigned to the current user's seller
- Preserves commission tracking
- Falls back to None if user has no seller

### URL Parameter Preservation

The redirect preserves seller console navigation parameters:

- `url`: Return URL for seller console
- `offset`: Pagination offset
- `new`: New contact flag
- `act`: Activity flag

This ensures seamless navigation when using retention discounts from the seller console.

## Benefits

### For Managers

- ✅ **Single Workflow:** One view for all retention actions
- ✅ **More Flexibility:** Can handle complex retention scenarios
- ✅ **Better UX:** Clear instructions and validation
- ✅ **Address Configuration:** Redirects to edit page for new products

### For Customers

- ✅ **More Options:** Can change products during retention
- ✅ **Faster Resolution:** Manager can handle everything in one session
- ✅ **Better Retention:** More likely to stay with flexible options

### For Business

- ✅ **Higher Retention:** More tools to keep customers
- ✅ **Better Tracking:** Seller commissions tracked correctly
- ✅ **Audit Trail:** All changes properly logged
- ✅ **Reporting:** Can track retention success by product changes

## Compatibility

- ✅ **Backward Compatible:** Original discount-only workflow still works
- ✅ **Template Reuse:** Same template for base and custom implementations
- ✅ **Seller Console:** Preserves navigation parameters
- ✅ **Logistics:** Integrates with existing logistics module if installed

## Files Modified

1. **Backend: `support/views/subscriptions.py`**
   - Removed target_product filtering
   - Added offerable_products support
   - Enhanced POST processing for new products
   - Improved validation logic
   - Changed redirect to edit_subscription

2. **Frontend: `support/templates/add_retention_discount.html`**
   - Added product addition section
   - Updated instructions
   - Enhanced JavaScript validation
   - Separated CSS classes for clarity

## Testing Recommendations

### Retention Scenarios

1. ✅ Add discount only (original behavior)
2. ✅ Add discount + remove products
3. ✅ Add discount + add products
4. ✅ Add discount + add and remove products
5. ✅ Remove all products + add new ones (should work)
6. ✅ Remove all products without adding (should fail)

### Navigation

1. ✅ Verify redirect to edit_subscription
2. ✅ Verify URL parameters preserved
3. ✅ Verify seller console navigation works
4. ✅ Verify breadcrumbs correct

### Seller Tracking recommendations

1. ✅ Verify new products assigned to current seller
2. ✅ Verify existing products keep original seller
3. ✅ Verify commission tracking works

### Edge Cases

1. ✅ Customer already has all offerable products
2. ✅ No retention discounts available
3. ✅ User has no seller configured
4. ✅ Subscription already has end date

## Migration Notes

- **No database changes required**
- **No data migration needed**
- **Template changes backward compatible**
- **View changes maintain existing API**

## Future Enhancements

1. **Address Validation:** Alert if new products missing addresses
2. **Price Preview:** Show calculated price before saving
3. **Change History:** Track what products were added/removed
4. **Success Metrics:** Report on retention success by product changes
5. **Bulk Operations:** Handle multiple subscriptions at once

---

**Related Changes:**

- 2025-12-01: Initial retention discount system implementation
- 2025-12-04: Enhanced with product addition support

**Documentation:**

- User guide updated with new workflow
- Manager training materials updated
- Seller console documentation updated
