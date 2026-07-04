# Contact Detail Overview: UX Compaction and Query Optimizations

**Date:** 2026-03-20
**Author:** Trifero + AI pair programmer
**Ticket:** t1060
**Type:** UX Improvement, Performance
**Component:** Contact Detail, Core Models
**Impact:** User Experience, Performance, Page Load Time

## 🎯 Summary

Refactored the Latest Issues and Latest Activities sections in the contact detail overview tab to be more compact and readable, replacing multi-line card items with a condensed 2-line layout and expandable notes. The number of items shown was also increased from 3 to 5 for both issues and activities. Alongside the visual changes, several N+1 query problems were addressed: activities now use `select_related` for seller and campaign, `get_subscriptionproducts()` now joins address and route in a single query, and `product_summary()` avoids a redundant DB query when subscription products are already prefetched.

## ✨ Changes

### 1. Compact Issues List in Overview

**File:** `support/templates/contact_detail/tabs/_overview.html`

The latest issues section was redesigned from a multi-paragraph card per issue into a tight 2-line layout. Line 1 shows category–subcategory, a status badge, the creation date, and a view button all in one row. Line 2 shows the first 60 characters of notes, with an inline "expand" link when notes exceed that length.

```html
<div class="list-group-item py-2 px-3">
  <div class="d-flex justify-content-between align-items-center">
    <span class="font-weight-bold">{{ issue.get_category }} – {{ issue.get_subcategory }}</span>
    <div class="d-flex align-items-center ml-2 flex-shrink-0">
      <span class="badge badge-secondary mr-2">{{ issue.get_status }}</span>
      <span class="text-muted mr-2">{{ issue.date_created|date:"d/m/Y" }}</span>
      <a href="..." class="btn btn-xs btn-outline-primary ..."><i class="fas fa-eye"></i></a>
    </div>
  </div>
  <!-- truncated notes with expand link -->
</div>
```

### 2. Compact Activities List in Overview

**File:** `support/templates/contact_detail/tabs/_overview.html`

The latest activities section received the same treatment. Line 1 shows activity type, optional campaign name, status badge, date, and seller. Line 2 shows truncated notes (60 chars) with an "expand" link that also reveals the seller console action, topic, response, and created-by fields when present.

### 3. Expand/Collapse JavaScript

**File:** `support/templates/contact_detail/detail.html`

Two click handlers were added inside the existing `DOMContentLoaded` block: one for `.issue-notes-toggle` and one for `.activity-extra-toggle`. Both toggle `d-none` on the short/full spans and flip the link text between "expand" and "collapse".

```javascript
document.querySelectorAll(".issue-notes-toggle").forEach(link => {
  link.addEventListener("click", event => {
    event.preventDefault();
    const id = link.dataset.id;
    const shortEl = document.querySelector(`.issue-notes-short-${id}`);
    const fullEl = document.querySelector(`.issue-notes-full-${id}`);
    const expanded = fullEl.classList.toggle("d-none");
    shortEl.classList.toggle("d-none");
    link.textContent = expanded ? "expand" : "collapse";
  });
});
```

### 4. Increased Items Shown and Added select_related for Activities

**File:** `support/views/contacts.py`

The `last_issues` and `activities` slices were increased from 3 to 5 items. Both the overview `activities` slice and the full `all_activities` queryset now use `select_related("seller", "campaign")` to avoid one DB query per activity when the template accesses `a.seller.name` or `a.campaign.name`.

```python
activities = self.object.activity_set.all().select_related("seller", "campaign").order_by("-datetime", "id")[:5]
all_activities = self.object.activity_set.all().select_related("seller", "campaign").order_by("-datetime", "id")
last_issues = all_issues[:5]
```

### 5. Eliminated N+1 in product_summary() via Prefetch Cache

**File:** `core/models.py` — `Subscription.product_summary()`

When a subscription's `subscriptionproduct_set` is already in `_prefetched_objects_cache` (as it is from `ContactDetailView.prefetched_subscriptions`), the method now iterates the in-memory list instead of firing a fresh `SubscriptionProduct.objects.filter(subscription=self)` query. The fallback to a DB query is preserved for all other callers.

