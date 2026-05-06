# Campaign Statistics Rate Redefinitions and Contacted Status Centralisation

- **Date:** 2026-03-26
- **Author:** Tanya Tree + Claude Sonnet 4.6
- **Ticket:** t1071
- **Type:** Enhancement
- **Component:** Campaign Statistics, Core Models, Support Views
- **Impact:** Reporting accuracy, Code maintainability

## 🎯 Summary

Campaign statistics were reporting "contacted" and "success" rates against misleading denominators: contacted was divided by the total number of contacts in the campaign, and successes were divided by that same total. The business request was to redefine contacted as a proportion of all contacts that were actually called, and to redefine successes as a proportion of those who were contacted. At the same time, the set of statuses considered "contacted" was widened to include `SWITCH_TO_MORNING` (6) and `SWITCH_TO_AFTERNOON` (7) — statuses that require having spoken with the person — and centralised in a single `get_contacted_statuses()` helper in `core/choices.py` so that no view has to hard-code status integers. Three dead `Campaign` model methods that had no callers anywhere in either project were also removed.

## ✨ Changes

### 1. Centralised "contacted" status definition

**File:** `core/choices.py`

A new helper function `get_contacted_statuses()` was added immediately above `CAMPAIGN_RESOLUTION_CHOICES`. It returns the four statuses that require actual contact with the person, expressed as `CAMPAIGN_STATUS` enum members rather than raw integers:

```python
def get_contacted_statuses():
    return [
        CAMPAIGN_STATUS.CONTACTED,          # 2
        CAMPAIGN_STATUS.ENDED_WITH_CONTACT, # 4
        CAMPAIGN_STATUS.SWITCH_TO_MORNING,  # 6
        CAMPAIGN_STATUS.SWITCH_TO_AFTERNOON,# 7
    ]
```

Statuses 6 and 7 (switch-to-morning and switch-to-afternoon) were previously excluded despite representing contacts where a conversation took place — the person answered and asked to be called at a different time. They are now included.

### 2. Replaced all raw status literals in campaign statistics views

**File:** `support/views/all_views.py`

All six occurrences of `status__in=[2, 4]` (or `(2, 4)`) across four functions were replaced with `core_choices.get_contacted_statuses()`:

- `campaign_statistics_list` — contacted count per campaign
- `CampaignStatisticsDetailView.get_context_data` — contacted count, and the `ccs_with_resolution_contacted_count` used for resolution percentages
- `campaign_statistics_per_seller` — contacted count per seller
- `seller_performance_by_time` — contacted count for totals and per-seller loop

### 3. Redefined rate denominators

**File:** `support/views/all_views.py`

Two denominator changes were applied across all statistics functions:

**Contacted rate:** previously `contacted / total_in_campaign`, now `contacted / total_called` (status >= 2). A contact being in the campaign does not mean anyone picked up the phone; dividing by those actually called gives a meaningful conversion rate.

**Success rate:** previously `success / total_in_campaign` (or `/ assigned`), now `success / contacted`. This measures how well sellers convert the contacts they actually spoke with, not the raw campaign base.

In `CampaignStatisticsDetailView`, a local `called_count` variable was introduced to avoid re-querying:

```python
called_count = filtered_qs.filter(status__gte=2).count()
context['contacted_pct'] = (context['contacted_count'] * 100) / (called_count or 1)
```

In `campaign_statistics_per_seller`, the per-seller success percentage now divides by that seller's contacted count:

```python
seller.success_pct = (seller.success_count * 100) / (seller.contacted_count or 1)
```

### 4. Updated template labels to reflect new semantics

**Files:** `support/templates/campaign_statistics_detail.html`, `support/templates/campaign_statistics_per_seller.html`

- The "Conversión de la base" card in the detail view previously read `% del total`; it now reads `% de contactados`.
- The per-seller table tooltip for the contacted percentage column was updated to `Porcentaje contactado sobre llamados`, and for the success percentage column to `Porcentaje suscrito sobre contactados`.

### 5. Removed dead Campaign model methods

**File:** `core/models.py`

Three methods with no callers in either `utopia-crm` or `utopia-crm-ladiaria` were removed:

