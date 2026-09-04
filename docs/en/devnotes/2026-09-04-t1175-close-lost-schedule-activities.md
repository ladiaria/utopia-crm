# Closing Lost Schedules with a Dedicated Campaign Resolution

- **Date:** 2026-09-04
- **Author:** Tanya Tree + Claude Opus 5
- **Ticket:** t1175
- **Type:** Feature (+ Bug Fix on the command it replaces)
- **Component:** Core — Campaigns, Activities, Seller Console Actions; Support — Seller Console
- **Impact:** Data Integrity, Campaign Statistics, Seller Console Queues

## 🎯 Summary

Community management asked to close every dangling **schedule** — a pending `Activity` of type call
tied to a campaign, which is how the seller console represents "call this contact back on this
date" — older than 2026-05-31, and to close the associated `ContactCampaignStatus` marking that the
close was forced rather than done by a seller.

Dangling schedules are not just noise. A contact with a pending activity stays in the console's
"act" queue forever, keeps being counted in the seller's pending work, and — the expensive part — is
excluded from the "new" queue of **every** active campaign through
`Campaign.get_not_contacted()`. A schedule from 2025 blocks that contact for every campaign running
today. In production there are 1,173 such activities across 1,167 contact/campaign pairs.

The change adds a new `campaign_resolution` value (`LS`, *closed due to lost schedule*), a new
management command `close_lost_schedule_activities`, and a `close-lost-schedule` seller console
action that marks the forced close. It also replaces
`close_old_pending_activities_and_campaign_status`, which did the same job destructively: it forced
**every** campaign status to `5` / `CW` without looking at what was already resolved, and when it was
run in production on 2025-07-01 it overwrote 181 successful sales.

## ✨ Changes

### 1. A new campaign resolution, not a new campaign status

**File:** `core/choices.py`

The label of the forced close lives in `campaign_resolution` — the field that says *why* a contact
ended the way it did — and not in `status`, which says *where in the funnel* the contact stopped:

```python
CAMPAIGN_RESOLUTION_CHOICES = (
    ...
    ("CW", _("Close without contact")),
    ("LS", _("Closed due to lost schedule")),
)
```

96.3% of the dangling schedules hang from a contact in `status=2` (contacted): the appointment was
agreed while actually talking to the person. A new `status` value would drop all of them out of
`get_contacted_statuses()`, so people we *did* speak to would show up in the "unreachable" CSV
(`not_contacted_campaign`) and would inflate the denominator of `unreachable_pct` and
`error_in_promotion_pct` across the whole history of those campaigns. A new resolution code, by
contrast, falls into no statistics bucket: it shows up in filters, exports and the activities API
glossary, and nothing else. The precedent is `NF`, added exactly this way in `core.0117`.

### 2. The campaign status is mapped conditionally

**File:** `core/management/commands/close_lost_schedule_activities.py`

Instead of sending everything to "ended without contact", the terminal status respects what was
already known about the contact:

```python
STATUS_MAP = {
    CAMPAIGN_STATUS.NOT_YET_CONTACTED: CAMPAIGN_STATUS.ENDED_WITHOUT_CONTACT,
    CAMPAIGN_STATUS.CALLED_COULD_NOT_CONTACT: CAMPAIGN_STATUS.ENDED_WITHOUT_CONTACT,
    CAMPAIGN_STATUS.CONTACTED: CAMPAIGN_STATUS.ENDED_WITH_CONTACT,
    CAMPAIGN_STATUS.SWITCH_TO_MORNING: CAMPAIGN_STATUS.ENDED_WITH_CONTACT,
    CAMPAIGN_STATUS.SWITCH_TO_AFTERNOON: CAMPAIGN_STATUS.ENDED_WITH_CONTACT,
}
```

Statuses 4 and 5 are already terminal and are not in the map, so they are left untouched; the
dangling activity is still closed. Sales are protected separately: a status carrying `S1` or `S2` is
never overwritten, whatever its status value.

