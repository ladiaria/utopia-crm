# Validating a Sale as the Gate for Web Activation

- **Date:** 2026-09-08
- **Author:** Tanya Tree + Claude Opus 5
- **Ticket:** branch `desync/validacion-y-activacion` (desync CRM ↔ CMS front, task 3)
- **Type:** Feature (+ Bug Fix on free subscriptions and on the contact detail)
- **Component:** Core — Subscriptions, Utils; Support — Sales Records, Validation views, Sidebar
- **Impact:** Web Access Propagation, Commissions, Data Integrity, User Experience

## 🎯 Summary

A subscription created by the call center did not exist for the website until the nightly
`activos.csv` batch ran: the person paid in the morning and kept hitting the paywall until the next
day. The CRM already knows how to tell the CMS to activate a subscriber
(`utopia_crm_ladiaria/services/activation.py`, in production since 2026-08-12, used by Witty), so
what was missing was **when** to call it from a call-center sale.

The answer this branch implements is **on validation, not on creation**. A freshly created sale may
still be a duplicate — the same person with two web accounts, which is exactly what the deduplication
queue resolves by hand — and handing out access before a human has looked at it gives it to the wrong
web account half of the time. Validation is the moment a human already looked.

Hanging web access off validation only works if the validation queue means something, and it did not:
**every** subscription was born unvalidated, including the ones coming from the web, which have no
seller, no commission and nothing a manager could possibly validate. The queue was a pile nobody
read. So the branch also settles who carries a sales record and who is born validated, fixes what
free subscriptions report, and makes the validation state reachable from the contact detail for every
subscription type.

## ✨ Changes

### 1. A hook for what "validated" should trigger

**Files:** `core/utils.py`, `support/views/all_views.py`

The base CRM has no opinion on what validating a sale should propagate; installations do. The hook is
a dotted path taking `(subscription, user)`:

```python
hook_path = getattr(settings, "SUBSCRIPTION_VALIDATED_HOOK", None)
if not hook_path:
    return None
try:
    from django.utils.module_loading import import_string

    return import_string(hook_path)(subscription, user)
except Exception:
    logger.exception("SUBSCRIPTION_VALIDATED_HOOK failed for subscription %s", ...)
    return None
```

It is called from `ValidateSubscriptionSalesRecord.form_valid()`, right after
`subscription.validate(user=...)`. Two properties matter: **fail closed** — with no setting nothing
happens at all — and **never raises**: the validation is already saved and is the source of truth, so
a failure to propagate is logged and swallowed.

### 2. Who is born validated, and who carries a sales record

**Files:** `utopia-crm-ladiaria` (`utils.py`, `views/api.py`), documented here because it defines the
queue this branch depends on

Sales made on the web have no seller behind them, so there is nothing to validate: MercadoPago,
Witty and the API promo are created with `validated=True` and no sales record. The two-month free
digital subscription does carry one — with price 0 and the seller who gave it away — because somebody
inside the CRM creates it.

### 3. A validated subscription can still be commissioned

**File:** `support/views/all_views.py`

Being born validated should not close the door on commissioning: the real case is a seller who refers
someone who then buys on their own. `SalesRecordCreateView` no longer re-validates an already
validated subscription — doing so overwrote `validated_by`, and `NULL` there is precisely the mark
that the system validated it. The button reads differently depending on the case: *Register Sale*
when the sale is pending, *Commission a seller* when the subscription is validated and has no record.

### 4. Free subscriptions report no payment method and pay no commission

**Files:** `core/models.py`, `support/models.py`, `support/forms.py`,
`support/templates/sales_record_filter.html`

Gift and staff subscriptions are recorded as FULL sales, so the panel used to show them the
subscription's payment method and compute a commission over a sale that moved no money. The criterion
lives in one place, `Subscription.is_free()` — types `"F"` (gift) and `"S"` (staff), the same pair
`core.forms` already treats as free — and `SalesRecord.is_free_subscription()` delegates to it.
`get_payment_type`, `calculate_total_commission`, `calculate_commission` and `set_commissions` all
read it; the last one writes 0 explicitly, so the stored value cannot drift from what the panel shows
even when a manager forces the calculation while validating.

On the validation screen the commission fields are **locked, not just hidden**:

```python
if self.instance and self.instance.pk and self.instance.is_free_subscription():
    self.initial["can_be_commissioned"] = False
    self.fields["can_be_commissioned"].disabled = True
    self.fields["override_commission_value"].disabled = True
```

`disabled` makes Django ignore whatever arrives in the POST and keep the initial value, so a
hand-made request cannot obtain a commission either. The initial has to be overridden on
`self.initial`, which is where a `ModelForm` keeps the instance's own value.

### 5. The validation state is visible for every subscription type

**Files:** `support/templates/includes/_subscription_validation_actions.html` (new),
`support/templates/includes/_overview_subscription_list_item.html`

The validation block lived inside the `else` branch of an `if` on `subscription.type`, so only normal
subscriptions showed it. That became wrong when free subscriptions started carrying sales records:
they enter the queue and the badge, but there was no way to validate them from the contact detail (in
the local database, 724 gifts and 3,650 promos with a sales record, all invisible from there). The
block moved to its own include, used from the three branches instead of being repeated, and it now
decides on `Subscription.is_free()` whether commissioning applies — staff subscriptions used to fall
into the "normal" branch and were offered a commission they cannot pay.

