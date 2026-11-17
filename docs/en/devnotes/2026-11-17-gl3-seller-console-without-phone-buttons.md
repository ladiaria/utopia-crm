# The seller console no longer deletes or validates phones by hand

- **Date:** 2026-11-17
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#3
- **Type:** Change
- **Component:** Support (seller console, subscription form), Core (Contact)
- **Impact:** User Experience, Data

## 🎯 Summary

Supervision does not want sellers deleting numbers from the console: deleting a wrong number has to go through a rule agreed with them. So the ✓ and ✗ buttons that ladiaria/utopia-crm#457 put on each Phone and Mobile row are gone, and so is their endpoint. Validating a number is now only automatic, when the contact has a single number and the seller spoke with the person: a scheduled call, a call declined or ended with contact (unless the reason says whoever answered was not the person), and, new, a sale from the console.

## ✨ Changes

### 1. `Contact.validate_the_only_phone()`

**File:** `core/models.py`

```python
contact.validate_the_only_phone(PhoneValidationSource.CALL_CENTER, user=request.user)
```

The rule that lived in the console view moves to the model, so the call result and the sale share it: if Phone or Mobile is the contact's only number (the Work phone counts as another number), it is validated with `mark_phone_validated()`. It returns the field it validated, or `None`.

### 2. A sale from the console validates the number

**File:** `support/views/subscriptions.py`

`SubscriptionMixin.get_redirect_url_and_sales_record()` calls `validate_the_only_phone()` when the sale comes from the console: a direct sale (`?new=`) or a sale from a scheduled activity (`?act=`). It reads the contact from the database, because a number typed in the form may not have been saved (for example, if the save failed against the web). A subscription made from the contact detail page validates nothing.

### 3. The buttons are gone

**Files:** `support/templates/seller_console.html`, `support/views/seller_console.py`, `support/urls.py`, `support/views/__init__.py`

The Phone and Mobile rows go back to how they were before #457, with the "Validated" badge and no buttons. `seller_console_phone_row.html`, `phone_row()`, the `seller_console_phone` view and its URL are deleted, and so are their translations. `SellerConsoleView.validate_the_only_phone()` keeps the conditions of the call result (Contacted or Ended with contact, no shift switch, reason not in `SELLER_CONSOLE_PHONE_NOT_VALIDATED_REASONS`) and delegates the rest to the model.

`Contact.remove_phone()` stays: nothing calls it now, but it is what the agreed deletion rule will use.

## 📁 Modified Files

- **`core/models.py`** — `validate_the_only_phone()`
- **`support/views/seller_console.py`** — No `phone_row()` or `seller_console_phone()`; `validate_the_only_phone()` uses the model
- **`support/views/subscriptions.py`** — The sale from the console validates the number
- **`support/templates/seller_console.html`** — The Phone and Mobile rows without buttons
- **`support/urls.py`**, **`support/views/__init__.py`** — No buttons' URL
- **`locale/es/LC_MESSAGES/django.po`** — The buttons' translations removed
- **`tests/test_seller_console_phones.py`** — No button tests; tests for the model method, scheduling, both reasons, the sale and the console without buttons
- **`CHANGELOG.md`** — Entry for this change

## 📁 Deleted Files

- **`support/templates/seller_console_phone_row.html`** — The row with the buttons

## 🧪 Manual Testing

1. **Normal case, sale:**
   - In the console, with a test contact that only has a Mobile, make a sale from the "Sell" button.
   - **Check:** The Mobile shows "Validated", with source Call center, and the contact's history (admin) has the seller as the author.

2. **Normal case, scheduling:**
   - With another contact with a single number, schedule a call.
   - **Check:** The number is validated.

3. **Edge case, wrong reason:**
   - Close the call of a contact with a single number with "Not interested" and the reason "Número y email incorrectos".
   - **Check:** The number is not validated and is not deleted.

4. **Edge case, two numbers:**
   - Make a sale to a contact with Phone and Mobile.
   - **Check:** Neither is validated.

5. **No buttons:**
   - **Check:** The Phone and Mobile rows of the console have no ✓ or ✗.

## 📝 Deployment Notes

- No migrations.
- No new settings. `SELLER_CONSOLE_PHONE_NOT_VALIDATED_REASONS` keeps working as before.

## 🎓 Design Decisions

- **No permission to keep the ✗ for a few:** a permission-gated ✗ was considered, but supervision wants a rule, not a person deciding at the console. When the rule is agreed, the deletion will be a script or a process, not a button.
- **No ✓ either:** with no ✗, a ✓ alone invites validating by feel. Validating stays tied to what the seller already records: the call result or the sale.
- **With two numbers nothing is validated:** the CCS and the activity do not record which number was dialed, and validating both would vouch for a number that may be wrong.
- **The sale reads the contact from the database:** the form may change the numbers, and if saving the contact failed, the object in memory has numbers that are not stored.

---

- **Date:** 2026-11-17
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl3-consola-sin-botones
- **Type:** Change
- **Modules affected:** core, support