### 3. The forced close is legible in three places

**Files:** `core/management/commands/close_lost_schedule_activities.py`,
`core/management/commands/populate_seller_console_actions.py`

1. `ContactCampaignStatus.campaign_resolution = "LS"` — the resolution itself.
2. `Activity.seller_console_action` → the new `close-lost-schedule` action, which is what
   distinguishes this from the `close-without-contact` a seller clicks by hand. The same action is
   stored in `ContactCampaignStatus.last_console_action`.
3. `Activity.notes` — a dated line is **appended**, never overwriting what was there:
   *"Automatically closed due to lost schedule (t1175, 2026-09-04)."*

The action had to be added to the `populate_seller_console_actions` tuple: that command **deletes**
every `SellerConsoleAction` outside it, and both `Activity.seller_console_action` and
`ContactCampaignStatus.last_console_action` are `on_delete=SET_NULL` — creating the action by hand
would mean the mark silently disappears from thousands of rows the next time anyone runs the
populate.

But the tuple used to force `is_active=True`, and `get_seller_console_action()` filters by
`is_active=True`. So the tuple grew a sixth column and the new action is registered **inactive**: it
survives the populate and cannot be triggered from the console by a hand-crafted POST.

```python
(
    SellerConsoleAction.ACTION_TYPES.NO_CONTACT,
    "close-lost-schedule",
    "Cerrado por agenda perdida",
    None,  # The status is decided per contact by close_lost_schedule_activities
    "LS",  # Closed due to lost schedule
    False,
),
```

### 4. The command

**File:** `core/management/commands/close_lost_schedule_activities.py`

```bash
python manage.py close_lost_schedule_activities --date 2026-05-31 --dry-run --csv /tmp/lost.csv
python manage.py close_lost_schedule_activities --date 2026-05-31
```

| Flag | Required | Purpose |
| --- | --- | --- |
| `--date YYYY-MM-DD` | yes | Closes schedules on that date or older. No default on purpose: nobody should close schedules by accident |
| `--dry-run` | no | Writes nothing; prints the full breakdown of transitions |
| `--csv PATH` | no | Dumps the affected rows (contact, campaign, seller, schedule date, status and resolution before/after) so they can be audited before running for real |
| `--campaign ID` | no | Restricts to one campaign, so the work can be done in batches |
| `--limit N` | no | Caps the universe for a first small pass |

The selection is deliberately narrow: `status` in `P`/`E`, `activity_type="C"`,
`campaign__isnull=False`. Pending activities that are not tied to a campaign are out of scope for
this ticket, and only calls act as schedules in the console. `EXPIRED` is included even though there
are currently zero such rows, in case `expire_old_pending_activities` starts running.

The date is inclusive of the whole day, which is what community management asked for:

```python
cutoff = datetime.combine(parsed, time.max)
return timezone.make_aware(cutoff) if settings.USE_TZ else cutoff
```

### 5. The old command becomes a stub

**File:** `core/management/commands/close_old_pending_activities_and_campaign_status.py`

`close_old_pending_activities_and_campaign_status` set `status=5` and `campaign_resolution="CW"` on
*any* `ContactCampaignStatus` of the pair, sales included. It was run in production on 2025-07-01
(7,927 activities, 7,768 statuses set to `CW`) and overwrote **181** successful sales — all 181 have
a subscription whose `start_date` predates the run, so the sale already existed when it was erased.

It is not in any crontab (`ss_conf/etc/cron.d/crm`), so nothing depends on its current behaviour.
Rather than leaving a loaded gun next to its fixed twin, it now aborts:

```python
raise CommandError(
    "This command is deprecated because it overwrote already resolved campaign statuses, sales "
    "included. Use 'close_lost_schedule_activities' instead:\n"
    "    python manage.py close_lost_schedule_activities --date YYYY-MM-DD --dry-run"
)
```

