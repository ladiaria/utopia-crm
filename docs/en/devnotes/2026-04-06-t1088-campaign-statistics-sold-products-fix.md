# Campaign Statistics: Count Sold Products Only

- **Date:** 2026-04-06
- **Author:** Tanya Tree + Claude Sonnet 4.6
- **Ticket:** t1088
- **Type:** Enhancement / Behaviour correction
- **Component:** Campaign Statistics, Sales Records
- **Impact:** Reporting accuracy

## 🎯 Summary

`CampaignStatisticsDetailView` was building its per-product count by querying `SubscriptionProduct` filtered by `subscription__campaign`. This returned all products currently on the subscription — including ones the subscriber had before the campaign sale happened. The fix replaces that query with `SalesRecord.objects.filter(campaign=...).filter(products=product)`, using the M2M field that already records only what was actually sold. The `export_csv()` method in the same view had the same issue and was fixed in the same commit. Regression tests were added in `utopia-crm-ladiaria` to document the correct behaviour.

## 🔍 Problem

When a seller uses the subscription edit view to add product C to a subscription that already has products A and B:

1. A `SalesRecord` is created with `products = {C}` only — this was already correct.
2. `subscription.campaign` is set to the current campaign (via `mark_as_sale` or `handle_direct_sale`).
3. The statistics view was querying `SubscriptionProduct` filtered by `subscription__campaign`, returning A, B, and C as "products sold in the campaign".

`SalesRecordFilterManagersView` already used `SalesRecord.products` and was correct. The inconsistency was between the two views.

## ✨ Changes

### 1. Per-product count in campaign statistics

**File:** `support/views/all_views.py`

In `get_context_data()`, the block that builds `subs_dict` now queries `SalesRecord` instead of `SubscriptionProduct`:

```python
# Before
subscription_products = SubscriptionProduct.objects.filter(
    subscription__campaign=self.campaign,
    subscription__contact_id__in=filtered_contact_ids
)
for product in Product.objects.filter(offerable=True, type="S"):
    subs_dict[product.name] = subscription_products.filter(product=product).count()

# After
sales_records = SalesRecord.objects.filter(
    campaign=self.campaign,
    subscription__contact_id__in=filtered_contact_ids,
)
for product in Product.objects.filter(offerable=True, type="S"):
    subs_dict[product.name] = sales_records.filter(products=product).count()
```

### 2. CSV export products column

**File:** `support/views/all_views.py`

In `export_csv()`, the "Products sold" column previously read `subscriptionproduct_set.all()` from the subscription. It now accumulates products from all `SalesRecord` objects for the contact in the campaign, handling the case where a contact has multiple sale records correctly.

## 📁 Files Modified

- **`support/views/all_views.py`** — `CampaignStatisticsDetailView`: `get_context_data()` and `export_csv()` updated to use `SalesRecord.products`

## 📁 Files Created

*(In utopia-crm-ladiaria — not in this repo)*

- **`utopia_crm_ladiaria/tests/test_seller_registry.py`** — Diagnostic tests for subscription views and regression test for campaign statistics

## 📚 Technical Details

`Subscription.campaign` is set by two methods in `core/models.py`:

- `Activity.mark_as_sale()` — called when a seller completes a sale from an existing activity (`?act=<id>`)
- `ContactCampaignStatus.handle_direct_sale()` — called when a seller registers a new direct sale (`?new=<ccs_id>`)

Both set `subscription.campaign = campaign` and save. This is what caused `SubscriptionProduct.objects.filter(subscription__campaign=...)` to find the subscription — and all its products, new and old.

`SalesRecord.products` is set explicitly at the time of sale: one product per record for partial sales (update view), or all selected products at once for new subscriptions (create view). This is the authoritative source for "what was sold".

## 🧪 Manual Testing

1. **Seller adds a product to an existing subscription from the campaign console:**
   - Open the campaign console for a contact who already has an active subscription with products.
   - Use "Edit subscription" and add one new product.
   - Go to Campaign Statistics → the relevant campaign.
   - **Verify:** The new product appears with count 1. Pre-existing products show count 0 for this campaign.

2. **Edge case — contact has multiple sale records in the same campaign:**
   - Create two `SalesRecord` objects for the same contact and campaign, each with a different product.
   - View campaign statistics.
   - **Verify:** Both products appear with count 1 each; no duplicates or omissions.

3. **CSV export:**
   - Go to Campaign Statistics → a campaign with sales.
   - Click "Export".
   - **Verify:** The "Products sold" column shows only the products in the SalesRecord, not the full subscription product list.

## 📝 Deployment Notes

- No database migrations required.
- No configuration changes required.
- This ticket has one commit in `utopia-crm` (this repo) and one in `utopia-crm-ladiaria`. Both branches must be merged together.

## 🎓 Design Decisions

The fix was applied to `CampaignStatisticsDetailView` rather than to the subscription views because the source data was already correct — `SalesRecord.products` contained only sold products. The problem was that the statistics view was bypassing `SalesRecord` and reading subscription products directly.

This is a behaviour alignment rather than a strict bug fix: `SalesRecordFilterManagersView` already showed correct data. Users were unaware of that view and expected the same semantics from campaign statistics. The decision was to make both views consistent.

---

- **Date:** 2026-04-06
- **Author:** Tanya Tree + Claude Sonnet 4.6
- **Branch:** t1088
- **Type:** Enhancement / Behaviour correction
- **Modules affected:** Support (Campaign Statistics, Sales Records)
