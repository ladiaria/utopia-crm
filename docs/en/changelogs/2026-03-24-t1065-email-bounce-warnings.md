# Email Bounce Warnings on Email Fields

**Date:** 2026-03-24
**Author:** Tanya Tree + AI pair programmer
**Ticket:** t1065
**Type:** UX Improvement
**Component:** Support, Core Models
**Impact:** User Experience, Data Integrity

## 🎯 Summary

Staff had no visual indication that a contact's email address was flagged in the `EmailBounceActionLog` model. The address appeared normally in all contact detail views and in subscription and seller console forms, with no indication that messages to that address have bounced. This change adds visible warnings throughout the interface: on the contact detail overview and information tabs the email address is rendered in red with a ✕ icon and the bounce action type displayed inline, and on edit forms (contact data and new subscription) and the seller console the email field label or table row turns red with the same information. The implementation mirrors the pattern introduced for Do Not Call phone numbers in t1063.

## ✨ Changes

### 1. New `get_email_bounce_action()` Method on Contact

**File:** `core/models.py`

A new method on `Contact` retrieves the most recent `EmailBounceActionLog` entry for the contact's email address (ordered by `-created`), returning `None` if the email is blank or no log entry exists:

```python
def get_email_bounce_action(self):
    if not self.email:
        return None
    return EmailBounceActionLog.objects.filter(email=self.email).order_by("-created").first()
```

The method returns the full model instance so templates can call `get_action_display` to get the human-readable action name (e.g. "invalid email" or "max bounce reached"). A `{% with %}` block is used in every template to avoid calling the method — and hitting the database — more than once per render.

### 2. Email Bounce Warnings in Contact Detail Views

**Files:** `support/templates/contact_detail/tabs/_overview.html`, `support/templates/contact_detail/tabs/_information.html`

In both tabs, the email display block now calls `contact.get_email_bounce_action` and conditionally renders a warning. When a bounce log entry exists, the `mailto:` link and surrounding text are wrapped in `text-danger`, a `fa-times-circle` icon is added, and the action name follows as a `<small>` element:

```html
{% with email_bounce=contact.get_email_bounce_action %}
  {% if contact.email %}
    {% if email_bounce %}
      <span class="text-danger">
        <a href="mailto:{{ contact.email }}" class="text-danger">{{ contact.email }}</a>
        <i class="fas fa-times-circle ml-1" title="{{ email_bounce.get_action_display }}"></i>
        <small>{{ email_bounce.get_action_display }}</small>
      </span>
    {% else %}
      <a href="mailto:{{ contact.email }}">{{ contact.email }}</a>
    {% endif %}
  {% else %}
    -
  {% endif %}
{% endwith %}
```

### 3. Email Bounce Warning in the Contact Edit Form

**File:** `support/templates/create_contact/tabs/_data.html`

The Email field label now checks `contact.get_email_bounce_action`. When flagged, the label renders in red with a ✕ icon and the action name. The outer `{% if contact %}` guard ensures the check is skipped safely on the new-contact creation form where no contact object yet exists:

```html
<label for="">
  {% if contact %}
    {% with email_bounce=contact.get_email_bounce_action %}
      {% if email_bounce %}
        <span class="text-danger">
          <i class="fas fa-times-circle"></i> {% trans "Email" %} — {{ email_bounce.get_action_display }}
        </span>
      {% else %}
        {% trans "Email" %}
      {% endif %}
    {% endwith %}
  {% else %}
    {% trans "Email" %}
  {% endif %}
</label>
```

### 4. Email Bounce Warning in the New Subscription Form

**File:** `support/templates/new_subscription.html`

The Email field label uses `contact.get_email_bounce_action` directly (the `contact` object is always present in this view). When a bounce log entry exists, the label renders in red with icon and action name, mirroring the DNC phone label pattern already in use in the same template:

```html
<label for="id_email">
  {% with email_bounce=contact.get_email_bounce_action %}
    {% if email_bounce %}
      <span class="text-danger">
        <i class="fas fa-times-circle"></i> {{ form.email.label }} — {{ email_bounce.get_action_display }}
      </span>
    {% else %}
      {{ form.email.label }}
    {% endif %}
  {% endwith %}
</label>
```

### 5. Email Bounce Warning in the Seller Console

**File:** `support/templates/seller_console.html`