It is a stub rather than a silent rewiring: anyone who still has it in a personal runbook gets a
clear message instead of different semantics without noticing.

### 6. Where the number shows up: the statistics panel stops being hardcoded

**Files:** `core/choices.py`, `support/views/all_views.py`,
`support/templates/campaign_statistics_detail.html`

A resolution that falls into no statistics bucket is exactly what protects the historical
percentages — but it also means nobody can see how many contacts were closed this way. The campaign
statistics panel counted resolutions one by one, hardcoded in the view **and** labelled by hand in
the template, so every new resolution needed edits in two places or it stayed invisible.

The breakdown is now declared in `core/choices.py` as rows of `(context_key, label, codes)`:

```python
CONTACTED_RESOLUTION_BREAKDOWN = (
    ("success_with_direct_sale", _("Success"), ("S2",)),
    ("total_rejects", _("Rejection"), REJECT_RESOLUTIONS),
    ("scheduled", _("Scheduled appointment"), ("SC",)),
    ("started_promotion", _("Promotion in progress"), ("SP",)),
    ("lost_schedule", _("Closed due to lost schedule"), ("LS",)),
)
```

The two tuples (contacted / not contacted) differ in their denominator, which is what the two cards
of the panel already did implicitly. The view turns them into rows with `build_resolution_rows()`
and the template renders them with a `{% for %}`. Adding a resolution to the panel is now one line
in `choices.py`.

Two things came along with it:

- The seven `.count()` queries became **one grouped query**
  (`values("campaign_resolution").annotate(Count("id"))`).
- The old per-resolution context keys (`scheduled_count`, `scheduled_pct`, ...) are still written,
  so a custom installation overriding this template keeps working.

The Spanish labels are unchanged: the new `msgid`s were added to the `.po` with exactly the text the
template used to hardcode.

Two more constants replace literals scattered across the view — `SALE_RESOLUTIONS = ("S1", "S2")`
and `REJECT_RESOLUTIONS = ("AS", "DN", "LO", "NI")`, which appeared six times between
`CampaignStatisticsDetailView`, `campaign_statistics_per_seller` and the campaign list. The command
of change 4 imports `SALE_RESOLUTIONS` from there too, instead of defining its own copy.

### 7. Filtering by resolution, in the panel and in the admin

**Files:** `support/filters.py`, `core/admin.py`,
`support/templates/campaign_statistics_detail.html`,
`support/templates/all_campaigns_status_export.html`

`ContactCampaignStatusFilter` and `AllCampaignsContactStatusFilter` declared
`fields = ["seller", "status"]`, so there was no way to list the contacts closed with a given
resolution from the web. Both now include `campaign_resolution`, and both templates render the new
select. Filtering by "Finalizado por agenda perdida" gives the count in `filtered_count` and the
list in the CSV export, which already carried the resolution column.

`ContactCampaignStatusAdmin` gets `campaign_resolution` in `list_filter` and in `list_display`.

## 📁 Files Created

- **`core/management/commands/close_lost_schedule_activities.py`** — The command
- **`core/migrations/0122_add_lost_schedule_campaign_resolution.py`** — `AlterField` on
  `ContactCampaignStatus.campaign_resolution`
- **`support/migrations/0041_add_lost_schedule_campaign_resolution.py`** — `AlterField` on
  `SellerConsoleAction.campaign_resolution`
- **`tests/test_close_lost_schedule.py`** — 23 tests

## 📁 Files Modified

- **`core/choices.py`** — New `LS` value in `CAMPAIGN_RESOLUTION_CHOICES`
- **`core/management/commands/populate_seller_console_actions.py`** — Sixth `is_active` column in the
  tuple; `close-lost-schedule` registered inactive
- **`core/management/commands/close_old_pending_activities_and_campaign_status.py`** — Reduced to a
  stub that aborts
- **`COMMANDS.md`** — New row for the command; the old one marked `deprecated`
- **`locale/es/LC_MESSAGES/django.po`** — The resolution label, the activity note, the panel row
  labels (with the exact text the template used to hardcode) and "Filter by resolution"
