# Showing the Settled Commission on a Validated Sale

- **Date:** 2026-09-10
- **Author:** Tanya Tree + Claude Opus 5
- **Ticket:** t1178
- **Type:** Bug Fix (+ Enhancement on the validation screen)
- **Component:** Support — Sales Records, Validation views
- **Impact:** Commissions, User Experience, Trust in the panel

## 🎯 Summary

A sales record detail page reported a commission of `0` for sales that had already been validated,
commissioned, and were on their way to the seller's liquidation. The case that surfaced it was a
**partial sale** — a product added to an existing subscription — whose detail read:

```text
0 (Credit card) + 0 (1 products) + 0 (1) + 105 (specific products) = 0
```

while the sales record list, and the seller's monthly liquidation, both said `105`.

Nothing was miscalculated. A commission has two legitimate values at different moments: a
**forecast** before the sale is validated, and a **settled** amount afterwards. `SalesRecord`
already modelled both — `calculate_total_commission()` for the forecast, the stored
`total_commission_value` for the settled figure — and the list template already picked the right one
with an `if subscription.validated`. The detail page never got that distinction, so it kept
recomputing the forecast as if nothing had been decided.

Fixing the number exposed the next problem: a settled figure that the breakdown does not explain is
just as confusing as a wrong one. So the screen now leads with the total and, when the components do
not account for it, says **why** — and to say why honestly, one thing had to start being recorded.

## ✨ Changes

### 1. One definition of "which figure to show"

**File:** `support/models.py`

Two methods on `SalesRecord` replace the `if` that was copied into templates:

```python
def is_settled(self):
    return bool(self.subscription and self.subscription.validated)

def get_commission_value(self):
    if self.is_settled():
        return self.total_commission_value
    return self.calculate_total_commission()
```

`calculate_total_commission()` and `total_commission_value` are both left untouched: each is still
correct for its own moment. What changes is that nothing in the UI has to know which is which.

### 2. The total is shown apart from its components

**Files:** `support/models.py`, `support/templates/validate_subscription_sales_record.html`

`get_commission_breakdown()` returns the components with **no total attached**, and the template
renders the figure on its own line in bold with the breakdown as a footnote underneath. Joining them
with an `=` is what made the old screen state something false; now there is no equation to be wrong.

`calculate_commission()` (breakdown and total in one line) is kept for callers outside the panel.

### 3. The screen says why, when the breakdown does not explain the figure

**File:** `support/models.py`

`get_commission_note()` returns a sentence, or `None` when the breakdown speaks for itself. Every
branch reports something the record **knows** — a stored flag or a rule — never a guess made by
comparing numbers:

| Situation | What it says |
|---|---|
| Free subscription | A free subscription pays no commission |
| `can_be_commissioned` is false | Marked as not commissionable: it does not enter the liquidation |
| Not validated yet, not a full sale | A partial sale pays no commission unless whoever validates decides otherwise |
| `commission_overridden` | Amount entered by hand at validation time |
| Settled, computed, components disagree | Settled at validation; the components are today's and no longer add up — prices or commission rules changed since |

### 4. Overrides are now recorded

**Files:** `support/models.py`, `support/views/all_views.py`, `support/migrations/0042_salesrecord_commission_overridden.py`

`override_commission_value` is a form field, not a model field: it was used to write the total and
then discarded. The only remaining trace of an override was that the stored value no longer matched
the sum of the components — which is *also* what a price change after the fact looks like, so the
panel could not tell the two apart and had to stay silent about both.

A `commission_overridden` boolean now records it. `set_commissions()` clears it when it computes a
commission, so the flag cannot go stale if a sale is settled again.

### 5. A misspelled assignment removed

**File:** `support/views/all_views.py`

```python
sales_record.can_be_commisioned = True   # one "s" short of the real field
```

The field is `can_be_commissioned`, so this created a stray attribute and did nothing. It was also
redundant: `can_be_commissioned` is in the validation form's `fields`, so the ModelForm had already
put the checked value on `form.instance`. Replaced by a comment saying so.

### 6. Follow-up (2026-09-11): the note fired on every commissioned partial sale

**File:** `support/models.py`

The first version compared the settled amount against `calculate_total_commission()`. That method
applies the "only full sales commission" rule and answers `0` for a partial sale, so **every**
commissioned partial sale was flagged as unexplained — while its breakdown, `0 + 0 + 0 + 105` next
to a total of `105`, added up in plain sight.

`sum_commission_components()` now provides the sum with no rule on top: the arithmetic a reader can
do from what is on screen. That is what the note compares against, so it only appears when the
components genuinely fail to explain the figure — the case it was written for, where a sale was
settled at one price and the catalogue moved afterwards. `calculate_total_commission()` is now
expressed in terms of it and keeps its forecasting behaviour untouched.

