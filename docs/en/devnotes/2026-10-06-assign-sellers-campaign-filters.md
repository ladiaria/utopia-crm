# Campaign filters in the assign-sellers list

- **Date:** 2026-10-06
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** assign-sellers-filters
- **Type:** Enhancement
- **Component:** Support (campaign management)
- **Impact:** Call center UX, Performance

## 🎯 Summary

The "Assign contacts to sellers" page (`/support/assign_sellers/`) listed every campaign with at least one contact
without a seller, including hundreds of old, inactive campaigns. It now shows only active campaigns by default,
can be filtered by name, and shows each campaign's status and dates. The counts are now computed in a single query
instead of three queries per campaign.

## ✨ Changes

### 1. Active and name filters, active by default

**File:** `support/views/all_views.py`

`list_campaigns_with_no_seller` reuses the existing `CampaignFilter` (the same one used by the campaign statistics
page), so both pages share the same filter form. When the request does not include `active`, the view applies
`active=true`:

```python
filter_data = request.GET.copy()
filter_data.setdefault("active", "true")
```

Choosing "Unknown" in the select shows every campaign; "No" shows only inactive ones.

### 2. Counts annotated in a single query

The previous version ran three `count()` queries per campaign (unassigned, morning, afternoon). With about 300
campaigns locally, that was around 900 queries. The counts are now `Count(..., filter=Q(...))` annotations, and the
"has contacts without a seller" condition is an `Exists` subquery, so it does not interfere with the joins used by
the counts. The whole page now runs 7 queries. Results are ordered by active first, then by name.

### 3. Status and date columns

**File:** `support/templates/distribute_campaigns.html`

- New columns: **Status** (green "Active" / grey "Inactive" badge), **Start date** and **End date**.
- Filter card above the table, with a "Clear" button that goes back to the default view.
- The campaign name now links to the assignment page through `{% url %}` instead of a relative `href`.
- An empty row says "No campaigns found" when the filters match nothing.

### 4. Translations with context

**File:** `locale/es/LC_MESSAGES/django.po`

"Campaign" is feminine in Spanish, and the existing "Active"/"Inactive" translations are masculine. The badges use
`{% trans "Active" context "campaign" %}`, with new `msgctxt "campaign"` entries ("Activa"/"Inactiva"). Also added:
"No campaigns found".

## 📁 Files Modified

- **`support/views/all_views.py`** — Filter with active by default, annotated counts.
- **`support/templates/distribute_campaigns.html`** — Filter form, status and date columns, empty state.
- **`locale/es/LC_MESSAGES/django.po`** — New strings.
- **`CHANGELOG.md`** — Entry for this change.

## 🧪 Manual Testing

1. **Default view (happy path):**
   - Open `/support/assign_sellers/`.
   - **Verify:** only active campaigns are listed, each with a green badge and its dates.

2. **All and inactive campaigns:**
   - Set "Active" to "Unknown" and filter; then to "No".
   - **Verify:** the first shows every campaign, the second only inactive ones (grey badge).

3. **Name filter with no matches (edge case):**
   - Type a name that does not exist and filter.
   - **Verify:** the table shows "No campaigns found"; "Clear" goes back to the active campaigns.

4. **Counts unchanged:**
   - Compare the Contacts / Morning / Afternoon columns with the assignment page of a campaign.
   - **Verify:** they match (checked locally against the old calculation on 232 campaigns, no differences).

## 📝 Deployment Notes

- No database migrations required.
- **Compile translations** (`python manage.py compilemessages -l es`).
- No configuration changes.

## 🎓 Design Decisions

- **Active by default, not hard-coded.** Inactive campaigns can still have contacts waiting for a seller, so
  they stay reachable through the filter instead of being excluded.
- **Reusing `CampaignFilter`** keeps the filter consistent with the campaign statistics page.

---

- **Date:** 2026-10-06
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** assign-sellers-filters
- **Type:** Enhancement
- **Modules affected:** Support