- **`core/choices.py`** — `SALE_RESOLUTIONS`, `REJECT_RESOLUTIONS` and the two panel breakdowns
- **`support/views/all_views.py`** — `build_resolution_rows()`, one grouped query instead of seven
  counts, and the constants replacing the scattered literals
- **`support/filters.py`** — `campaign_resolution` in both filter sets
- **`core/admin.py`** — `campaign_resolution` in `list_filter` and `list_display` of
  `ContactCampaignStatusAdmin`
- **`support/templates/campaign_statistics_detail.html`** — Resolution rows rendered in a loop; new
  filter field
- **`support/templates/all_campaigns_status_export.html`** — New filter field

## 📚 Technical Details

### Why `bulk_update` and not `save()`

`ContactCampaignStatus.last_action_date` is `auto_now=True`. With `save()`, every touched row would
read "last action: today", overwriting the date of the last **real** action and breaking the
`last_action_date_min/max` filters of `ContactCampaignStatusFilter`. `bulk_update` only writes the
fields it is given, so `last_action_date` stays as it is. The date of the forced close is readable
from the activity note and from the `LS` resolution instead.

The accepted trade-off: `Activity` has `HistoricalRecords`, and `bulk_update` fires no signals, so no
history rows are written for the close. The traceability already lives in the row itself (the
`close-lost-schedule` action plus the dated note) and in the CSV kept from the dry run; a synthetic
history of thousands of rows would add nothing.

### Query shape

The pairs are resolved in a single query and kept in a `{(contact_id, campaign_id): ccs}` dict —
never one query per activity. A pair with more than one dangling schedule (6 of them in production)
closes both activities but maps the campaign status only once.

### `USE_TZ`

This installation runs with `USE_TZ = False` (the Django 4 default), where `timezone.now()` returns a
naive datetime and `timezone.localdate()` raises. The command builds its cutoff with `make_aware`
only when `settings.USE_TZ` is on, so it keeps working in base-app installations that enable it.

### What is deliberately not touched

- **`ContactCampaignStatus.seller`** — nulling it would send those contacts to the "no seller" bucket
  of `AssignSellerView`, which is the opposite of closing them, and would break
  `campaign_statistics_per_seller`.
- **`Activity.datetime`** — the agreed date is information. (The manual close from the console does
  overwrite it with `now()`; this one does not.)
- **`resolution_reason`** — that is the rejection-reason list from `local_settings`; a lost schedule
  is not a rejection.
- **Subscriptions and `Campaign.active`** — out of scope.

## 🧪 Manual Testing

1. **Happy path — a contacted schedule is closed:**
   - Run `python manage.py populate_seller_console_actions`.
   - Pick a contact with a pending call activity dated before the cutoff, whose
     `ContactCampaignStatus` is in status 2 with resolution `SC`.
   - Run `python manage.py close_lost_schedule_activities --date 2026-05-31 --dry-run` and read the
     breakdown, then run it without `--dry-run`.
   - **Verify:** the activity is `Completed` with the `close-lost-schedule` action and a note
     appended below the original one; the campaign status is now 4 (ended with contact) with
     resolution `LS`; the contact no longer appears in the console's "act" queue; its
     `last_action_date` is unchanged.

2. **Edge case — a status that already holds a sale:**
   - Pick a pair whose `ContactCampaignStatus` has resolution `S1` or `S2` and a dangling schedule.
   - Run the command.
   - **Verify:** the activity is closed, but the campaign status keeps its status and its `S1`/`S2`
     resolution. This is the exact failure of the old command.

3. **Edge case — the cutoff date is inclusive:**
   - Create two schedules, one at 2026-05-31 23:30 and one at 2026-06-01 09:00.
   - Run with `--date 2026-05-31`.
   - **Verify:** the first is closed, the second is untouched.

