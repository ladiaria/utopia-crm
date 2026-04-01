# Do Not Call Warnings on Phone Fields

**Date:** 2026-03-23
**Author:** Tanya Tree + AI pair programmer
**Ticket:** t1063
**Type:** UX Improvement, Bug Fix
**Component:** Support, Core Models
**Impact:** User Experience, Data Integrity

## 🎯 Summary

Staff had no way to tell at a glance whether a contact's phone number was on the Do Not Call registry. The number appeared normally in contact detail views and in subscription/edit forms, with no indication that calling it could be a compliance issue. This change adds visible warnings throughout the interface: on the contact detail overview and information tabs the number is rendered in red with an ✕ icon and the message "Number in do not call list", and on edit forms (contact data and new subscription) the field label turns red with the same icon and message. Additionally, the underlying `Contact.do_not_call()` model method was hardened to handle cases where a phone attribute holds a plain string instead of a `PhoneNumber` object, which was causing a `'str' object has no attribute 'national_number'` crash in certain view flows.

## ✨ Changes

### 1. Do Not Call Warnings in Contact Detail Views

**Files:** `support/templates/contact_detail/tabs/_overview.html`, `support/templates/contact_detail/tabs/_information.html`

In both tabs, the `phone`, `mobile`, and `work_phone` display blocks now call the corresponding model methods (`do_not_call_phone`, `do_not_call_mobile`, `do_not_call_work_phone`) and conditionally render a warning. When flagged, the phone number link and surrounding text are wrapped in `text-danger`, the `tel:` link itself also gets `text-danger`, and a `fa-times-circle` icon plus a short message follow inline:

```html
{% if contact.do_not_call_phone %}
  <span class="text-danger">
    <a href="tel:{{ contact.phone }}" class="text-danger">{{ contact.phone.as_national }}</a>
    <i class="fas fa-times-circle ml-1" title="{% trans "Number in do not call list" %}"></i>
    <small>{% trans "Number in do not call list" %}</small>
  </span>
{% else %}
  <a href="tel:{{ contact.phone }}">{{ contact.phone.as_national }}</a>
{% endif %}
```

The same pattern applies to `mobile` and `work_phone` in both templates.

### 2. Do Not Call Warnings in the Contact Edit Form

**File:** `support/templates/create_contact/tabs/_data.html`

The labels for the Phone, Mobile, and Institutional phone fields check `contact.do_not_call_phone`, `contact.do_not_call_mobile`, and `contact.do_not_call_work_phone` respectively. When flagged the label renders in red with the icon and message instead of the plain label text. The check uses `{% if contact and contact.do_not_call_phone %}` so it is safely skipped on the contact creation form where no contact object exists yet:

```html
<label for="">
  {% if contact and contact.do_not_call_phone %}
    <span class="text-danger">
      <i class="fas fa-times-circle"></i> {% trans "Phone" %} — {% trans "Number in do not call list" %}
    </span>
  {% else %}
    {% trans "Phone" %}
  {% endif %}
</label>
```

### 3. Do Not Call Warnings in the New Subscription Form

**Files:** `support/templates/new_subscription.html`, `support/views/subscriptions.py` (base), `utopia-crm-ladiaria: views/subscriptions.py` (mixin)

The Phone and Mobile labels in `new_subscription.html` use template variables `dnc_phone` and `dnc_mobile` (booleans) rather than calling the model method directly. This avoids a crash that occurred when `contact.mobile` had been mutated to a raw string value during POST processing.

The `SubscriptionCreateView.get_context_data()` and `SubscriptionUpdateView.get_context_data()` in the base app now include these two variables by calling the model methods on the clean contact object. In the ladiaria extension, `LadiariaSubscriptionMixin.get_context_data()` reloads the contact from the database before computing the flags, ensuring the values reflect the stored phone data regardless of any in-memory mutations:

```python
# Reload contact from DB to ensure clean phone values for DNC checks
contact = Contact.objects.get(pk=self.contact.pk)
...
"dnc_phone": contact.do_not_call_phone(),
"dnc_mobile": contact.do_not_call_mobile(),
```

### 4. Hardened `Contact.do_not_call()` Against String Phone Values

**File:** `core/models.py`

The `do_not_call()` method previously assumed `number` was always a `PhoneNumber` object, calling `number.national_number` unconditionally. If `number` held a plain string (e.g. an empty string `""` from form cleaned data being set back onto the contact in memory), this raised `AttributeError: 'str' object has no attribute 'national_number'`. The method now handles all cases defensively:

```python
def do_not_call(self, phone_att="phone"):
    number = getattr(self, phone_att)
    if phone_att == "work_phone":
        return DoNotCallNumber.objects.filter(number__iexact=number).exists()
    elif not number:
        return False
    elif isinstance(number, str):
        return DoNotCallNumber.objects.filter(number__contains=number).exists()
    elif number.national_number is None:
        return False
    return DoNotCallNumber.objects.filter(number__contains=number.national_number).exists()
```

- Empty or `None` → returns `False` without error
- Plain string with a value → queries by string containment (same strategy as `work_phone`)
- `PhoneNumber` object → original behaviour unchanged

## 📁 Files Modified

- **`core/models.py`** — Hardened `Contact.do_not_call()` to handle string and empty phone values
- **`support/templates/contact_detail/tabs/_overview.html`** — Added DNC warnings for phone, mobile, and work_phone in the overview tab
- **`support/templates/contact_detail/tabs/_information.html`** — Added DNC warnings for phone, mobile, and work_phone in the information tab
- **`support/templates/create_contact/tabs/_data.html`** — Added DNC warnings to Phone, Mobile, and Institutional phone labels in the contact edit form
- **`support/templates/new_subscription.html`** — Changed phone/mobile labels to use `dnc_phone`/`dnc_mobile` boolean context variables
- **`support/views/subscriptions.py`** — Added `dnc_phone` and `dnc_mobile` to context in `SubscriptionCreateView` and `SubscriptionUpdateView`

## 📚 Technical Details

- The ladiaria `new_subscription` URL is handled by `LadiariaSubscriptionCreateView` / `LadiariaSubscriptionUpdateView` (class-based, in `utopia_crm_ladiaria/views/subscriptions.py`), not by the legacy `ladiaria_new_subscription` function-based view (which is now only reachable via `new_subscription_old`). The DNC context variables are injected via `LadiariaSubscriptionMixin.get_context_data()`.
- The DB reload in `LadiariaSubscriptionMixin.get_context_data()` is a defensive measure: in the legacy FBV, the view mutates `contact.phone`/`contact.mobile` in memory via `setattr` before attempting `contact.save()`. If that save fails (or the form is invalid and falls through to the render), the in-memory contact object may hold cleaned-data values rather than the original `PhoneNumber` objects, triggering the crash.
- The `do_not_call_*` methods are called directly from templates only where the contact object is guaranteed to be a fresh DB instance (detail views). In form views where the contact may be mutated, booleans are pre-computed in Python and passed as context.

## 🧪 Manual Testing

1. **Happy path — DNC number shown in red on overview tab:**
   - Add a phone number to `DoNotCallNumber` via the Django admin (e.g. a national number string like `099123456`).
   - Open a contact whose `phone` or `mobile` matches that number.
   - Navigate to the Overview tab.
   - **Verify:** The matching phone number appears in red, with a ✕ icon and "Number in do not call list" label. Non-matching numbers appear normally.

2. **Happy path — DNC warning on contact edit form:**
   - Open the edit form for the contact from scenario 1.
   - **Verify:** The Phone (or Mobile) label is rendered in red with the ✕ icon and message. Other labels are unaffected.

3. **Happy path — DNC warning on new subscription form:**
   - Navigate to the New Subscription page for the same contact.
   - **Verify:** The Phone and/or Mobile label shows the DNC warning in red.

4. **Edge case — contact with no phone number:**
   - Open a contact that has no `phone` and no `mobile` set.
   - Navigate to Overview, Information, and Edit tabs.
   - **Verify:** No DNC warning appears; no errors are raised.

5. **Edge case — phone number stored as empty string:**
   - This is an internal edge case; verify by checking the do_not_call method handles it.
   - **Verify:** No `AttributeError` is raised; the method returns `False` for empty strings.

6. **Edge case — create contact form (no existing contact object):**
   - Navigate to the New Contact creation form.
   - **Verify:** Phone, Mobile, and Institutional phone labels render normally (no DNC check attempted on a non-existent contact).

## 📝 Deployment Notes

- No database migrations required.
- No configuration changes needed.
- No management commands to run.

## 🚀 Future Improvements

- Extend DNC warnings to the seller console / campaign call views where agents make outbound calls
- Consider showing a non-blocking modal confirmation if a user tries to click a `tel:` link on a DNC-flagged number

---

**Date:** 2026-03-23
**Author:** Tanya Tree + AI pair programmer
**Branch:** t1063
**Type:** UX Improvement, Bug Fix
**Modules affected:** Core, Support, Subscriptions
