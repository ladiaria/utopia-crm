# Each of the contact's phones records whether it is validated

- **Date:** 2026-11-17
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#3
- **Type:** Feature
- **Component:** Core (Contact), Support (contact detail, seller console)
- **Impact:** Data, User Experience

## 🎯 Summary

The call center had no way to tell a number already confirmed as the person's from one nobody ever tried. Phone and Mobile (`phone`, `mobile`) now record when they were validated and how: call center, incoming call or web. The contact detail and the seller console show a "Validated" badge next to the number, with the date and source in its tooltip. Changing the number clears its validation, unless the same change validates the new number.

This PR adds the fields and their rule. Who validates (the initial load from Distribution's list, the seller console buttons) comes in other changes.

## ✨ Changes

### 1. New `Contact` fields

**Files:** `core/models.py`, `core/choices.py`, `core/migrations/0126_contact_phone_validation.py`

```python
phone_validated_at = models.DateTimeField(blank=True, null=True, ...)
phone_validation_source = models.CharField(blank=True, default="", max_length=16,
                                           choices=PhoneValidationSource.choices, ...)
mobile_validated_at = ...
mobile_validation_source = ...
```

`PhoneValidationSource`: `call_center`, `incoming_call`, `web`. A number with no date is unverified. `work_phone` has no validation: it holds numbers the person confirms are right even when they don't pass `PhoneNumberField`.

### 2. Changing the number clears its validation

**File:** `core/models.py`

`Contact.from_db` keeps the numbers and their dates as loaded, and `save()` calls `reset_changed_phone_validations()`. When a number changed and its date did not, it clears the date and the source. When both changed, whoever changed the number also validated the new one, and that is kept. Numbers are compared normalized: `099 123 456` and `+59899123456` are the same and keep their validation. With `update_fields` only the numbers being saved count, and the cleared fields are added to the list.

`bulk_update()` and `update()` skip `save()`: whoever changes numbers in bulk clears their validation by hand.

### 3. The "Validated" badge

**Files:** `support/templates/includes/_phone_validation.html`, `support/templates/contact_detail/tabs/_overview.html`, `support/templates/contact_detail/tabs/_information.html`, `support/templates/seller_console.html`

An include that takes the date and the source, and renders nothing for an unverified number.

### 4. Admin

**File:** `core/admin.py`

The four fields show in the contact's admin page, read only: validation is set by the processes that confirm a number.

## 📁 Modified Files

- **`core/models.py`** — The fields, `from_db`, `reset_changed_phone_validations()` and `save()`
- **`core/choices.py`** — `PhoneValidationSource`
- **`core/admin.py`** — The fields, read only
- **`support/templates/contact_detail/tabs/_overview.html`**, **`_information.html`**, **`support/templates/seller_console.html`** — The badge next to each number
- **`locale/es/LC_MESSAGES/django.po`** — Translations
- **`CHANGELOG.md`** — Entry for this change

## 📁 Created Files

- **`core/migrations/0126_contact_phone_validation.py`** — The fields on `Contact` and `HistoricalContact`
- **`support/templates/includes/_phone_validation.html`** — The badge
- **`tests/test_phone_validation.py`** — The `save()` rule, the badge on the contact detail and the admin

## 🧪 Manual Testing

1. **Normal case, a validated number:**
   - In a shell, give a contact `phone_validated_at` and `phone_validation_source="call_center"` with `update()`.
   - **Check:** The contact detail (overview and Information) and the seller console show "Validated" next to the phone, and the tooltip shows the date and "Call center".

2. **Normal case, changing the number:**
   - Edit that contact's phone from the contact detail.
   - **Check:** The badge is gone and the admin shows both fields empty.

3. **Edge case, the same number written otherwise:**
   - Edit the phone and save it with spaces or without the international prefix.
   - **Check:** The badge stays.

## 📝 Deployment Notes

- **Migration:** `core.0126_contact_phone_validation`. Adds four columns to `core_contact` and `core_historicalcontact`. Since PostgreSQL 11 a new column with a default does not rewrite the table, so it runs fast even with millions of rows.
- No new settings.

## 🎓 Design Decisions

- **An invalid number is deleted, not flagged.** A number kept as invalid would still be used by everything that reads `phone` and `mobile` directly (SMS notices, WhatsApp, caller lookup, exports, the web sync), and each of them would have to learn to skip it. The contact's history already keeps the deleted number, with the date, the user and the reason. So whatever is in the field is either validated or unverified, never "known to be wrong".
- **A date and a source instead of a boolean:** the date allows rules like "validated in the last 3 years", and the source tells how much the validation weighs. An empty date is already the "no".
- **The rule lives in `save()`, not in the forms:** the number changes from the contact detail, the admin, the web API and a customization package's processes. Putting it in the model covers them all.
- **The Phone 1 / Phone 2 labels are left for another change:** they touch texts across the whole interface.

---

- **Date:** 2026-11-17
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl3-telefonos-validados
- **Type:** Feature
- **Modules affected:** core, support
