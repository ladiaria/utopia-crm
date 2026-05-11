# Fix: SalesRecord Validation Overwrites Unrelated Subscription Product Sellers

- **Date:** 2026-05-08
- **Author:** Tanya Tree + Claude Sonnet 4.6
- **Ticket:** t1143
- **Type:** Bug Fix
- **Component:** Support — Sales Registry, Subscriptions
- **Impact:** Data Integrity, Commission Calculation

## 🎯 Summary

When a manager validated a `SalesRecord` with the "can be commissioned" checkbox enabled, a bulk `UPDATE` query was replacing the `seller` field on **every** type-S `SubscriptionProduct` belonging to that subscription — including products that had nothing to do with the sale being validated. In subscriptions that had gone through a product-change or additional-product flow (which produce partial `SalesRecord` entries covering only the newly added products), this silently reassigned the original seller of pre-existing products to the validating seller. The same bug existed in `SalesRecordCreateView`, which creates a `SalesRecord` manually for subscriptions that had none. The fix narrows both bulk updates to target only the `SubscriptionProduct` rows whose products are explicitly listed in `sales_record.products`, matching the semantic intent of the operation.

## ✨ Changes

### 1. Narrow the seller bulk-update in `ValidateSubscriptionSalesRecord`

**File:** `support/views/all_views.py`

The original filter used `product__type="S"` to select all subscription products, regardless of whether they appeared in the sales record being validated:

```python
# Before — overwrites all type-S products on the subscription
SubscriptionProduct.objects.filter(
    subscription=subscription, product__type="S"
).update(seller=sales_record.seller)
```

The fix filters by `product__in=sales_record.products.all()`, so only the products explicitly attached to this particular `SalesRecord` are touched:

```python
# After — touches only the products in this specific SalesRecord
SubscriptionProduct.objects.filter(
    subscription=subscription, product__in=sales_record.products.all()
).update(seller=sales_record.seller)
```

### 2. Same fix in `SalesRecordCreateView`

**File:** `support/views/all_views.py`

`SalesRecordCreateView.form_valid` contained an identical overly-broad bulk update immediately after assigning all type-S products of the subscription to the new record. Applied the same narrowing fix:

```python
# After — uses the M2M already populated by products.set() above
SubscriptionProduct.objects.filter(
    subscription=subscription, product__in=sales_record_obj.products.all()
).update(seller=sales_record_obj.seller)
```

Note: in `SalesRecordCreateView`, `products.set()` is called with `self.subscription.products.filter(type="S")` on the line immediately before the update, so in practice the old and new queries produce the same result for that view. The fix is applied for correctness and symmetry regardless.

### 3. Regression tests

**File:** `tests/test_product_change_seller.py`

A new `TestValidateSalesRecordSellerPreservation` test class was added with two scenarios:

- **`test_validate_sale_only_updates_sellers_in_sr`**: subscription has two products with different sellers; the `SalesRecord` covers only one of them. Verifies that validating the record updates the seller only on the covered product and leaves the other unchanged.
- **`test_validate_sale_does_not_overwrite_unrelated_sp_sellers`**: same setup, but the `SalesRecord` covers the second product with a different seller than the first. Verifies that the first product's seller is not touched.

Both tests were written before the fix was applied and confirmed to fail, then verified to pass after the fix.

## 📁 Files Modified

- **`support/views/all_views.py`** — Narrowed the `SubscriptionProduct` bulk-update filter in `ValidateSubscriptionSalesRecord.form_valid` and `SalesRecordCreateView.form_valid`
- **`tests/test_product_change_seller.py`** — Added `TestValidateSalesRecordSellerPreservation` with two regression tests; added `SalesRecord` to imports

## 📚 Technical Details

**Why the bug was rarely visible in practice:**

The takeover only manifested in subscriptions with products belonging to more than one seller — a state that arises after product-change or additional-product flows. A brand-new FULL subscription always has a single seller across all its products, so validating its `SalesRecord` produced no observable difference even with the broad filter.

