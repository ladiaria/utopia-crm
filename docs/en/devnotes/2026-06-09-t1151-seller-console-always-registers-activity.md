# Fix: Seller Console Skips Activity Registration on Terminal Actions and Loses Console Action When Scheduling

- **Date:** 2026-06-09
- **Author:** Tanya Tree + Claude Opus 4.8
- **Ticket:** t1151
- **Type:** Bug Fix
- **Component:** Support — Seller Console, Core Models (Activity, ContactCampaignStatus)
- **Impact:** Data Integrity, Activity Tracking, Campaign Reporting

## 🎯 Summary

When a seller resolved a not-yet-contacted contact from the seller console with a terminal action such as "No interesado" (Not interested), the contact's campaign status was updated (e.g. to "Ended with contact" with resolution "Not interested") but **no `Activity` record was created**. The contact ended up with a closed campaign status and an empty Activities tab, which made it impossible to audit what the seller actually did. The cause was an early `return` in `register_new_activity` for any action whose `action_type` was `DECLINED`. Separately, when a seller used the "Agendar" (Schedule) action, the resulting pending future activity (the scheduled call) was created **without** a `seller_console_action`, so the scheduled call did not show the "Agendar" action in the activity list. This change makes the console always register a completed activity for any POSTed resolution in the `new` category (even with empty notes), and stamps the scheduled pending activity with the `schedule` console action.

## ✨ Changes

### 1. Always register a completed activity for terminal actions in the `new` category

**File:** `support/views/seller_console.py`

`register_new_activity` short-circuited for `DECLINED` actions, so contacts resolved as "Not interested", "Do not call", "Logistics", etc. from the not-contacted queue never got an activity:

```python
# Before — terminal actions left the contact with no activity
seller_console_action = self.get_seller_console_action(result, required=False)
# If the ACTION_TYPE was DECLINED, we won't create a new activity
if seller_console_action.action_type == SellerConsoleAction.ACTION_TYPES.DECLINED:
    return
```

The early return was removed and replaced with a defensive guard for a missing action. The final `category == "new"` block now always creates a completed activity, with empty notes coerced to an empty string:

```python
# After — any POSTed resolution in "new" registers a completed activity
seller_console_action = self.get_seller_console_action(result, required=False)
if not seller_console_action:
    return

# ... (CALL_LATER / NOT_FOUND / KEEP_CONTACTS_IN_CAMPAIGNS_INDEFINITELY branches unchanged) ...

if category == "new":
    Activity.objects.create(
        contact=contact,
        activity_type="C",
        datetime=datetime.now(),
        campaign=campaign,
        seller=seller,
        status="C",  # Completed
        notes=notes or "",
        seller_console_action=seller_console_action,
    )
```

The only path that intentionally leaves a contact without an activity is the "Omitir y pasar al siguiente contacto" link, which is a plain `<a href>` that only changes the `offset` and does not POST a `result` — so it never reaches this code.

### 2. Stamp the scheduled pending activity with the console action

**File:** `support/views/seller_console.py`

`create_scheduled_activity` did not set `seller_console_action`, so the scheduled future call had no console action attached:

```python
# Before
def create_scheduled_activity(self, contact, campaign, seller, call_datetime):
    return Activity.objects.create(
        contact=contact,
        activity_type="C",
        datetime=call_datetime,
        campaign=campaign,
        seller=seller,
        notes="{} {}".format(_("Scheduled for"), call_datetime),
    )
```

The method now accepts and sets `seller_console_action`, and `handle_post_request` passes the `schedule` action through:

```python
# After
def create_scheduled_activity(self, contact, campaign, seller, call_datetime, seller_console_action=None):
    return Activity.objects.create(
        contact=contact,
        activity_type="C",
        datetime=call_datetime,
        campaign=campaign,
        seller=seller,
        seller_console_action=seller_console_action,
        notes="{} {}".format(_("Scheduled for"), call_datetime),
    )

# in handle_post_request:
if seller_console_action.action_type == SellerConsoleAction.ACTION_TYPES.SCHEDULED:
    call_datetime = self.get_call_datetime(data)
    self.create_scheduled_activity(contact, campaign, seller, call_datetime, seller_console_action)
```