4. **Edge case — an orphan schedule:**
   - Pick an activity with a campaign but no `ContactCampaignStatus` (there are 2 in production).
   - Run the command.
   - **Verify:** the activity is closed and the pair is listed in the summary under "Without
     ContactCampaignStatus".

5. **Idempotency:**
   - Run the command twice with the same date.
   - **Verify:** the second run reports "No schedules to close with the given parameters."

6. **The number is visible afterwards:**
   - Open the campaign statistics of a campaign that had dangling schedules.
   - **Verify:** the "Contactados" card shows a "Finalizado por agenda perdida" row with the count,
     "Agendado" dropped by the same amount, and `contacted_pct` did not move. Filtering by that
     resolution and exporting the CSV gives the list of affected contacts.

### Automated tests

```bash
python -W ignore manage.py test --settings=test_settings --keepdb tests.test_close_lost_schedule
```

23 tests covering the mapping of every status, sales protection, the inclusive cutoff, activities
without a campaign, non-call activities, pairs with two schedules, orphan schedules, `--dry-run`,
`--campaign`, idempotency, `last_action_date`, the `get_contacted_statuses()` guard rail, the missing
console action, the deprecated command, and the fact that `close-lost-schedule` survives the populate
while staying inactive. Four of them cover the panel: the `LS` row appearing with its count, the
old context keys still being written, a bucket adding up several codes, and filtering by
resolution.

## 📝 Deployment Notes

- **Migrations required:** `core.0122` and `support.0041`. Both are `AlterField` on choices only, so
  they are no-ops at the database level in PostgreSQL.
- **`populate_seller_console_actions` must be run after migrating.** Without it the command aborts,
  because the `close-lost-schedule` action does not exist.
- `compilemessages` is needed for the Spanish label ("Finalizado por agenda perdida") and for the
  activity note; the `.mo` file is not versioned.
- The run itself is a separate decision from the deploy. Recommended order in production:

  ```bash
  python manage.py migrate
  python manage.py populate_seller_console_actions
  python manage.py close_lost_schedule_activities --date 2026-05-31 --dry-run \
      --csv /tmp/lost_schedules_t1175.csv
  # hand the CSV and the summary to community management, then:
  python manage.py close_lost_schedule_activities --date 2026-05-31
  ```

- **Expected figures** (measured against the production dump of 2026-09-03): 1,173 activities across
  1,167 pairs; 1,124 pairs going to status 4, 40 to status 5, 1 already terminal, 2 without a
  campaign status. Only 57 pairs belong to active campaigns, so the impact on live queues is small.
- **Post-deploy check:** open `CampaignStatisticsDetailView` for an active campaign before and after
  and confirm `contacted_pct` did not move — that is the whole point of the conditional mapping. The
  panel now also shows the "Finalizado por agenda perdida" row, and both the panel and the
  all-campaigns export can be filtered by resolution.
- The panel and filter changes need no migration and are independent of the run: they are useful
  from the moment they are deployed.

## 🚀 Future Improvements

- Repair the 181 campaign statuses the old command overwrote on 2025-07-01. They are identifiable
  (`last_action_date='2025-07-01'` + `CW` + a subscription attributed to that campaign), but the
  original resolution is not recorded; `S2` is the likely one, since that is what `handle_direct_sale`
  and `mark_as_sale` set. Needs its own ticket and its own decision.
- Decide what to do with `expire_old_pending_activities`: it is labelled `scheduled` in `COMMANDS.md`
  but is in no crontab, and there is not a single row in status `E`. Either schedule it or drop it.
- Around 700 schedules from June to September 2026 are already overdue and stay out of this cutoff by
  explicit decision of community management — sellers can still work them. If that changes, the same
  command handles it: it is the same `--date`.

---

- **Date:** 2026-09-04
- **Author:** Tanya Tree + Claude Opus 5
- **Branch:** t1175
- **Type:** Feature (+ Bug Fix)
- **Modules affected:** Core, Support
