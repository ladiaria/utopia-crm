# SalesRecord Creation for Product Change, Additional Product, and Retention Flows

- **Date:** 2026-04-24
- **Author:** Tanya Tree + Claude Sonnet 4.6
- **Ticket:** t1126
- **Type:** Bug Fix | Enhancement
- **Component:** Support — Subscriptions, Sales Registry
- **Impact:** Data Integrity, Operator Workflow, Commission Calculation

## 🎯 Summary

The `SalesRecordFilterManagersView` (the manager sales filter at `support/sales_record_filter/`) was not showing sales made through product change, additional product, or retention discount flows because those views never created `SalesRecord` objects. Only new-subscription and edit-subscription flows created records. This ticket fixes all three missing flows in both the base app and the ladiaria customisation layer, standardises how partial sales records are created in the ladiaria `edit_subscription` view (one record per session instead of one per product), fixes an `AttributeError` bug caused by a wrong attribute path, and improves the validate-sale UX by defaulting the commission checkbox to checked with an explanatory note.

## ✨ Changes

### 1. SalesRecord creation added to `product_change` (base and ladiaria)

**Files:** `support/views/subscriptions.py`, `utopia_crm_ladiaria/views/subscriptions.py`

Both `product_change` (base) and `ladiaria_product_change` now create one PARTIAL `SalesRecord` on the new subscription, containing only the newly activated type-`S` products. The price is the difference between the new and old subscription prices, matching the pattern already used by `book_additional_product`.

```python
sf = SalesRecord.objects.create(
    subscription=new_subscription,
    seller_id=seller_id,
    price=new_subscription.get_price_for_full_period() - old_subscription.get_price_for_full_period(),
    sale_type=SalesRecord.SALE_TYPE.PARTIAL,
)
sf.products.add(*new_products_list)  # only type "S" products
if not seller_id:
    sf.set_generic_seller()
```

### 2. SalesRecord creation added to `add_retention_discount` (base and ladiaria)

**Files:** `support/views/subscriptions.py`, `utopia_crm_ladiaria/views/retention.py`

Both `add_retention_discount` (base) and `ladiaria_add_retention_discount` now create one PARTIAL `SalesRecord`. Retention discount products (type `D`, `P`, or `A`) are intentionally excluded — only newly added subscription products (type `S`) are linked to the record, because discount products have no independent sale value.

### 3. `edit_subscription` partial sales: one record per session (ladiaria)

**File:** `utopia_crm_ladiaria/views/subscriptions.py` — `LadiariaSubscriptionMixin.process_subscription_products`

Previously, each newly added product inside an edit-subscription POST created its own `SalesRecord` with default type FULL. This was inconsistent with the other partial-sale flows and produced cluttered records when adding two or more products at once.

The method was refactored: the per-product record creation was removed from inside the loop; instead, all newly added type-`S` products are collected and a single PARTIAL `SalesRecord` is created after the loop, with the price set to the sum of the individual product prices:

```python
if self.edit_subscription and added_subscription_products:
    price = sum(p.price for p in added_subscription_products)
    sf = SalesRecord.objects.create(
        subscription=subscription,
        seller_id=self.user_seller_id,
        price=price,
        sale_type=SalesRecord.SALE_TYPE.PARTIAL,
        campaign=self.campaign,
    )
    sf.products.add(*added_subscription_products)
    if not self.user_seller_id:
        sf.set_generic_seller()
```

No record is created if no new subscription products were added (e.g. the user only updated addresses).

### 4. Bug fix: `SalesRecord.TYPES.PARTIAL` → `SalesRecord.SALE_TYPE.PARTIAL`

**File:** `support/views/subscriptions.py` — `book_additional_product`

The attribute `SalesRecord.TYPES` does not exist; the correct path is `SalesRecord.SALE_TYPE`. The existing call would raise an `AttributeError` at runtime. Fixed to use `SalesRecord.SALE_TYPE.PARTIAL`.

### 5. Validate-sale form: `can_be_commissioned` defaults to checked

**Files:** `support/views/all_views.py`, `support/templates/validate_subscription_sales_record.html`

`ValidateSubscriptionSalesRecord.get_initial` previously forced `can_be_commissioned=False` for any non-FULL sale, which meant partial sales (product changes, retentions) would never appear as commissionable by default. The explicit override was removed; the field now relies on the model's own default (`True`).

An explanatory note was added below the checkbox in the template:

> "If checked, the seller will receive commission for this sale. Uncheck to exclude it from commission calculations (e.g. retention discounts or non-commissionable changes)."

### 6. Unit tests extended

**Files:** `utopia_crm_ladiaria/tests/test_seller_registry.py`, `utopia_crm_ladiaria/tests/test_product_change_views.py`, `utopia_crm_ladiaria/tests/test_retention_view.py`

- **`TestSellerRegistryFullSalesRecord`** (13 new cases): covers new-subscription FULL records (count, products, seller, price, type) and edit-subscription PARTIAL records (one per session, only new products, correct price sum, type, discount products excluded, no-seller flow).
- **`TestProductChangeSalesRecord`** (8 new cases): covers `ladiaria_product_change` and `ladiaria_book_additional_product` — record created, correct products, seller assigned, type PARTIAL.
- **`TestRetentionDiscountSalesRecord`** (7 new cases): covers `ladiaria_add_retention_discount` — record created, discount products excluded, type-S products included, seller assigned, type PARTIAL, no record on failed validation.