Additionally, `SalesRecordCreateView` assigns `sr.products = all type-S products on the subscription` before running the update, making old and new filters equivalent for that path. The only dangerous path was `ValidateSubscriptionSalesRecord` being used to validate a PARTIAL `SalesRecord` (created by `product_change`, `additional_product`, or `edit_subscription` edit flows) on a subscription that still carried products from an earlier seller.

**Why FULL sales were never affected:**

A FULL `SalesRecord` is created at subscription creation time and covers all products on the subscription. When `can_be_commissioned` is checked at validation, the seller is the same one already on all SPs, so the update is a no-op from a data-correctness perspective.

**Relationship to t1142:**

t1142 fixed seller takeover in the `edit_subscription` POST flow (via `capture_variables` / `process_subscription_products` in the ladiaria mixin). t1143 closes the remaining path: the validation step, which could undo t1142's preserved sellers if a manager validated a partial sale after editing.

## 🧪 Manual Testing

1. **Happy path — validate a full sale, all sellers remain correct:**
   - Create a new subscription with two type-S products, both sold by Seller A.
   - Validate the resulting FULL `SalesRecord` with `can_be_commissioned` checked and Seller A as seller.
   - **Verify:** Both `SubscriptionProduct` rows still show Seller A as seller.

2. **Happy path — validate a partial sale, only covered products are updated:**
   - Create a subscription with two type-S products: product 1 → Seller A, product 2 → Seller B.
   - Simulate a product-change or edit-subscription flow that creates a PARTIAL `SalesRecord` covering only product 2, with Seller B.
   - Go to `support/validate_sale/<sr_id>/`, check `can_be_commissioned`, confirm seller is Seller B, and submit.
   - **Verify:** `SubscriptionProduct` for product 2 shows Seller B. `SubscriptionProduct` for product 1 still shows Seller A (unchanged).

3. **Edge case — partial sale where the SalesRecord seller differs from the original SP seller:**
   - Same setup as scenario 2, but the `SalesRecord` seller is Seller C (e.g. a manager who took over the call).
   - Validate with `can_be_commissioned` checked, Seller C as seller.
   - **Verify:** product 2's SP seller is updated to Seller C. product 1's SP seller remains Seller A.

4. **Edge case — `can_be_commissioned` unchecked, no sellers are modified:**
   - Repeat scenario 2 but leave the checkbox unchecked.
   - **Verify:** Both `SubscriptionProduct` sellers are unchanged after validation.

## 📝 Deployment Notes

- No database migrations required.
- No configuration changes required.
- The fix is purely logic-level: the SQL `UPDATE` query is narrowed by an additional `IN` subquery over `sales_record.products`. No data is backfilled; previously taken-over sellers in production must be corrected using the existing `detect_seller_takeovers` management command if needed.

## 🎓 Design Decisions

The fix does not attempt to determine whether the existing SP seller "should" be preserved or overwritten — it simply restricts the update to products the `SalesRecord` explicitly covers. This matches the semantic meaning of the operation: "the seller who sold these specific products gets credit for them." Products not in the record were sold (or transferred) through a different transaction and should not be touched.

An alternative considered was removing the bulk-update entirely and relying solely on the seller field already set on each SP at creation time. This was rejected because the validate-sale flow is intentionally designed to let a manager correct or confirm who should receive commission for a sale — the seller on the `SalesRecord` may legitimately differ from the one set at product creation (e.g. a supervisor reassigned a call). The narrowed update preserves that flexibility while scoping it correctly.

## 🚀 Future Improvements

- Add an audit log to `SubscriptionProduct` to track seller field changes over time, making it easier to detect and diagnose any future takeover-style bugs without running a management command.
- Consider whether `ValidateSubscriptionSalesRecord` should display a warning when the `SalesRecord.seller` differs from the existing SP sellers for covered products, so the manager can confirm the change intentionally rather than applying it silently.

---

**Date:** 2026-05-08
**Author:** Tanya Tree + Claude Sonnet 4.6
**Branch:** t1143
**Type:** Bug Fix
**Modules affected:** Support, Sales Registry
