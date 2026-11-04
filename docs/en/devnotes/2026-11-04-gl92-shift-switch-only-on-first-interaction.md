# The "not found" shift switch only applies to the first interaction

- **Date:** 2026-11-04
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** gl92-primera-interaccion-no-encontrado (it/utopia-crm-ladiaria#92)
- **Type:** Bug fix
- **Component:** Support (seller console)
- **Impact:** User Experience

## 🎯 Summary

Since gl72 (it/utopia-crm-ladiaria#72), a "not found" call moves the contact to the other shift when it is the first
"not found" call to that contact in the campaign. The call center wanted something stricter: the switch should only
happen when the **first interaction** with the contact in the campaign is a "not found" call. With the old rule, a
contact that had been scheduled, or that had an earlier "call later", switched shifts the first time it did not answer,
which is not what the shift switch is meant for. Now any earlier activity of the contact in the campaign keeps the
usual behaviour.

## ✨ Changes

### 1. Any earlier activity in the campaign is an earlier interaction

**File:** `support/views/seller_console.py`

`get_first_not_found_switch_status()` used to look only for an earlier completed call whose console action is of the
`NOT_FOUND` type. It now looks for any activity of the contact in the campaign, of any type, status or seller:

```python
if Activity.objects.filter(contact=contact, campaign=campaign).exists():
    return None
return Shift.switch_status_at(moment)
```

It runs before the current call is registered, so every activity found is an earlier one. As a consequence:

- **"act" queue (scheduled calls, "call later"):** never switches, because the pending activity being completed is
  itself an earlier interaction. The contact keeps its seller, gets its new pending activity and the offset moves on,
  as before gl72.
- **"new" queue, no activity in the campaign:** switches as before.
- **The other shift:** does not switch again, because the first "not found" call is already registered.
- **Activities in other campaigns** don't count.

Everything else from gl72 stays as it was: the call is registered as a "not found" one, the warning to the seller, the
shift buttons by the time of day and `SELLER_CONSOLE_FIRST_NOT_FOUND_SWITCHES_SHIFT`.

### 2. Tests

**File:** `tests/test_seller_console.py`

- The "act" queue test is inverted: a contact with a pending scheduled call no longer switches shifts, keeps its seller
  and its pending activity, and gets the usual success message and offset.
- New: a "not found" call after a "call later" one in the "new" queue behaves as usual.
- New: an earlier activity of another type and with no seller (a call center WhatsApp message) also counts.
- New: an activity in another campaign does not count, so the contact still switches.

## 📁 Files Modified

- **`support/views/seller_console.py`** — `get_first_not_found_switch_status()` looks for any earlier activity in the
  campaign; docstring updated.
- **`tests/test_seller_console.py`** — "act" queue test inverted and three new tests.
- **`local_settings_sample.py`** — The comment of `SELLER_CONSOLE_FIRST_NOT_FOUND_SWITCHES_SHIFT` describes the new
  rule.
- **`CHANGELOG.md`** — Entry.

## 🧪 Manual Testing

1. **First interaction is "not found" (happy path):**
   - With two shifts loaded, during the morning one, open the seller console on a contact with no activity in the
     campaign.
   - Press "Not found".
   - **Verify:** the yellow warning says the contact was moved to the afternoon shift, as in gl72.

2. **Scheduled contact:**
   - Schedule a call for a contact in the campaign and, once it is due, open it from the activities queue during a
     shift.
   - Press "Not found".
   - **Verify:** the usual green message; the contact stays with the seller, with a new pending activity, and is not
     moved to the other shift.

3. **"Call later" first:**
   - On a contact with no activity in the campaign, press "Call later", then come back to it and press "Not found".
   - **Verify:** the usual green message and no shift switch.

## 📝 Deployment Notes

- No migrations required.
- No new translations.
- Contacts already moved by the old rule are not moved back.

## 🎓 Design Decisions

- **Any activity, not only console calls:** a WhatsApp message from the call center, an email or a direct sale
  registered in the campaign also mean someone already dealt with the contact there.
- **Earlier stays in the same campaign count:** if a contact leaves a campaign and is added again, its old activities
  still point to the campaign and keep the usual behaviour. The rule is about the contact in the campaign, not about
  the current stay.

---

- **Date:** 2026-11-04
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl92-primera-interaccion-no-encontrado
- **Change type:** Bug fix
- **Affected modules:** Support