## 📁 Files Modified

- **`support/views/subscriptions.py`** — Added `SalesRecord` creation to `product_change` and `add_retention_discount`; fixed `TYPES.PARTIAL` bug in `book_additional_product`
- **`support/views/all_views.py`** — Removed forced `can_be_commissioned=False` in `ValidateSubscriptionSalesRecord.get_initial`
- **`support/templates/validate_subscription_sales_record.html`** — Added explanatory note for the `can_be_commissioned` checkbox
- **`utopia_crm_ladiaria/views/subscriptions.py`** — Added `SalesRecord` creation to `ladiaria_product_change`; refactored `process_subscription_products` to create one PARTIAL record per edit session
- **`utopia_crm_ladiaria/views/retention.py`** — Added `SalesRecord` creation to `ladiaria_add_retention_discount`
- **`utopia_crm_ladiaria/tests/test_seller_registry.py`** — New `TestSellerRegistryFullSalesRecord` class with 13 test cases
- **`utopia_crm_ladiaria/tests/test_product_change_views.py`** — New `TestProductChangeSalesRecord` class with 8 test cases
- **`utopia_crm_ladiaria/tests/test_retention_view.py`** — New `TestRetentionDiscountSalesRecord` class with 7 test cases

## 📚 Technical Details

- Only type-`S` (subscription) products are linked to `SalesRecord.products` in partial flows. Discount products (type `D`, `P`, `A`) are explicitly filtered out because they do not represent independently sold items and would distort commission calculations.
- `set_generic_seller()` is always called when no seller ID is available, consistent with all other `SalesRecord` creation points in the codebase.
- The base app views (`product_change`, `add_retention_discount`) were also fixed even though they are overridden by ladiaria URLs, to keep the base package correct for other deployments.
- All 55 tests across the three test files pass after the changes.

## 🧪 Manual Testing

1. **Happy path — product change by a seller creates a visible sales record:**
   - Log in as a user with an associated `Seller`.
   - Open a contact with an active subscription and go to the product change view.
   - Select a new product to add and submit.
   - Navigate to `support/sales_record_filter/` as a manager.
   - **Verify:** The new PARTIAL sales record appears in the list, linked to the new subscription and showing only the newly added product(s).

2. **Happy path — retention discount creates a sales record with only type-S products:**
   - Apply a retention discount (type `D`) plus one new subscription product (type `S`) via the retention view.
   - Check the sales filter.
   - **Verify:** The record shows the type-`S` product; the discount product does not appear.

3. **Happy path — validate-sale form defaults to commissionable:**
   - Open the validate-sale page for a PARTIAL sale.
   - **Verify:** The `can_be_commissioned` checkbox is checked by default.
   - Read the explanatory note below it.
   - **Verify:** The note explains what enabling/disabling the checkbox implies.

4. **Edge case — edit subscription adding two products creates one record, not two:**
   - Edit an existing subscription and add two new products in the same POST.
   - Check `SalesRecord.objects.filter(subscription=...)`.
   - **Verify:** Exactly one record exists; both products are linked to it; the price equals the sum of both product prices.

5. **Edge case — edit subscription with no new products creates no record:**
   - Edit an existing subscription and change only an address (no new products).
   - **Verify:** No new `SalesRecord` is created.

6. **Edge case — product change by a user without a seller still creates a record:**
   - Log in as a superuser with no associated `Seller`.
   - Run a product change.
   - **Verify:** A `SalesRecord` is created with a generic seller (or seller set via `set_generic_seller()`).

## 📝 Deployment Notes

- No database migrations required.
- No configuration changes required.
- After deploying, existing subscriptions that went through product-change or retention flows before this fix will not retroactively have `SalesRecord` entries. If historical records are needed for those subscriptions, they can be created manually via the existing `SalesRecordCreateView` (`support/create_sales_record/<subscription_id>/`).

## 🎓 Design Decisions

Discount products are excluded from `SalesRecord.products` because a retention discount applied to a subscription is not a sale — it is a price reduction. Including it would inflate product counts in commission calculations and campaign statistics. The seller is still recorded on the record (and commissions can be calculated at validation time) based on the subscription price difference, which already accounts for discounts.

One PARTIAL record per edit session (rather than one per product) aligns with how the other partial-sale views work and avoids cluttering the manager sales filter with multiple near-identical records when a seller adds a bundle of products at once. The price is the sum of the individual product prices, which is correct for a monthly subscription where each product has an independent price.

## 🚀 Future Improvements

- The `SalesRecordFilterManagersView` could expose a "sale type" filter column so managers can distinguish FULL vs PARTIAL records at a glance without opening each one.
- Consider surfacing the `can_be_commissioned` default differently based on sale type (e.g. a visual warning for retention records) rather than relying solely on the manager to uncheck it.

---

- **Date:** 2026-04-24
- **Author:** Tanya Tree + Claude Sonnet 4.6
- **Branch:** t1126
- **Type:** Bug Fix | Enhancement
- **Modules affected:** Support, Sales Registry