## 📁 Files Modified

- **`support/models.py`** — `is_settled()`, `get_commission_value()`, `get_commission_breakdown()`, `get_commission_note()`; `commission_overridden` field; `set_commissions()` clears the flag
- **`support/views/all_views.py`** — records the override; misspelled assignment removed
- **`support/templates/validate_subscription_sales_record.html`** — total in bold, note, breakdown underneath; heading switches on `is_settled`
- **`support/templates/sales_record_filter.html`** — uses `get_commission_value`
- **`tests/test_subscription_validation.py`** — `TestCommissionShownAfterValidating`, 12 tests
- **`locale/es/LC_MESSAGES/django.po` / `.mo`** — new strings

## 📁 Files Created

- **`support/migrations/0042_salesrecord_commission_overridden.py`**
- **`docs/es/plans/2026-09-10-t1178-comision-detalle-venta-validada.md`** — the analysis behind this change

## 📚 Technical Details

**Why the payment-type component stays at 0 on a partial sale.**
`calculate_payment_type_commission()` has its own `sale_type == FULL` gate, and it is deliberate: the
payment method belongs to the subscription as a whole, not to a product added later. The screen
already says so ("Payment method is only relevant for full sales"). That zero is not part of the bug
and was not touched.

**Decimal vs. the raw sum.** `total_commission_value` is a `DecimalField`; the per-component values
come from settings as `int`/`float` (`412.5`, `105`). Comparisons go through `Decimal(str(...))` so a
settled `105.00` matches a recomputed `105` instead of being reported as a disagreement over a
representation difference.

**Known, out of scope: `commission_for_amount_of_products_sold` is not a field.**
`calculate_products_count_commission()` assigns it and `set_commissions()` adds it to the total, but
the model has no such column — only `commission_for_payment_type`, `commission_for_products_sold` and
`commission_for_subscription_frequency`. The total is right because the sum happens in memory right
after the assignment, so no money is wrong today; what is lost is the **persisted breakdown**, which
is missing that one component. Adding it needs its own migration and its own ticket.

## 🧪 Manual Testing

1. **Happy path — a partial sale decided to be commissioned:**
   - Find a Partial sales record whose product carries a specific-product commission, still unvalidated
   - **Verify:** list and detail both show `0`, and the detail explains that a partial sale does not commission unless whoever validates decides otherwise
   - Validate it with "Can be commissioned" checked
   - **Verify:** both screens now show the same figure (105 in the reference case), the heading reads "Comisión liquidada", the total is in bold, and the note explains that the components no longer add up to it

2. **Edge case — a manually overridden amount:**
   - Repeat, typing an amount in "Add Commission Value Manually" (e.g. 300)
   - **Verify:** both screens show 300, and the note says the amount was entered by hand — not the "prices changed" wording

3. **Edge case — not commissionable:**
   - Validate with "Can be commissioned" unchecked
   - **Verify:** the note says the record is marked as not commissionable, instead of an unexplained 0

4. **Edge case — a free subscription:**
   - Open a gift or staff subscription's sales record
   - **Verify:** unchanged — no payment method, no commission, fields locked

5. **Regression — an ordinary full sale:**
   - Validate one with the box checked and no override
   - **Verify:** the figure matches what this screen showed before the change, and there is **no** note: the breakdown explains itself

## 📝 Deployment Notes

- **Migration required:** `support.0042_salesrecord_commission_overridden` — adds a boolean with a
  default, no data rewrite, no backfill
- Sales validated **before** this deploy will not be marked as overridden even if they were: that
  information was never stored. They fall into the "components no longer add up" note instead, which
  is accurate — it names both possibilities rather than picking one
- **Run `python manage.py compilemessages -l es` on deploy.** The `.po` is versioned, the compiled
  `.mo` is not (`.gitignore`), so without this step the new strings show up in English
- No settings changes. `SELLER_COMMISSION_*` are read exactly as before
- Nothing is recalculated retroactively: sales validated earlier already have the correct
  `total_commission_value` stored, and that is now what they display

## 🚀 Future Improvements

- Add the missing `commission_for_amount_of_products_sold` field so the persisted breakdown is complete
- Show the stored components on a settled sale instead of recomputing them, once that field exists
- Record **who** overrode a commission and when, not only that it happened

---

- **Date:** 2026-09-10
- **Author:** Tanya Tree + Claude Opus 5
- **Branch:** t1178
- **Type:** Bug Fix (+ Enhancement)
- **Modules affected:** Support (Sales Records, Validation views)
