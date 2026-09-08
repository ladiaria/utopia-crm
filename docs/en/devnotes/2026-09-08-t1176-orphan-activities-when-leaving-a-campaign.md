# Orphan Activities and Stale Console Links When a Contact Leaves a Campaign

- **Date:** 2026-09-08
- **Author:** Tanya Tree + Claude Opus 5
- **Ticket:** t1176
- **Type:** Bug Fix
- **Component:** Support — Campaign Management, Seller Console, Subscriptions
- **Impact:** Data Integrity, Seller Console Queues, User Experience

## 🎯 Summary

`Activity` has a foreign key to `Campaign`, not to `ContactCampaignStatus`. Removing a contact from a
campaign deletes the `ContactCampaignStatus` row and leaves every activity behind, still pointing at
the campaign. Two unrelated-looking symptoms come from that single fact:

1. A pending activity outlived its campaign status and kept showing up in the seller console `act`
   queue. Worse, `handle_post_request` marked the activity as completed **before** checking the
   campaign status, so resolving it produced the error message *"Contact is no longer in this
   campaign"* **and** closed the activity anyway — a call that never happened, recorded as done, with
   no follow-up scheduled.
2. `LadiariaSubscriptionCreateView` raised a `DoesNotExist` (HTTP 500) whenever the console link
   `?new=<ccs_id>` pointed at a deleted `ContactCampaignStatus` — a tab left open, a browser back
   button. The `act` branch of `capture_variables()` handled that case with a message and a redirect,
   but **no `dispatch` used the return value**, so that redirect was dead code and the view carried on
   without `self.ccs`.

The production traces that motivated the ticket: contact 31806 had two activities in campaign 297
(*Mundo 2026*) with no campaign status, the pending one closed on 2026-08-28 by a request that
aborted; and user `sofia.fernandez` hit the 500 on 2026-08-28 with `new=916086`, a status deleted a
month earlier by the CSV bulk delete.

## ✨ Changes

### 1. Bulk delete removes the open activities too

**File:** `support/views/campaign_management.py`

`BulkDeleteCampaignStatusView` now deletes the still-open activities of the same contacts on the same
campaign, inside the same transaction as the campaign statuses:

```python
with transaction.atomic():
    deleted_activities, _unused = Activity.objects.filter(
        contact_id__in=contact_ids,
        campaign=campaign,
        status__in=[ACTIVITY_STATUS.PENDING, ACTIVITY_STATUS.DELAYED],
    ).delete()
    deleted_count, _unused = ContactCampaignStatus.objects.filter(
        contact_id__in=contact_ids, campaign=campaign
    ).delete()
```

Only `PENDING` and `DELAYED` are removed: those represent calls that never happened. Completed
activities are history and stay. This mirrors what `Contact.combine()` already does when merging
contacts (`core/models.py`). The success message reports both counts.

### 2. The seller console checks the campaign status first

**File:** `support/views/seller_console.py`

The existence check moved ahead of every write, right after the console action is resolved:

```python
if not ContactCampaignStatus.objects.filter(campaign=campaign, contact=contact).exists():
    messages.error(self.request, _("Contact is no longer in this campaign"))
    return HttpResponseRedirect(reverse("seller_console", args=[category, campaign.id]))
```

`process_activity_result()` still performs its own lookup afterwards — it needs the instance to
update it — so the guarantee is not duplicated logic, it is ordering: nothing is written by a request
that is going to abort.

### 3. The `act` queue leaves orphans out

**File:** `support/views/seller_console.py`

`get_console_instances()` filters the pending activities by the existence of the campaign status, so
the activities orphaned before this fix are no longer offered:

```python
still_in_campaign = ContactCampaignStatus.objects.filter(
    campaign=campaign, contact=OuterRef("contact")
)
return (
    activities.filter(Exists(still_in_campaign))
    .select_related('seller_console_action')
    .order_by("datetime", "id")
)
```

The branch on `ALLOW_ACCESSING_FUTURE_ACTIVITIES_IN_SELLER_CONSOLE` was flattened into a single
queryset while touching the method, so the filter is applied once instead of in each return.

### 4. `capture_variables()` no longer trusts the link, and its callers honour it

**Files:** `support/views/subscriptions.py`,
`utopia-crm-ladiaria/utopia_crm_ladiaria/views/subscriptions.py`

The `new` branch was doing a bare `get()`. It now behaves like the `act` branch:

```python
try:
    self.ccs = ContactCampaignStatus.objects.get(pk=self.request.GET["new"])
except ContactCampaignStatus.DoesNotExist:
    messages.error(
        self.request,
        _("The contact is no longer in this campaign, instance number: {}").format(
            self.request.GET["new"]
        ),
    )
    return HttpResponseRedirect(reverse("seller_console_list_campaigns"))
```

The `act` branch got the same treatment for a deleted `Activity`, and both branches now read
`self.ccs.seller_id` instead of `self.ccs.seller.id`, which raised `AttributeError` on a campaign
status with no seller.

The important half is the callers. Every `dispatch()` calling `capture_variables()` discarded its
return value, so the redirects above would never have reached the browser:

```python
response = self.capture_variables()
if response:
    return response
return super().dispatch(request, *args, **kwargs)
```

This applies to the two `dispatch` methods of `SubscriptionMixin`, the one in
`CorporateSubscriptionCreateView`, the three in `utopia_crm_ladiaria`, and the ladiaria override of
`capture_variables()` itself, which also swallowed the response from `super()`.

## 📁 Files Modified

- **`support/views/campaign_management.py`** — bulk delete also removes open activities; success
  message reports the count
- **`support/views/seller_console.py`** — campaign status checked before writing; `act` queue filtered
  by `Exists`
- **`support/views/subscriptions.py`** — `new` and `act` branches handle missing rows; `seller_id`
  instead of `seller.id`; three `dispatch` methods honour the returned response
- **`tests/test_seller_console.py`** — new `TestSellerConsoleContactRemovedFromCampaign`

## 📚 Technical Details

**Why the orphans went unnoticed for so long.** `BulkDeleteCampaignStatusView` has existed since
2025-11-14, was disabled between 2026-03-19 and 2026-05-25, and only records a `LogEntry` per deleted
row since t1147 (2026-05-25). Deletions before that date left no trace at all, which is why most
orphan pairs cannot be explained from `django_admin_log`. The ones that can are recognisable by their
`change_message`: *"Bulk delete via CSV by …"*.

**Scale on the 2026-09-03 production dump.** 13,589 activities over 5,337 contacts and 251 campaigns
had no matching campaign status. Restricted to activity in 2026: 2,042 contacts, of which 1,037 were
left mid-gestion (last console action of type `SCHEDULED`, `CALL_LATER`, `NOT_FOUND` or `PENDING`)
and have no active subscription — the list handed to the distribution team so those contacts can be
put back into a campaign and called again. Only 8 activities were still pending and workable; 6
survived to the day of the cleanup and were deleted in production.

**Backward compatibility.** No model or schema change. The `Exists` filter is an extra `EXISTS`
subquery on a queryset already filtered by campaign and seller, over the
`(contact_id, campaign_id)` unique index of `ContactCampaignStatus`.

## 🧪 Manual Testing

1. **Bulk delete cleans the schedules (happy path):**
   - Pick a campaign, and a contact in it with a pending scheduled call.
   - Go to *Campaign Management → Bulk Delete Campaign Status*, upload a CSV with that `contact_id`
     and select the campaign.
   - **Verify:** the success message reports 1 campaign status and 1 activity deleted; the seller's
     `act` queue for that campaign no longer offers the contact.

2. **A contact removed from the campaign while a schedule is open (edge case):**
   - Create a pending activity for a contact in a campaign, then delete the `ContactCampaignStatus`
     directly from the admin (simulating the old data).
   - Open the seller console `act` queue for that campaign.
   - **Verify:** the contact is not listed. If the URL of the item is forced by hand and a result is
     posted, the message *"Contact is no longer in this campaign"* appears **and** the activity is
     still pending — not completed.

3. **Stale console link to a sale (edge case):**
   - Open the console `new` queue, copy a contact's "sell" link (`…/new_subscription/?new=<id>&…`).
   - Delete that `ContactCampaignStatus`, then load the copied link.
   - **Verify:** no 500. The page redirects to the campaign list with the message *"The contact is no
     longer in this campaign, instance number: …"*.

## 📝 Deployment Notes

- No database migrations required.
- No configuration changes.
- Optional post-deployment cleanup, for pending activities orphaned before the fix:

  ```sql
  DELETE FROM core_activity a
  USING (
    SELECT a2.id FROM core_activity a2
    LEFT JOIN core_contactcampaignstatus ccs
           ON ccs.contact_id = a2.contact_id AND ccs.campaign_id = a2.campaign_id
    WHERE a2.campaign_id IS NOT NULL AND a2.status = 'P' AND ccs.id IS NULL
  ) h WHERE a.id = h.id;
  ```

  Run the `SELECT` on its own first: with the fix deployed this should return few or no rows.
- The ladiaria package must be deployed together with the base app: the `dispatch` fix spans both.

## 🚀 Future Improvements

- The dashboard counters (`Seller.get_campaigns_with_activities()`, `campaign.pending`,
  `total_pending_activities_count()`) still count orphan activities. They cannot be worked on, so a
  campaign can appear in the list with a count the queue does not show. Worth aligning them with the
  same `Exists` filter.
- The seller console links carry `ContactCampaignStatus` and `Activity` primary keys in the
  querystring. Any of those can go stale between rendering and clicking; a periodic revalidation, or
  keying by contact and campaign instead, would remove a whole class of these errors.
- `BulkDeleteCampaignStatusView` logs deletions of campaign statuses but not of activities. If the
  audit trail matters for the activities too, they deserve their own `LogEntry`.

---

- **Date:** 2026-09-08
- **Author:** Tanya Tree + Claude Opus 5
- **Branch:** t1176
- **Type:** Bug Fix
- **Modules affected:** Support (Campaign Management, Seller Console, Subscriptions), Core (Activity,
  ContactCampaignStatus)