The fourth case — validated **and** with a record — showed nothing at all, so "everything is in
order" looked exactly like "nothing was loaded". It now shows a *Validated* badge with who and when
in the tooltip, or "by the system" when `validated_by` is `NULL`.

### 6. Sales Records moved to the main sidebar, with a pending count

**Files:** `templates/components/_sidebar.html`,
`templates/components/sidebar_items/_campaign_management.html`, `core/templatetags/core_tags.py`

The queue stops being a campaign-management item and becomes a top-level entry for Managers, with a
badge. Validation lives on the subscription, not on the record, so the tag counts records whose
subscription is still unvalidated, and it is defensive in the same shape as `pending_email_takeovers`:
a badge is never a reason for a page not to render.

## 📁 Files Modified

- **`core/utils.py`** — `run_subscription_validated_hook()`
- **`core/models.py`** — `Subscription.is_free()`
- **`core/templatetags/core_tags.py`** — `pending_sales_records()`
- **`support/models.py`** — `SalesRecord.is_free_subscription()` delegates to `Subscription.is_free()`;
  payment type and commissions honour it
- **`support/forms.py`** — commission fields locked for free subscriptions
- **`support/views/all_views.py`** — hook call on validation; no re-validation when commissioning
- **`support/views/subscriptions.py`** — validation state in the subscription context
- **`support/templates/…`** — validation actions include, sales record filter tooltip, validation
  screen
- **`templates/components/…`** — sidebar entry and badge
- **`tests/test_subscription_validation.py`** — new suite

## 📚 Technical Details

**Why the hook and not a signal.** A `post_save` on `Subscription` would fire on every save, and
validation is one specific transition made by one specific view. The hook is called exactly where the
transition happens, receives the user who made it, and is configured per installation — the base app
ships no behaviour at all.

**Subscriptions with a future start date.** The la diaria implementation does not propagate them: the
`plan_id` the CMS receives is built by the same serializer the nightly CSV uses, which filters
`start_date__lte=today`, so a future subscription would push an empty `plan_id` — worse than not
telling. The batch of the night it starts picks it up, which is what already happens today.

**The old queue.** Before this branch, production had ~126,650 unvalidated subscriptions, of which
only ~8,700 carried a sales record. The ladiaria package adds
`validate_historic_subscriptions` to cut that queue by date; see its devnote.

## 🧪 Manual Testing

1. **Validating a call-center sale (happy path):**
   - With `SUBSCRIPTION_VALIDATED_HOOK` configured, open *Sales Records*, pick a pending sale and
     validate it.
   - **Verify:** the success message appears, the subscription shows as validated with your user, and
     the configured hook ran (in la diaria, the person can read on the website immediately).

2. **The hook is not configured (edge case):**
   - Remove `SUBSCRIPTION_VALIDATED_HOOK` from settings and validate a sale.
   - **Verify:** validation is saved normally and nothing is propagated — no error, no traceback.

3. **A gift subscription (edge case):**
   - Create a gift subscription (`type="F"`) from the contact detail, then open its validation screen.
   - **Verify:** the commission fields are disabled; the panel shows N/A as payment method and 0 as
     commission. Posting the form by hand with `can_be_commissioned=on` still results in no
     commission.

4. **Commissioning a web sale (edge case):**
   - Take a subscription created from the web (born validated, no sales record) and use
     *Commission a seller* from the contact detail.
   - **Verify:** the sales record is created with the seller and the commission, and `validated_by`
     stays `NULL` — the *Validated* badge keeps reading "by the system".

## 📝 Deployment Notes

- No database migrations required.
- Deploy together with the `utopia-crm-ladiaria` branch of the same name.
- **Post-deployment order matters.** First cut the old queue with
  `validate_historic_subscriptions` (ladiaria; dry run, then `--fix`), and only then configure the
  hook in production:

  ```python
  SUBSCRIPTION_VALIDATED_HOOK = "utopia_crm_ladiaria.services.activation.activate_on_validation"
  ```

  Not for technical risk, but because the day it is switched on every validation starts granting real
  web access — better over a small, real queue than over the ~8,700 of backlog.
- The rest of the activation settings (`WEB_ACTIVATE_SUBSCRIBER_URI` / `_ENABLED`, and the POST
  whitelist) are already in place in production, and the CMS endpoint has been live since 2026-08-17.

## 🚀 Future Improvements

- The CMS → CRM direction of the instant sync is still pending (task 3 of the front).
- Activation on approving a deduplication request: the code exists, the call from the queue's
  *Approve* branch does not. The order is not negotiable — takeover, then apply the email, then
  activate — or the CMS answers `409 contact_id_conflict`.
- Nothing tells the manager, on the validation screen, whether the web activation actually worked.
  A note on the sales record, or a status on the subscription, would save a trip to the logs.

---

- **Date:** 2026-09-08
- **Author:** Tanya Tree + Claude Opus 5
- **Branch:** desync/validacion-y-activacion
- **Type:** Feature (+ Bug Fix)
- **Modules affected:** Core (Subscriptions, Utils, Template tags), Support (Sales Records,
  Validation, Sidebar)
