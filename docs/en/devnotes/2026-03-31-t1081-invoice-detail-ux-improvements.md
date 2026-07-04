# Invoice Detail View UX Improvements

- **Date:** 2026-03-31
- **Author:** Tanya Tree + Claude Sonnet 4.6
- **Ticket:** t1081
- **Type:** UX Improvement
- **Component:** Invoicing
- **Impact:** User Experience, Operator Workflow

## 🎯 Summary

Several small but meaningful improvements were made to the invoice detail view (`invoice_detail.html`). The "Edit" button now opens the Django admin in a new browser tab so operators do not lose their place in the CRM while making admin edits. The "Cancel invoice" button is now hidden when the invoice is already canceled, preventing a confusing and redundant action. When a canceled invoice has an associated credit note, the detail view now shows the credit note's serie and number alongside a link to its admin record. Finally, a Notes card was added to surface the invoice's `notes` field, which was previously populated in the database but never shown in this view.

## ✨ Changes

### 1. Edit button opens in a new tab

**File:** `invoicing/templates/invoice/invoice_detail.html`

`target="_blank"` was added to the admin edit link so that clicking "Edit" opens the Django admin change form in a new browser tab. This allows operators to review and modify the invoice in admin without navigating away from the CRM detail view.

### 2. Cancel button hidden for already-canceled invoices

**File:** `invoicing/templates/invoice/invoice_detail.html`

The visibility condition for the "Cancel invoice" button was tightened from `{% if perms.invoicing.can_cancel_invoice %}` to `{% if perms.invoicing.can_cancel_invoice and not object.canceled %}`. The button now only appears when the invoice is still active, eliminating a confusing affordance on invoices that have already been canceled.

### 3. Credit note information shown when invoice is canceled

**File:** `invoicing/templates/invoice/invoice_detail.html`

When an invoice is canceled and has an associated `CreditNote` (accessed via `object.get_creditnote`), the status section now shows:

- The credit note's **serie and number** (e.g. `A-1042`) when those fields have been populated — that is, after the credit note has been sent to the electronic invoicing provider.
- A **link to the credit note's admin change form** (opens in a new tab), shown only to users with the `invoicing.change_creditnote` permission.

```html
{% with cnote=object.get_creditnote %}
  {% if cnote %}
    {% if cnote.serie and cnote.numero %}
      <strong>{{ cnote.serie }}-{{ cnote.numero }}</strong>
    {% endif %}
    {% if perms.invoicing.change_creditnote %}
      <a href="{% url "admin:invoicing_creditnote_change" cnote.id %}" target="_blank" ...>
        Go to credit note in admin
      </a>
    {% endif %}
  {% endif %}
{% endwith %}
```

If the credit note exists but has not yet been sent to the provider (no `serie`/`numero`), only the admin link is shown without the identifier.

### 4. Notes card

**File:** `invoicing/templates/invoice/invoice_detail.html`

A new card was inserted between the Status card and the Billing Data card. It renders the contents of `Invoice.notes` (a `TextField`) using `|linebreaksbr`, and is only rendered when the field has content. The `notes` field has existed in the model for some time but was not previously visible in this view.

## 📁 Files Modified

- **`invoicing/templates/invoice/invoice_detail.html`** — Edit button opens in new tab; cancel button hidden when already canceled; credit note info and link shown when canceled; notes card added

## 🧪 Manual Testing

1. **Happy path — edit button opens new tab:**
   - Open any invoice detail view as a user with `invoicing.change_invoice`.
   - Click "Edit".
   - **Verify:** The Django admin change form opens in a new browser tab; the CRM detail view remains open in the original tab.

2. **Happy path — credit note shown after cancellation:**
   - Open a canceled invoice that has a credit note with `serie` and `numero` populated.
   - **Verify:** The Status section shows the credit note identifier (e.g. `A-1042`) and a button linking to the credit note in admin.

3. **Happy path — notes card displayed:**
   - Open an invoice whose `notes` field has content (set one via admin if needed).
   - **Verify:** A "Notes" card appears between the Status and Billing Data sections, with the text rendered respecting line breaks.

4. **Edge case — cancel button absent on canceled invoice:**
   - Open a canceled invoice as a user with `invoicing.can_cancel_invoice`.
   - **Verify:** The "Cancel invoice" button is not rendered. The "Canceled" badge and cancelation date are visible instead.

5. **Edge case — credit note without serie/numero:**
   - Open a canceled invoice whose `CreditNote` record exists but has `serie` and `numero` both null (credit note not yet sent to the provider).
   - **Verify:** The credit note identifier is not shown, but the "Go to credit note in admin" link still appears (for users with the appropriate permission).

6. **Edge case — notes card absent when notes is empty:**
   - Open an invoice whose `notes` field is null or blank.
   - **Verify:** No Notes card appears; the layout goes directly from the Status card to the Billing Data card.

## 📝 Deployment Notes

- No database migrations required.
- No configuration changes needed.
- No new permissions were introduced; the credit note admin link respects the existing `invoicing.change_creditnote` permission.

---

- **Date:** 2026-03-31
- **Author:** Tanya Tree + Claude Sonnet 4.6
- **Branch:** t1081
- **Type:** UX Improvement
- **Modules affected:** Invoicing
