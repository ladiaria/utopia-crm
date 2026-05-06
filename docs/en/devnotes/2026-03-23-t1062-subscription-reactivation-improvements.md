# Subscription Reactivation: Payment Method Editing and Billing Date Correction

**Date:** 2026-03-23
**Author:** Tanya Tree + AI pair programmer
**Ticket:** t1062
**Type:** Enhancement, Bug Fix
**Component:** Support, Subscriptions
**Impact:** Data Integrity, User Experience

## 🎯 Summary

Two problems were addressed in the subscription reactivation flow. First, the confirmation page had no way to view or update the subscription's payment method, forcing staff to do a separate edit after reactivation. Second, the next billing date adjustment logic was incorrect: instead of shifting the billing date forward by the full inactive period, it was unconditionally setting it to `today + 1 day`, which could leave the customer getting billed too soon (or too late). The reactivation page now includes an editable payment method selector and the billing date is correctly shifted forward by exactly the number of days the subscription was inactive.

## ✨ Changes

### 1. Corrected Next Billing Date Shift

**File:** `support/views/subscriptions.py` — `reactivate_subscription()`

The previous logic replaced `next_billing` with `today + 1` whenever it was in the past. This ignored how long the subscription had actually been inactive. The correct rule is: shift `next_billing` forward by `(today − end_date)` days, regardless of whether `next_billing` is already in the past or future — the customer should not be charged for the period the subscription was paused.

```python
# Capture end_date before it is cleared
inactive_end_date = subscription.end_date
# ...clear unsubscription fields...
if subscription.next_billing and inactive_end_date and inactive_end_date < date.today():
    inactive_days = (date.today() - inactive_end_date).days
    subscription.next_billing += timedelta(days=inactive_days)
```

`inactive_end_date` is captured before the unsubscription fields are cleared, since `subscription.end_date` is set to `None` as part of the reactivation.

The GET handler also computes a projected `new_next_billing` and passes it to the template so staff can preview the adjustment before confirming.

### 2. Editable Payment Method on the Reactivation Form

**Files:** `support/views/subscriptions.py`, `support/templates/reactivate_subscription.html`

The `payment_type` field (a `CharField` with choices from `settings.SUBSCRIPTION_PAYMENT_METHODS`) is the payment method field in active use on `Subscription`. The reactivation template now includes a `<select>` for this field with the current subscription value pre-selected. On POST, the submitted value is applied to the subscription before saving:

```python
subscription.payment_type = request.POST.get("payment_type") or None
```

A blank selection clears the field. The choices are passed from the view via `payment_method_choices`:

```python
"payment_method_choices": settings.SUBSCRIPTION_PAYMENT_METHODS,
```

### 3. Subscription Details Table Additions

**File:** `support/templates/reactivate_subscription.html`

The read-only subscription details table now shows three additional rows:

- **Next billing** — current value, with an arrow and the projected post-reactivation value when an adjustment will be applied (e.g. `2026-03-10 → 2026-04-14 (adjusted for inactive period)`)
- **Payment method** — current `payment_type` display value

## 📁 Files Modified

- **`support/views/subscriptions.py`** — Fixed `next_billing` shift logic; added payment type handling on POST; added `payment_method_choices` and `new_next_billing` to GET context
- **`support/templates/reactivate_subscription.html`** — Added next billing and payment method rows to details table; added editable `payment_type` select to the form

## 🎓 Design Decisions

- **`payment_type` only, not `payment_method_fk`/`payment_type_fk`:** The `Subscription` model has newer FK-based payment fields (`payment_method_fk`, `payment_type_fk`) but they are not wired up anywhere in the application. The legacy `payment_type` char field is what billing, filters, and existing forms use. Only this field is exposed in the reactivation form.
- **Shift applies unconditionally to past `end_date`:** The shift is applied whenever `end_date < today`, regardless of whether `next_billing` is already in the past or still in the future. A subscription that was billed through April 1 but inactive from March 1 to March 23 (22 days) should have its next billing moved to April 23 — the customer did not receive service during that period.
- **Blank payment type clears the field:** HTML select with a blank first option and `or None` in Python means a blank submission explicitly clears the field, matching typical Django admin behavior for nullable char fields.

## 🧪 Manual Testing

1. **Happy path — billing date shift:**
   - Find a subscription with `end_date` in the past (e.g. March 1) and a `next_billing` date that is either in the past or near future.
   - Navigate to its reactivation page.
   - **Verify:** The "Next billing" row in the details table shows the original date, an arrow, and the projected shifted date with the "(adjusted for inactive period)" note.
   - Confirm reactivation.
   - Open the subscription and check `next_billing`.
   - **Verify:** `next_billing` equals the original value plus the number of days between `end_date` and today.

2. **Happy path — payment method update:**
   - Navigate to the reactivation page for a subscription.
   - Change the payment method select to a different value.
   - Confirm reactivation.
   - Open the subscription record.
   - **Verify:** `payment_type` reflects the value selected on the reactivation form.

3. **Edge case — clear payment method:**
   - Navigate to the reactivation page for a subscription that has a `payment_type` set.
   - Change the select to the blank `"---------"` option.
   - Confirm reactivation.
   - **Verify:** `payment_type` is now null/blank on the subscription.

4. **Edge case — no billing date adjustment when end_date is today or in the future:**
   - Find (or create) a subscription whose `end_date` is today or in the future.
   - Navigate to its reactivation page.
   - **Verify:** The "Next billing" row shows only the current value — no arrow or adjustment note is shown.
   - Confirm reactivation.
   - **Verify:** `next_billing` is unchanged.

## 📝 Deployment Notes

- No database migrations required.
- No configuration changes needed.
- No management commands to run.

---

**Date:** 2026-03-23
**Author:** Tanya Tree + AI pair programmer
**Branch:** t1062
**Type:** Enhancement, Bug Fix
**Modules affected:** Support, Subscriptions