```python
if "subscriptionproduct_set" in getattr(self, "_prefetched_objects_cache", {}):
    subscription_products = self._prefetched_objects_cache["subscriptionproduct_set"]
    if with_pauses:
        subscription_products = [sp for sp in subscription_products if sp.active]
else:
    subscription_products = SubscriptionProduct.objects.filter(subscription=self)
    if with_pauses:
        subscription_products = subscription_products.filter(active=True)
```

### 6. Added address and route to get_subscriptionproducts() select_related

**File:** `core/models.py` — `Subscription.get_subscriptionproducts()`

The `_subscription_card.html` template accesses `sp.address.address_1` and `sp.route.number` for every subscription product. These were not previously joined, causing one extra query per SP. Adding them to `select_related` resolves the N+1 in a single character change.

```python
.select_related("product", "address", "route")
```

## 📁 Files Modified

- **`support/templates/contact_detail/tabs/_overview.html`** — Redesigned latest issues and latest activities sections with compact 2-line layout and expandable notes
- **`support/templates/contact_detail/detail.html`** — Added expand/collapse JavaScript handlers for issues and activities
- **`support/views/contacts.py`** — Added `select_related` for activities; increased issues and activities slice to 5
- **`core/models.py`** — `product_summary()` uses prefetch cache when available; `get_subscriptionproducts()` joins address and route

## 📚 Technical Details

- The `_prefetched_objects_cache` approach in `product_summary()` is Django's standard internal cache key for prefetched reverse relations. It is safe to read but should never be written to directly.
- An attempt was also made to pass prefetched products into `calc_price_from_products()` to skip its `Product.objects.in_bulk()` call. This was reverted because `product_summary()` passes its output through `process_products()`, which can replace original product IDs with rule-generated bundle IDs — making the prefetched product set incomplete for the pricing lookup.
- The `select_related("address", "route")` on `get_subscriptionproducts()` benefits all callers of this method across the codebase, not only the contact detail page.

## 🧪 Manual Testing

1. **Compact issues display:**
   - Open a contact detail page with at least 2 issues having notes longer than 60 characters.
   - **Verify:** Each issue shows as a single compact row (category–subcategory, badge, date, eye button). A truncated notes line appears below it with an "expand" link.
   - Click "expand".
   - **Verify:** Full notes are shown and the link changes to "collapse". Clicking "collapse" returns to the truncated view.

2. **Compact activities display:**
   - Open a contact detail page with activities that have campaign, seller, and notes set.
   - **Verify:** Each activity shows type, campaign name, status badge, date, and seller in one row. Notes are truncated with an "expand" link.
   - Click "expand".
   - **Verify:** Full notes plus seller console action, topic, response, and created-by fields are revealed.

3. **Activity without expandable content:**
   - Find an activity with no notes, topic, response, seller console action, or created-by.
   - **Verify:** Only the first info row is shown; no expand link appears.

4. **Issue without notes:**
   - Find an issue with no notes.
   - **Verify:** Only the info row is shown; no notes line or expand link appears.

5. **Performance — subscription products:**
   - Open a contact with multiple active subscriptions using Django Debug Toolbar (or query logging).
   - **Verify:** No `SELECT ... FROM core_subscriptionproduct WHERE subscription_id = ...` queries fire during page render. No `SELECT ... FROM core_address WHERE id = ...` queries fire per subscription product.

## 📝 Deployment Notes

- No database migrations required.
- No configuration changes needed.
- No management commands to run.
- The `get_subscriptionproducts()` change applies globally — verify any custom templates or views that call this method and rely on address or route being lazy-loaded still work as expected (they will, since `select_related` only adds joins and never changes the returned queryset shape).

## 🚀 Future Improvements

- Extend the `product_summary()` prefetch-cache pattern to `calc_price_from_products()` once a safe approach for handling `process_products()` bundle ID remapping is identified.
- Consider applying the same compact 2-line pattern to the activities tab (`_activities.html`) for consistency across the full contact detail page.

---

**Date:** 2026-03-20
**Author:** Trifero + AI pair programmer
**Branch:** t1060
**Type:** UX Improvement, Performance
**Modules affected:** Support, Core Models, Contact Detail