The email table row now checks `contact.get_email_bounce_action`. When flagged, the row receives `class="table-danger"` (matching the style used for DNC phone rows in the same template) and the action name is prepended to the email address as a prefix label:

```html
{% with email_bounce=contact.get_email_bounce_action %}
  <tr {% if email_bounce %}class="table-danger"{% endif %}>
    <td><i class="fas fa-at"></i> {% trans "Email" %}:</td>
    <td>
      {% if email_bounce %}<span>{{ email_bounce.get_action_display }}:</span> {% endif %}
      {{ contact.email }}
    </td>
  </tr>
{% endwith %}
```

## 📁 Files Modified

- **`core/models.py`** — Added `Contact.get_email_bounce_action()` method
- **`support/templates/contact_detail/tabs/_overview.html`** — Added email bounce warning to the overview tab email display
- **`support/templates/contact_detail/tabs/_information.html`** — Added email bounce warning to the information tab email display
- **`support/templates/create_contact/tabs/_data.html`** — Added email bounce warning to the Email field label in the contact edit form
- **`support/templates/new_subscription.html`** — Added email bounce warning to the Email field label in the new subscription form
- **`support/templates/seller_console.html`** — Added email bounce warning to the email table row in the seller console

## 📚 Technical Details

- `EmailBounceActionLog` has two action types: `EMAIL_BOUNCE_ACTION_INVALID = 1` ("invalid email") and `EMAIL_BOUNCE_ACTION_MAXREACH = 2` ("max bounce reached"), defined in `core/choices.py`.
- The existing `EmailBounceActionLog.email_is_bouncer()` static method only checks for `EMAIL_BOUNCE_ACTION_MAXREACH` entries in the last 90 days. The new `get_email_bounce_action()` method intentionally returns the latest entry of **any** action type regardless of age — the presence of any log entry is considered sufficient reason to surface a warning.
- No view changes were required: `contact` is available in all affected templates, and `{% with %}` caches the single DB query per render without adding context variables.
- The method returns the full `EmailBounceActionLog` instance rather than a boolean so templates can call `get_action_display` to show which type of bounce was recorded.

## 🧪 Manual Testing

1. **Happy path — bounced email shown in red on overview tab:**
   - Create an `EmailBounceActionLog` entry for a contact's email via the Django admin (choose any action type).
   - Open that contact's detail page and navigate to the Overview tab.
   - **Verify:** The email address appears in red with a ✕ icon and the action name (e.g. "max bounce reached") displayed inline.

2. **Happy path — warning shown on information tab:**
   - Using the same contact from scenario 1, navigate to the Information tab.
   - **Verify:** Same red email display with icon and action name.

3. **Happy path — warning shown on contact edit form:**
   - Open the edit form for the same contact.
   - **Verify:** The Email field label renders in red with the ✕ icon and action name prepended.

4. **Happy path — warning shown on new subscription form:**
   - Navigate to the New Subscription page for the same contact.
   - **Verify:** The Email label shows the bounce warning in red.

5. **Happy path — warning shown in seller console:**
   - Open the seller console for a campaign that includes the same contact.
   - **Verify:** The email row is highlighted red (`table-danger`) and the action name appears as a prefix before the email address.

6. **Edge case — contact with no email address:**
   - Open a contact that has no email set.
   - Navigate to Overview, Information, Edit, and New Subscription pages.
   - **Verify:** No warning appears; no errors are raised; the email field renders its normal "-" or empty state.

7. **Edge case — contact with email but no bounce log entry:**
   - Open a contact whose email has no `EmailBounceActionLog` records.
   - **Verify:** The email address renders normally (black `mailto:` link, plain label), with no icon or warning.

8. **Edge case — new contact creation form:**
   - Navigate to the New Contact creation form (no existing contact object).
   - **Verify:** The Email label renders as plain "Email" text; no bounce check is attempted; no errors are raised.

## 📝 Deployment Notes

- No database migrations required.
- No configuration changes needed.
- No management commands to run.

## 🚀 Future Improvements

- Consider showing the bounce date alongside the action type for more context at a glance
- Add a tooltip or expandable detail showing the full bounce history for a contact's email

---

**Date:** 2026-03-24
**Author:** Tanya Tree + AI pair programmer
**Branch:** t1065
**Type:** UX Improvement
**Modules affected:** Core, Support, Subscriptions
