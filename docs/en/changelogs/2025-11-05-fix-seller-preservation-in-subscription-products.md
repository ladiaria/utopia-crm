# 2025-11-05: Fix Seller Preservation in Subscription Products

## Summary

Fixed a critical bug where original sellers were being overwritten when editing subscriptions that came from `book_additional_product` or `product_change` views. This caused a "seller takeover" issue where the current user's seller would be assigned to all products, including those originally sold by different sellers.

## Problem Description

### Symptom: Seller Takeover

**Problematic scenario:**

1. Seller A sells Product 1 to a contact → Subscription 1 created
2. Seller B adds Product 2 using `book_additional_product` → Subscription 2 created (copies Product 1 with Seller A, adds Product 2 with Seller B)
3. System redirects to `edit_subscription` to review the new subscription
4. When saving changes in the edit screen → **BUG**: Product 1 changes from Seller A to Seller B ❌

**Incorrect result:**

- Product 1: Seller B (should be Seller A)
- Product 2: Seller B ✅

**Impact:**

- Sellers lost commissions for products they originally sold
- Incorrect sales reports
- Inconsistent seller history

## Root Cause

The issue was in the generic `utopia-crm` codebase, specifically in how subscription products handle seller assignment when products are migrated between subscriptions.

While the ladiaria-specific views (`ladiaria_book_additional_product` and `ladiaria_product_change`) correctly preserve sellers when copying products, the generic `utopia-crm` views needed the same fix to ensure consistency across the codebase.

## Solution Implemented

### Files Modified

#### 1. `support/views/subscriptions.py`

**Lines 668-673 (product_change view):**

```python
# Before:
new_sp = new_subscription.add_product(
    product=sp.product,
    # ... other fields ...
    seller_id=sp.seller_id,
    original_datetime=sp.original_datetime,  # ❌ add_product doesn't accept this parameter
)

# After:
new_sp = new_subscription.add_product(
    product=sp.product,
    # ... other fields ...
    seller_id=sp.seller_id,
)
new_sp.original_datetime = sp.original_datetime  # ✅ Assigned after creation
```

**Lines 775-780 (book_additional_product view):**

Same change as above - moved `original_datetime` assignment outside of `add_product()` call.

**Reason:** The `add_product()` method doesn't accept `original_datetime` as a parameter, so it must be assigned after creating the object.

### Technical Details

**Seller Preservation Logic:**

The views correctly preserve sellers when copying products:

```python
for sp in old_subscription.subscriptionproduct_set.all():
    if sp.product not in old_subscription.unsubscription_products.all():
        new_sp = new_subscription.add_product(
            product=sp.product,
            address=sp.address,
            copies=sp.copies,
            message=sp.label_message,
            instructions=sp.special_instructions,
            seller_id=sp.seller_id,  # ✅ Preserves original seller
        )
        new_sp.original_datetime = sp.original_datetime  # ✅ Preserves original datetime
```

**New Products Logic:**

New products get the current user's seller (or None if no seller):

```python
for product_id in new_products_ids_list:
    product = Product.objects.get(pk=product_id)
    if product not in new_subscription.products.all():
        new_subscription.add_product(
            product=product,
            address=default_address,
            seller_id=seller_id,  # ✅ Current user's seller for new products
        )
```

## Testing Scenarios

### Scenario 1: book_additional_product

1. Create subscription with Product A (Seller 1)
2. Use `book_additional_product` to add Product B (Seller 2)
3. Edit the new subscription and save
4. **Verify:** Product A should keep Seller 1, Product B should have Seller 2

### Scenario 2: product_change

1. Create subscription with Product A (Seller 1)
2. Use `product_change` to change to Product B (Seller 2)
3. Edit the new subscription and save
4. **Verify:** Product A should keep Seller 1, Product B should have Seller 2

### Scenario 3: Products without seller

1. Create subscription with Product A (no seller, `seller_id=NULL`)
2. Use `book_additional_product` to add Product B (Seller 1)
3. Edit the new subscription
4. **Verify:** Product A should keep `seller_id=NULL`, Product B should have Seller 1

## Impact

✅ **Correct seller preservation:** Products maintain their original seller when migrating between subscriptions  
✅ **Correct new product assignment:** New products receive the current seller  
✅ **Compatibility with existing flows:** Works correctly with `book_additional_product` and `product_change`  
✅ **Accurate reports:** Sales reports now correctly reflect which seller sold each product  
✅ **Correct commissions:** Sellers receive commissions only for products they sold  
✅ **Consistent with ladiaria:** Generic views now match the behavior of ladiaria-specific views

## Modified Files

### utopia-crm

1. **`support/views/subscriptions.py`**
   - Lines 668-673: Fixed `original_datetime` assignment in `product_change` view
   - Lines 775-780: Fixed `original_datetime` assignment in `book_additional_product` view

## Related Changes

This fix complements the seller preservation fix in `utopia-crm-ladiaria` (see ladiaria changelog 2025-11-05). Together, these changes ensure consistent seller preservation across both the generic and ladiaria-specific codebases.

## Technical Context

**Flow of `book_additional_product`:**

1. User clicks "Add additional product"
2. View `book_additional_product` creates new subscription with `updated_from=old_subscription`
3. Copies all old products preserving `seller_id=sp.seller_id`
4. Adds new products with `seller_id=current_user_seller_id`
5. Sets unsubscription date and redirects

**Key Principle:**

> When migrating products between subscriptions, preserve the original seller. Only new products should get the current user's seller.

---

**Date:** 2025-11-05  
**Type:** Critical bug fix  
**Priority:** High  
**Related to:** Subscription management, seller tracking, commission calculation