- `get_activities_by_seller(seller, status, type, datetime)` — was used in the seller console list campaigns view until February 2021, when the algorithm was simplified and the method was dropped.
- `get_already_contacted(seller_id)` — returned contacts with `status=2` only; had been dead since the initial open-source release.
- `get_already_contacted_count(seller_id)` — delegated to `get_already_contacted`; equally dead.

The `get_contacted_statuses` import that had been added to `models.py` solely for `get_already_contacted` was also removed.

## 📁 Files Modified

- **`core/choices.py`** — Added `get_contacted_statuses()` helper function
- **`core/models.py`** — Removed three dead `Campaign` methods; removed unused `get_contacted_statuses` import
- **`support/views/all_views.py`** — Replaced all `status__in=[2, 4]` literals with `get_contacted_statuses()`; changed contacted and success rate denominators in `campaign_statistics_list`, `CampaignStatisticsDetailView`, `campaign_statistics_per_seller`, and `seller_performance_by_time`
- **`support/templates/campaign_statistics_detail.html`** — Updated success rate label from "del total" to "de contactados"
- **`support/templates/campaign_statistics_per_seller.html`** — Updated tooltip titles for contacted and success percentage columns

## 📚 Technical Details

- All division-by-zero guards use `(x or 1)` as the denominator, consistent with the existing pattern throughout the statistics views.
- `seller_performance_by_time` had its contacted count updated to use `get_contacted_statuses()` but its success rate denominator was left as `assigned_count` — that function computes a different kind of report (performance over a date range, not a campaign conversion funnel) and was not part of the original request.
- The git history shows `get_activities_by_seller` was last called in commit `36f9f01` (February 2021), and `get_already_contacted` was present but uncalled since the initial public commit `ed3b749`.

## 🧪 Manual Testing

1. **Happy path — campaign statistics list:**
   - Open `/support/campaign_statistics/` and pick a campaign where some contacts have been called.
   - **Verify:** The "Contacted" percentage is now the ratio of contacted (statuses 2, 4, 6, 7) over called (status >= 2), not over the total campaign size. The "Success (over contacted)" column should also reflect the new contacted base.

2. **Happy path — campaign statistics detail view:**
   - Open the detail view for any campaign.
   - **Verify:** The "Contactado" row shows its percentage relative to called contacts. The "Conversión de la base" card now reads `% de contactados` instead of `% del total`, and the figure reflects successes over contacted, not over the full campaign.

3. **Happy path — per-seller statistics:**
   - Open `/support/campaign_statistics_per_seller/<id>/` for a campaign with multiple sellers.
   - **Verify:** Each seller's "%" column next to "Contactado" shows contacted/called, and the "%" column next to "Suscrito" shows successes/contacted. Hover over those column headers to confirm the updated tooltip text.

4. **Edge case — seller with zero calls:**
   - Find (or simulate) a seller assigned to a campaign who has not yet called anyone (called_count = 0).
   - **Verify:** The contacted percentage displays as 0% without a division-by-zero error. The success percentage also displays as 0%.

5. **Edge case — campaign with contacts in switch-to-morning/afternoon status:**
   - Find a contact whose `ContactCampaignStatus` has status 6 or 7.
   - **Verify:** That contact now contributes to the contacted count in all statistics views, whereas previously they would have been excluded.

## 📝 Deployment Notes

- No database migrations required.
- No configuration changes needed.
- The change affects reported percentages in existing campaigns — numbers will shift for any campaign that has contacts in statuses 6 or 7, or where the previous total-based denominators differed significantly from the called/contacted bases.

## 🎓 Design Decisions

- `get_contacted_statuses()` is a function rather than a module-level constant so that it can reference `CAMPAIGN_STATUS` enum members (which are defined above it in the same file) without relying on import order. It is also consistent with the existing `get_activity_types()` pattern in the same module.
- The decision to include statuses 6 and 7 as "contacted" is based on operational semantics: to switch a contact to a different time slot, the seller must have spoken with them. They are therefore contacted in the meaningful sense even though the campaign interaction is not yet complete.

---

- **Date:** 2026-03-26
- **Author:** Tanya Tree + Claude Sonnet 4.6
- **Branch:** t1071
- **Type:** Enhancement
- **Modules affected:** Campaign Statistics, Core Models, Support Views
