# Feature: Export Contact Campaign Status Across All Campaigns to CSV

- **Date:** 2026-06-19
- **Author:** Tanya Tree + Claude Opus 4.8
- **Ticket:** feature/export-all-campaigns-status
- **Type:** Feature (+ Bug Fix)
- **Component:** Support — Campaign Management, Core Models (ContactCampaignStatus, Activity)
- **Impact:** Campaign Reporting, Data Export, Data Integrity

## 🎯 Summary

The existing per-campaign statistics view (`/support/campaign_statistics/<pk>/`) can export the `ContactCampaignStatus` records of a single campaign, but there was no way to export them across **all** campaigns at once. This change adds a new view, `AllCampaignsStatusExportView`, that streams a CSV of contact campaign statuses spanning every campaign, using the same filters as the per-campaign view. Because that dataset would be enormous, the view returns nothing by default: a `date_assigned` (from) filter is required before any data is shown or exported. While building it we confirmed a long-standing bug the user suspected: the "Times contacted" column was almost always `0` because it read the persisted `ContactCampaignStatus.times_contacted` field, which is never incremented anywhere in the code. It is now computed on the fly by counting completed calls for that exact contact and campaign — both in the new view and in the existing per-campaign export.

## ✨ Changes

### 1. New global export view

**File:** `support/views/all_views.py`

`AllCampaignsStatusExportView` is a `FilterView` over `ContactCampaignStatus` (not scoped to one campaign). It mirrors the per-campaign view's permissions (`Managers` group or superuser, `staff_member_required`). Nothing is returned until a date is selected:

```python
def has_date_filter(self):
    return bool(self.request.GET.get("date_assigned_min"))

def get_queryset(self):
    if not self.has_date_filter():
        return ContactCampaignStatus.objects.none()
    return ContactCampaignStatus.objects.all()
```

The page shows a filter form plus a paginated preview; `?export=csv` triggers a `StreamingHttpResponse` (UTF-8 BOM for Excel, `io.StringIO` buffer flushed per row, `iterator(chunk_size=1000)`), matching the seller-attendance export pattern already in the codebase.

### 2. Correct "Times contacted" calculation (correlated per campaign)

**File:** `support/views/all_views.py`

Because the global query spans many campaigns, the completed-call count must correlate the `Activity.campaign` with each row's `ContactCampaignStatus.campaign`. A correlated `Subquery` is used (not a `Count` with `F('campaign')`, which is unreliable across a multi-campaign `GROUP BY`):

```python
times_contacted_sq = (
    Activity.objects.filter(
        contact=OuterRef("contact"),
        campaign=OuterRef("campaign"),
        activity_type="C",
        status="C",
    )
    .order_by()
    .values("contact")
    .annotate(c=Count("id"))
    .values("c")
)
filtered_qs = filtered_qs.annotate(
    times_contacted_real=Coalesce(Subquery(times_contacted_sq, output_field=IntegerField()), 0),
    activity_count=Coalesce(Subquery(activity_count_sq, output_field=IntegerField()), 0),
)
```

`activity_count` uses the same correlation (without the type/status filter) so the count belongs to that specific contact-campaign pair and not to another campaign of the same contact. Products sold are mapped per `(contact_id, campaign_id)` from `SalesRecord.products`, built once before streaming and bounded by the filtered contacts/campaigns.

### 3. Fix the same bug in the existing per-campaign export

**File:** `support/views/all_views.py`

`CampaignStatisticsDetailView.export_csv` exported the raw `ccs.times_contacted` field (always `0`). Since that view is single-campaign, a plain `Count` with a constant campaign filter is enough (no Subquery needed):

```python
times_contacted_real=Count(
    "contact__activity",
    filter=Q(
        contact__activity__campaign=self.campaign,
        contact__activity__activity_type="C",
        contact__activity__status="C",
    ),
)
```

The CSV row now uses `ccs.times_contacted_real`. The model field is left untouched (no persistence logic added); the on-the-fly count matches what the seller console already computes.

### 4. New filter, URL, menu card, and sidebar item

**Files:** `support/filters.py`, `support/urls.py`, `support/templates/campaign_management_menu.html`, `templates/components/sidebar_items/_campaign_management.html`

