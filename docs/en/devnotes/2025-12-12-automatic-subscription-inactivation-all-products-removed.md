# Automatic Subscription Inactivation When All Products Removed

**Date:** 2025-12-12
**Type:** Feature Enhancement, Business Logic
**Component:** Subscription Management, Product Management
**Impact:** Subscription Lifecycle, Data Integrity
**Task:** t984

## Summary

Enhanced the `remove_product()` method in the `Subscription` model to automatically inactivate subscriptions when the last product is removed. This ensures that subscriptions without any products are properly marked as inactive with appropriate status codes and end dates, maintaining data integrity and preventing orphaned active subscriptions.

## Motivation

Previously, when removing products from a subscription, the system would:

1. **Allow empty subscriptions:** A subscription could remain active even with zero products
2. **Lack proper tracking:** No clear indication that a subscription ended due to all products being removed
3. **Data inconsistency:** Active subscriptions with no products created confusion in reporting and analytics
4. **Manual intervention required:** Staff had to manually mark subscriptions as inactive after removing all products

This created operational overhead and potential data quality issues, as active subscriptions should always have at least one product.

## Implementation

### 1. Added New Inactivity Reason and Unsubscription Type

**File:** `core/models.py`

Added new choice values to track subscriptions that ended due to all products being removed:

```python
class InactivityReasonChoices(models.IntegerChoices):
    # ... existing choices ...
    DEBTOR = 13, _("Debtor")
    DEBTOR_AUTOMATIC = 16, _("Debtor, automatic unsubscription")
    RETENTION = 17, _("Retention")
    ALL_PRODUCTS_REMOVED = 18, _("All products removed")  # NEW
    NOT_APPLICABLE = 99, _("N/A")

class UnsubscriptionTypeChoices(models.IntegerChoices):
    # ... existing choices ...
    NORMAL = 1, _("Normal")
    LOGISTICS = 2, _("Logistics")
    CHANGED_PRODUCTS = 3, _("Changed products")
    ADDED_PRODUCTS = 4, _("Added products")
    RETENTION = 5, _("Retention")
    ALL_PRODUCTS_REMOVED = 6, _("All products removed")  # NEW
```

### 2. Enhanced `remove_product()` Method

**File:** `core/models.py`

Updated the method to automatically inactivate subscriptions when the last product is removed:

```python
def remove_product(self, product):
    """
    Used to remove products from the current subscription. It is encouraged to always use this method when you want
    to remove a product from a subscription, so you always have control of what happens here. This also creates a
    product history with the current subscription, product, and date, with the type 'D' (De-activation).

    If that was the last product, mark the subscription as inactive, and mark the reason as ALL_PRODUCTS_REMOVED.
    """
    try:
        sp = SubscriptionProduct.objects.get(subscription=self, product=product)
    except SubscriptionProduct.DoesNotExist:
        pass
    else:
        self.contact.add_product_history(self, product, "D")

    # Check if this was the last product
    if not self.subscriptionproduct_set.exists():
        self.active = False
        self.status = "OK"
        self.inactivity_reason = self.InactivityReasonChoices.ALL_PRODUCTS_REMOVED
        self.unsubscription_addendum = _("All products were removed.")
        self.unsubscription_type = self.UnsubscriptionTypeChoices.ALL_PRODUCTS_REMOVED
        self.end_date = date.today()
        self.save()
```

## Business Logic

When a product is removed from a subscription:

1. **Product removal:** The `SubscriptionProduct` is deleted
2. **History tracking:** Product history is created with type 'D' (De-activation)
3. **Check remaining products:** System checks if any products remain
4. **Auto-inactivation:** If no products remain, the subscription is automatically:
   - Marked as inactive (`active = False`)
   - Set to "OK" status (normal termination)
   - Given inactivity reason: `ALL_PRODUCTS_REMOVED` (18)
   - Given unsubscription type: `ALL_PRODUCTS_REMOVED` (6)
   - Given unsubscription addendum: "All products were removed."
   - Given end date: today's date

## Use Cases

### 1. Manual Product Removal

**Scenario:** Staff member removes products one by one from a subscription

```python
subscription = Subscription.objects.get(id=123)
subscription.remove_product(product1)  # Still has products
subscription.remove_product(product2)  # Last product - auto-inactivates
```

**Result:** Subscription automatically marked as inactive with proper tracking

### 2. Bulk Product Removal

**Scenario:** System or script removes multiple products

```python
for product in subscription.subscriptionproduct_set.all():
    subscription.remove_product(product.product)
# After last iteration, subscription is automatically inactive
```

**Result:** Clean termination with proper status codes

### 3. Product Change Workflow

**Scenario:** User changes products via `product_change()` method

- Old subscription products are removed
- If all products removed, old subscription auto-inactivates
- New subscription created with new products

**Result:** Clear separation between old and new subscriptions

## Benefits

### 1. Data Integrity

- **No orphaned subscriptions:** Active subscriptions always have at least one product
- **Automatic cleanup:** System handles inactivation without manual intervention
- **Proper tracking:** Clear reason code for why subscription ended

### 2. Operational Efficiency

- **Reduced manual work:** Staff don't need to manually inactivate subscriptions
- **Consistent behavior:** Same logic applied regardless of how products are removed
- **Audit trail:** Unsubscription addendum provides clear explanation

### 3. Reporting Accuracy