### 3. Regression tests

**File:** `tests/test_seller_console.py` (new)

Two test classes were added:

- **`TestSellerConsoleRegistersActivity`** — verifies that a `DECLINED` action ("not-interested") in the `new` category creates exactly one completed activity (with and without notes), and that the `ContactCampaignStatus` is updated with the action's status, resolution, and `last_console_action`.
- **`TestSellerConsoleScheduledActivity`** — verifies that scheduling a contact creates a pending future activity stamped with the `schedule` console action.

## 📁 Files Modified

- **`support/views/seller_console.py`** — Removed the `DECLINED` early return in `register_new_activity`; coerced empty notes to `""`; threaded `seller_console_action` through `create_scheduled_activity` and its caller

## 📁 Files Created

- **`tests/test_seller_console.py`** — Regression tests for activity registration on terminal actions and for the scheduled-activity console action

## 📚 Technical Details

**Why the bug only showed in the `new` queue:**

The `act` category (contacts that already had a pending activity) updates the existing `Activity` in `handle_post_request` (sets notes, status to completed, datetime to now, and the console action), so those contacts always retained a record. The missing-activity bug only affected the `new` (not-yet-contacted) queue, which relied entirely on `register_new_activity` — exactly the path that returned early for `DECLINED`.

**Why stamping the pending activity is safe:**

Scheduling creates two activities: a completed one (the record that the seller scheduled today, which already carried the `schedule` action) and a pending future one (the call to be made). When the seller later attends that pending call from the `act` queue, `handle_post_request` overwrites its `seller_console_action` with whatever resolution the seller chooses. So the pending activity is born tagged "Agendar" and is re-tagged with the real resolution on completion.

## 🧪 Manual Testing

1. **Happy path — "Not interested" on a new contact creates an activity:**
   - Open the seller console for a campaign in the `new` category with a not-contacted contact assigned to the seller.
   - Click "No interesado" and submit (leave notes empty).
   - **Verify:** The contact's campaign status moves to "Finalizado con contacto" with resolution "No interesado", AND the Activities tab now shows one completed activity with the "No interesado" console action.

2. **Happy path — scheduling stamps the pending call:**
   - In the `new` category, click "Agendar", pick a future date/time, and submit.
   - **Verify:** A pending future activity exists for the chosen date with the "Agendar" console action attached (visible/colored as such in the console queue).

3. **Edge case — empty notes still create an activity:**
   - Resolve a new contact with "No llamar" leaving the notes field empty.
   - **Verify:** A completed activity is created with empty notes and the "No llamar" console action.

4. **Edge case — "skip to next" does NOT create an activity:**
   - On a new contact, click "Omitir y pasar al siguiente contacto".
   - **Verify:** No activity is created and the campaign status is unchanged; the console simply advances to the next contact.

## 📝 Deployment Notes

- No database migrations required.
- No configuration changes required.
- The change is purely logic-level inside the seller console view. Historical contacts that were resolved without an activity before this fix are not backfilled.

## 🎓 Design Decisions

The fix intentionally keeps the "skip to next" link as the only way to leave a contact without an activity, because that action is a navigation aid rather than a resolution — it does not POST a `result`. Every action that does POST a resolution now produces an activity, so the activity log becomes a complete audit trail of seller decisions. Empty notes are stored as an empty string rather than blocking the action, matching the requirement that an activity must always be created even when the seller provides no comment.

## 🚀 Future Improvements

- Preserve the originally scheduled date when a pending scheduled activity is completed (currently `datetime` is overwritten with `now()` on completion, losing the date the call was scheduled for). Tracked separately, outside t1151.
- Surface or auto-close stale pending scheduled activities whose date is far in the past and were never attended.

---

**Date:** 2026-06-09
**Author:** Tanya Tree + Claude Opus 4.8
**Branch:** t1151
**Type:** Bug Fix
**Modules affected:** Support, Core (Activity, ContactCampaignStatus)
