# The seller console validates or deletes each phone

- **Date:** 2026-11-17
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#3
- **Type:** Feature
- **Component:** Support (seller console), Core (Contact)
- **Impact:** User Experience, Data

## 🎯 Summary

The validation fields of Phone and Mobile (ladiaria/utopia-crm#456) had no way to be filled in day-to-day work. The seller console now has, on each number, a ✓ button that validates it and a ✗ one that deletes it as a wrong number. Also, closing a call where the seller spoke with the person validates the number without touching anything when the contact has only one: with two, the console can't tell which one answered, and the seller marks it.

## ✨ Changes

### 1. `Contact.mark_phone_validated()` and `Contact.remove_phone()`

**File:** `core/models.py`

```python
contact.mark_phone_validated("mobile", PhoneValidationSource.CALL_CENTER, user=request.user)
contact.remove_phone("phone", user=request.user, reason="Wrong number, ...")
```

Both save only the fields that change with `bulk_update_with_history`: a history record is kept, with the user and the reason, and `save()` is skipped. So they don't trigger the web sync contact by contact, like the scripts that cleaned the phones. `remove_phone` also clears the number's validation and, for the phone, its extension.

### 2. The buttons

**Files:** `support/templates/seller_console_phone_row.html`, `support/templates/seller_console.html`, `support/views/seller_console.py`, `support/urls.py`

The Phone and Mobile rows of the console move to their own template, built by `phone_row()`. The buttons POST with htmx to `seller_console_phone/<contact_id>/<field>/<validate|remove>/`, which answers with the new row. The ✗ asks first (`hx-confirm`). The POST carries the number the seller saw: if it changed meanwhile, nothing is touched and the row shows the current one. The view requires staff, CSRF, POST and htmx, and only takes `phone` and `mobile`.

### 3. Validation when closing the call

**File:** `support/views/seller_console.py`

`SellerConsoleView.validate_the_only_phone()` runs after the CCS is saved. It validates the number when:

- the action leaves the CCS as Contacted or Ended with contact (not a shift switch);
- the reason is not in `SELLER_CONSOLE_PHONE_NOT_VALIDATED_REASONS`;
- the contact has a single number among Phone, Mobile and Work phone, and it is Phone or Mobile.

## 📁 Modified Files

- **`core/models.py`** — `mark_phone_validated()`, `remove_phone()` and `_save_phone_fields()`
- **`support/views/seller_console.py`** — `phone_row()`, `seller_console_phone()` and `validate_the_only_phone()`
- **`support/templates/seller_console.html`** — The Phone and Mobile rows, with the new template
- **`support/urls.py`**, **`support/views/__init__.py`** — The buttons' URL
- **`locale/es/LC_MESSAGES/django.po`** — Translations
- **`CHANGELOG.md`** — Entry for this change

## 📁 Created Files

- **`support/templates/seller_console_phone_row.html`** — A Phone or Mobile row, with its buttons
- **`tests/test_seller_console_phones.py`** — The model methods, the buttons and the validation when closing the call

## 🧪 Manual Testing

1. **Normal case, validate:**
   - In the console, with a test contact with two numbers, click ✓ on one.
   - **Check:** "Validated" shows next to the number, only the ✗ is left, and what was typed in the activity is still there.

2. **Normal case, delete:**
   - Click ✗ on the other number and accept the question.
   - **Check:** The number is struck through with "Deleted as a wrong number"; the contact's history (admin) has the number, the user and the reason.

3. **Edge case, a single number:**
   - Close the call of a contact with a single number with "Not interested" and any reason except the setting's.
   - **Check:** The number is validated, with source Call center.

## 📝 Deployment Notes

- No migrations.
- **New optional setting:** `SELLER_CONSOLE_PHONE_NOT_VALIDATED_REASONS`, the reasons (`resolution_reason`) with which closing the call does not validate the number. Without it, any reason validates. At la diaria: "Número y email incorrectos" (12) and "Falleció" (14), `(12, 14)`.

## 🎓 Design Decisions

- **A wrong number is deleted, not flagged:** see the devnotes of #456.
- **With two numbers, the seller validates:** neither the CCS nor the activity records which number was dialed. Validating both blindly would vouch for a number that may be wrong.
- **The Work phone counts as another number** for the validation on closing: if the contact has one, the call may have gone there.
- **No button to undo a validation:** a wrong ✓ is rare and fixed by supervision. One more button per row confused more than it helped.

---

- **Date:** 2026-11-17
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl3-consola-telefonos
- **Type:** Feature
- **Modules affected:** core, support