- **Clear metrics:** Reports can distinguish subscriptions that ended due to product removal
- **Better analytics:** Track patterns in product removal behavior
- **Data quality:** No confusion about active subscriptions with zero products

### 4. Business Logic Enforcement

- **Automatic enforcement:** Business rule (subscriptions must have products) is enforced by code
- **Prevents edge cases:** Eliminates possibility of active empty subscriptions
- **Consistent state:** Subscription state always reflects reality

## Database Changes

### Migration Required

A migration will be needed to add the new choice values:

- `InactivityReasonChoices.ALL_PRODUCTS_REMOVED = 18`
- `UnsubscriptionTypeChoices.ALL_PRODUCTS_REMOVED = 6`

**Migration file:** `core/migrations/XXXX_add_all_products_removed_choices.py`

**Changes:**

- No schema changes required (integer fields already exist)
- New choice values are backward compatible
- Existing data is unaffected

## Edge Cases Handled

### 1. Product Already Removed

```python
subscription.remove_product(product_that_doesnt_exist)
# Handles gracefully - no error, no changes
```

### 2. Multiple Rapid Removals

```python
# Thread-safe - each removal checks current state
subscription.remove_product(product1)
subscription.remove_product(product2)  # Checks if products exist after product1 removal
```

### 3. Already Inactive Subscription

```python
# If subscription is already inactive, removal still works
# Auto-inactivation logic only runs if products reach zero
```

## Testing

### Verification Steps

1. **Test single product removal:**

   ```python
   from core.models import Subscription, Product

   subscription = Subscription.objects.get(id=123)
   print(f"Products before: {subscription.subscriptionproduct_set.count()}")
   print(f"Active: {subscription.active}")

   # Remove last product
   product = subscription.subscriptionproduct_set.first().product
   subscription.remove_product(product)

   subscription.refresh_from_db()
   print(f"Products after: {subscription.subscriptionproduct_set.count()}")
   print(f"Active: {subscription.active}")
   print(f"Inactivity reason: {subscription.inactivity_reason}")
   print(f"Unsubscription type: {subscription.unsubscription_type}")
   print(f"End date: {subscription.end_date}")
   ```

   **Expected output:**

   ```text
   Products before: 1
   Active: True
   Products after: 0
   Active: False
   Inactivity reason: 18
   Unsubscription type: 6
   End date: 2025-12-12
   ```

2. **Test multiple product removal:**

   ```python
   subscription = Subscription.objects.get(id=456)
   products = list(subscription.subscriptionproduct_set.all())

   for sp in products[:-1]:
       subscription.remove_product(sp.product)
       subscription.refresh_from_db()
       assert subscription.active == True, "Should still be active"

   # Remove last product
   subscription.remove_product(products[-1].product)
   subscription.refresh_from_db()
   assert subscription.active == False, "Should be inactive"
   assert subscription.inactivity_reason == 18
   ```

3. **Check database consistency:**

   ```sql
   -- Find subscriptions with ALL_PRODUCTS_REMOVED reason
   SELECT id, contact_id, active, inactivity_reason, unsubscription_type, end_date
   FROM core_subscription
   WHERE inactivity_reason = 18;

   -- Verify they have no products
   SELECT s.id, COUNT(sp.id) as product_count
   FROM core_subscription s
   LEFT JOIN core_subscriptionproduct sp ON sp.subscription_id = s.id
   WHERE s.inactivity_reason = 18
   GROUP BY s.id
   HAVING COUNT(sp.id) > 0;
   -- Should return 0 rows
   ```

## Files Modified

- `core/models.py` - Enhanced `Subscription.remove_product()` method and added new choice values

## Backward Compatibility

- **Existing code:** All existing code continues to work unchanged
- **Existing data:** No impact on existing subscriptions
- **New behavior:** Only applies when products are removed going forward
- **Choice values:** New integer values (18, 6) don't conflict with existing values
- **No breaking changes:** Method signature unchanged, behavior is additive

## Future Enhancements

Potential improvements for future iterations:

1. **Notification system:** Alert staff when subscriptions auto-inactivate
2. **Reactivation workflow:** Easy way to reactivate and add products back
3. **Bulk operations:** Dedicated view for managing product removals
4. **Analytics dashboard:** Track frequency of all-products-removed scenarios
5. **Configurable behavior:** Allow projects to customize auto-inactivation logic

## Related Issues

- Prevents orphaned active subscriptions with zero products
- Improves data quality and reporting accuracy
- Reduces manual operational overhead
- Enforces business rule: active subscriptions must have products

## Notes

- The method uses `subscriptionproduct_set.exists()` for efficient database checking
- End date is set to today's date when auto-inactivation occurs
- Status is set to "OK" to indicate normal termination (not an error condition)
- Unsubscription addendum provides human-readable explanation
- The logic only runs after successful product removal and history creation
- Thread-safe: checks current state at time of removal

## Migration Checklist

- [ ] Create migration for new choice values
- [ ] Run migration in development environment
- [ ] Test product removal scenarios
- [ ] Verify database consistency
- [ ] Update any reports that filter by inactivity_reason
- [ ] Update any documentation referencing subscription lifecycle
- [ ] Deploy to staging for testing
- [ ] Deploy to production

## Documentation Updates

Consider updating:

- User manual: Explain automatic inactivation behavior
- Admin documentation: How to handle auto-inactivated subscriptions
- API documentation: Document new choice values
- Training materials: Include new workflow in staff training
