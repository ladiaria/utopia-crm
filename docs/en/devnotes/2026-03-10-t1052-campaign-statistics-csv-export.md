# Campaign Statistics CSV Export

**Date:** 2026-03-10
**Author:** Trifero + AI pair programmer
**Ticket:** t1052
**Type:** Feature
**Component:** Campaign Management, Statistics
**Impact:** Manager Workflow, Campaign Analysis, Data Export

## 🎯 Summary

Added a CSV export button to the `CampaignStatisticsDetailView` so managers can download per-contact campaign data. The export respects all active filters (seller, status, date ranges) and includes 17 columns covering contact info, campaign resolution, seller assignment, activity counts, and subscription data (start date and products sold). Queries are optimized to avoid N+1 issues using `select_related`, `Count` annotation, and a bulk subscription prefetch.

## ✨ Changes

### 1. CSV Export Method on CampaignStatisticsDetailView

**File:** `support/views/all_views.py`

Added `get()` override to intercept `?export=csv` and route to a new `export_csv()` method. The method:

- Applies the same `ContactCampaignStatusFilter` as the page view
- Uses `select_related('contact', 'seller', 'last_console_action')` to avoid FK lookups in the loop
- Annotates `activity_count` via `Count` with a filter on the current campaign
- Builds a `contact_id → {start_date, products}` dict from `Subscription` + `SubscriptionProduct` in two bulk queries
- Streams rows with `iterator(chunk_size=1000)` for memory efficiency

```python
def get(self, request, *args, **kwargs):
    if request.GET.get("export") == "csv":
        return self.export_csv()
    return super().get(request, *args, **kwargs)
```

CSV columns (17 total):

| Column | Source |
| --- | --- |
| Contact ID, Name, Email, Phone, Mobile | `Contact` model |
| Status | `ContactCampaignStatus.get_status()` |
| Campaign resolution | `ContactCampaignStatus.get_campaign_resolution()` |
| Resolution reason | `ContactCampaignStatus.get_resolution_reason()` |
| Seller | `ContactCampaignStatus.seller.name` |
| Date assigned, Last action date, Date created | `ContactCampaignStatus` date fields |
| Times contacted | `ContactCampaignStatus.times_contacted` |
| Activity count | Annotated `Count` of activities for this campaign |
| Last console action | `SellerConsoleAction.name` |
| Subscription start date | `Subscription.start_date` (linked via campaign FK) |
| Products sold | Comma-separated `SubscriptionProduct` names |

### 2. Export Button in Template

**File:** `support/templates/campaign_statistics_detail.html`

Added a green "Export CSV" submit button inside the existing filter `<form>`. Because it uses `<button type="submit" name="export" value="csv">`, it automatically includes all current filter parameters — no extra URL or JavaScript needed.

```html
<button type="submit" name="export" value="csv" class="btn bg-gradient-success">
  <i class="fas fa-file-csv"></i> {% trans "Export CSV" %}
</button>
```

## 📁 Files Modified

- **`support/views/all_views.py`** — Added `get()` and `export_csv()` methods to `CampaignStatisticsDetailView`
- **`support/templates/campaign_statistics_detail.html`** — Added "Export CSV" button next to filter actions

## 📚 Technical Details

### How Subscriptions Relate to Campaigns

The `Subscription` model has a `campaign` FK to `Campaign`. When a seller makes a successful sale through the seller console, the subscription is linked to the campaign via `ContactCampaignStatus.handle_direct_sale()` which sets `subscription.campaign = self.campaign`. This allows us to query all subscriptions sold through a campaign and their products.

### Query Optimization Strategy

The export executes a fixed number of queries regardless of dataset size:

1. **Main query:** Filtered `ContactCampaignStatus` with `select_related` + `Count` annotation
2. **Subscription query:** All `Subscription` objects for this campaign with prefetched `SubscriptionProduct` → `Product`
3. **Loop:** Zero additional queries — all data accessed from prefetched/annotated fields

## 🧪 Manual Testing

1. **Happy path — export with no filters:**
   - Navigate to Campaign Statistics for an active campaign
   - Click "Export CSV" without applying any filters
   - **Verify:** CSV downloads with filename `campaign_{id}_{date}.csv`, contains all contacts in the campaign with correct data in all 17 columns

2. **Export with filters applied:**
   - Select a seller from the dropdown and set a date range
   - Click "Apply filters" to see filtered results
   - Click "Export CSV"
   - **Verify:** CSV contains only the filtered subset of contacts, matching the count displayed on the page

3. **Edge case — campaign with no subscriptions:**
   - Export CSV for a campaign where no sales were made
   - **Verify:** CSV downloads successfully; "Subscription start date" and "Products sold" columns are empty for all rows

4. **Edge case — contact with no seller assigned:**
   - Export a campaign that has unassigned contacts
   - **Verify:** Seller column is empty (not an error) for those contacts

## 📝 Deployment Notes

- No database migrations required
- No configuration changes needed
- No management commands to run
- Feature is available immediately after deploy

## 🎓 Design Decisions

- **GET parameter approach (`?export=csv`)** instead of a separate URL: simpler, automatically respects active filters, no URL routing changes needed
- **Bulk subscription dict** instead of per-contact queries: fixed query count regardless of campaign size
- **`iterator(chunk_size=1000)`** for memory-efficient streaming on large campaigns

---

**Date:** 2026-03-10
**Author:** Trifero + AI pair programmer
**Branch:** t1052
**Type:** Feature
**Modules affected:** Support, Campaign Management