`AllCampaignsContactStatusFilter` reuses the same fields as `ContactCampaignStatusFilter` (seller, status, `date_assigned_min/max`, `last_action_date_min/max`) plus an optional `campaign` filter to narrow a subset. The "empty by default" behaviour is enforced in the view, not the filter, so the filter stays reusable. A new URL (`all_campaigns_status_export`), a card in the "Tracking and reports" section of the campaign management menu, and a sidebar item were added.

### 5. Template with usage hint

**File:** `support/templates/all_campaigns_status_export.html` (new)

The page clarifies that **only** the assigned-date is required and that the other filters are optional — leaving the campaign empty includes every campaign — so operators do not mistake the non-required fields for required ones.

## 📁 Files Modified

- **`support/views/all_views.py`** — Added `AllCampaignsStatusExportView`; added imports (`io`, `Subquery`, `IntegerField`, `Coalesce`); fixed `times_contacted` in `CampaignStatisticsDetailView.export_csv`
- **`support/filters.py`** — Added `AllCampaignsContactStatusFilter`
- **`support/urls.py`** — Added the `all_campaigns_status_export` route
- **`support/templates/campaign_management_menu.html`** — Added the "Export all campaigns status" card
- **`templates/components/sidebar_items/_campaign_management.html`** — Added the sidebar item

## 📁 Files Created

- **`support/templates/all_campaigns_status_export.html`** — Filter form, usage hint, paginated preview, and CSV download button

## 📚 Technical Details

**Why the field was always 0:** `ContactCampaignStatus.times_contacted` is a `SmallIntegerField(default=0)` that is never incremented or saved anywhere in the codebase. The seller console computes the real value on the fly (`contact.activity_set.filter(activity_type="C", status="C", campaign=campaign).count()`) but does not persist it, so any reader of the raw field saw `0`. The fix computes the same value at query time instead of touching the model.

**Why Subquery instead of `F('campaign')` in the global view:** a `Count('contact__activity', filter=Q(... campaign=F('campaign')))` joins `Activity` by contact and can inflate or mis-correlate counts under a multi-campaign `GROUP BY`. A correlated `Subquery` with `OuterRef("campaign")` returns one scalar per row, correctly matched to that row's campaign, without inflating rows.

## 🧪 Manual Testing

1. **Happy path — export with a date:**
   - Open Campaign Management → "Export all campaigns status".
   - Select an "assigned date (from)" within a period that has data and click "Download CSV".
   - **Verify:** A CSV downloads with one row per contact campaign status across all campaigns; the header is translated and the "Times contacted" column shows real counts (not all zeros).

2. **Times contacted matches the seller console:**
   - Pick a contact with several completed calls in a campaign.
   - **Verify:** The CSV's "Times contacted" for that contact-campaign equals the count shown by the seller console (e.g. 6 calls → 6).

3. **Edge case — no date returns nothing:**
   - Open the view without selecting a date; also try `?export=csv` with no date.
   - **Verify:** The preview is empty with a hint to select a date; the CSV contains only the header (0 data rows).

4. **Edge case — campaign left empty includes all campaigns:**
   - Filter only by date, leaving the campaign select empty.
   - **Verify:** The export includes statuses from multiple campaigns.

5. **Permissions:**
   - Access the view as a non-Manager, non-superuser user.
   - **Verify:** Access is denied (403/redirect).

## 📝 Deployment Notes

- No database migrations required.
- No configuration changes required.
- Historical `times_contacted` values are not backfilled; the column is computed at export time, so no data migration is needed.

## 🎓 Design Decisions

The "empty by default" rule is enforced in the view (`get_queryset` returns `.none()` without a date) rather than in the filter, so `AllCampaignsContactStatusFilter` stays a plain, reusable, testable FilterSet. The persisted `times_contacted` field is intentionally left in place and unused for reads rather than removed or backfilled, keeping the change low-risk and consistent with the seller console's existing on-the-fly calculation.

## 🚀 Future Improvements

- Consider persisting `times_contacted` (or removing the dead field) so it does not mislead future readers.
- Add an index on `Activity(contact, campaign)` if the correlated subqueries become a bottleneck on very large date ranges.

---

**Date:** 2026-06-19
**Author:** Tanya Tree + Claude Opus 4.8
**Branch:** feature/export-all-campaigns-status
**Type:** Feature (+ Bug Fix)
**Modules affected:** Support, Core (ContactCampaignStatus, Activity)
