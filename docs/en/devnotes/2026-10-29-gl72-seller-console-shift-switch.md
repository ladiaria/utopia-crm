# The seller console switches shifts by the time of day

- **Date:** 2026-10-29
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** gl72-cambio-de-turno (it/utopia-crm-ladiaria#72)
- **Type:** Enhancement
- **Component:** Support (seller console, campaign statistics)
- **Impact:** User Experience, Reporting

## 🎯 Summary

The call center works in two shifts (`support.Shift`). When nobody answers the first call to a contact in a campaign,
the next try should come from the other shift, but sellers had to remember to press "Switch to afternoon/morning" by
hand, and both buttons were always shown. Now the first "not found" call to a contact in a campaign moves it to the
other shift by the time of day, the seller is told so, and during a shift only the move to the other one is offered.
The call is still registered as a "not found" one, so a customization can count unanswered calls (la diaria enables a
WhatsApp button after three of them: one in the first shift and two in the second). Contacts moved this way no longer
count as contacted in the statistics, since nobody answered.

## ✨ Changes

### 1. Shift of the moment

**File:** `support/models.py`

- `Shift.contains(moment)`: whether the time falls in the shift. It compares by the minute with an inclusive end, so
  there is no gap between shifts whether the end is set as `14:59` or `14:59:59`.
- `Shift.switch_status_at(moment)`: `SWITCH_TO_AFTERNOON` during the morning shift, `SWITCH_TO_MORNING` during the
  afternoon one, `None` outside both. The morning shift is the first by start time and the afternoon one the second,
  so the names don't matter. With other than exactly two shifts it returns `None` and nothing changes.

### 2. First "not found" switches the shift

**File:** `support/views/seller_console.py`

`get_first_not_found_switch_status()` returns the status to switch to when the action is of type `NOT_FOUND`, there is
no previous completed call of that type for the contact in the campaign (from any seller), and the time falls in a
shift. It looks at the activities and not at the campaign status, because assigning sellers to the other shift sets
the status back to "not yet contacted".

When it applies:

- The `ContactCampaignStatus` gets that status and no seller, as with the manual buttons; `last_console_action` stays
  "not found" and the campaign resolution is the action's, as before.
- The activity is completed with the "not found" action, as always.
- No new pending activity is created (neither the one of the `act` queue nor the one of
  `KEEP_CONTACTS_IN_CAMPAIGNS_INDEFINITELY`): the contact leaves this seller's queues.
- The offset is not incremented, since the contact leaves the list and the next one is already there.
- The seller gets a warning (yellow) instead of the usual success message, saying the contact was moved to the
  afternoon or morning shift.

`SELLER_CONSOLE_FIRST_NOT_FOUND_SWITCHES_SHIFT = False` turns this off; it defaults to `True`.

### 3. Only the move to the other shift

**Files:** `support/views/seller_console.py`, `support/templates/seller_console.html`

The context has `show_move_morning` and `show_move_afternoon`: during the morning shift only "Switch to afternoon" is
shown, during the afternoon one only "Switch to morning", and both outside the shifts. The POST rejects a move to the
current shift. This does not depend on the setting.

### 4. Not counted as contacted

**Files:** `core/choices.py`, `support/views/all_views.py`

`get_contacted_q()` is `status__in=get_contacted_statuses()` minus the rows in a switch status whose last console action
is a "not found" one. The six statistics that counted contacted rows (campaign list and detail, per seller and seller
performance) use it. Rows without a last console action still count.

## 📁 Files Modified

- **`support/models.py`** — `Shift.contains()` and `Shift.switch_status_at()`.
- **`support/views/seller_console.py`** — First "not found" shift switch, its warning, the POST check and the button
  flags.
- **`support/templates/seller_console.html`** — Each shift button shown by its flag.
- **`core/choices.py`** — `get_contacted_q()`.
- **`support/views/all_views.py`** — Contacted counts with `get_contacted_q()`.
- **`local_settings_sample.py`** — `SELLER_CONSOLE_FIRST_NOT_FOUND_SWITCHES_SHIFT`.
- **`locale/es/LC_MESSAGES/django.po`** — The three new strings.
- **`tests/test_seller_console.py`** — 13 new tests: shift of the moment (edges, no gap, outside, not two shifts),
  first "not found" in each shift, second one, outside the shifts, setting off, `act` queue, buttons shown, move to the
  current shift rejected, and `get_contacted_q()`.
- **`CHANGELOG.md`** — Entry.

## 🧪 Manual Testing

1. **First "not found" in the morning (happy path):**
   - Load two shifts in the admin (e.g. 09:00–14:59:59 and 15:00–21:00). During the morning one, open the seller
     console on a contact that was never called in the campaign.
   - Press "Not found".
   - **Verify:** a yellow warning says the contact was moved to the afternoon shift; the console shows the next contact
     (not the one after it); the contact appears under "afternoon" in campaign distribution; its activity has the "not
     found" action.

2. **Second "not found":**
   - Assign that contact to a seller of the afternoon shift and, during the afternoon, press "Not found" on it.
   - **Verify:** the usual green message; the contact stays with the seller as "called, could not contact".

3. **Shift buttons:**
   - Open the console during the morning, the afternoon and outside both shifts.
   - **Verify:** only "Switch to afternoon", only "Switch to morning", and both, respectively.

4. **Outside the shifts and setting off:**
   - Press "Not found" at 22:00, and again during a shift with `SELLER_CONSOLE_FIRST_NOT_FOUND_SWITCHES_SHIFT = False`.
   - **Verify:** both behave as before this change.

## 📝 Deployment Notes

- No database migrations required.
- Recompile translations: `python manage.py compilemessages -l es`.
- Check that exactly two shifts are loaded (Support → Shifts). Without them nothing changes.
- The behaviour is on by default; set `SELLER_CONSOLE_FIRST_NOT_FOUND_SWITCHES_SHIFT = False` to keep the old one.

## 🎓 Design Decisions

- **Shifts by start time, not by name:** the base app can't assume shift names, and two shifts ordered by start time
  are unambiguous.
- **"First" from the activities:** the campaign status goes back to 1 when the contact is assigned to the other shift,
  so it can't tell whether there was a previous "not found".
- **The call stays a "not found" one:** the shift switch is a consequence of the call, not a different result, and
  counts of unanswered calls depend on it.

---

- **Date:** 2026-10-29
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl72-cambio-de-turno
- **Type:** Enhancement
- **Modules affected:** Support, Core
