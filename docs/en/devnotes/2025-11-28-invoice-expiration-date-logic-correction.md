# 2025-11-28: Invoice Expiration Date Logic Correction

## Summary

Corrected the invoice expiration date query logic throughout the system, changing from "less than or equal" (`__lte`) to "less than" (`__lt`) when comparing with today's date. This ensures that invoices expiring TODAY are not considered overdue until the next day.

## Problem Description

### Previous Behavior (Incorrect)

The system used `expiration_date__lte=date.today()` in multiple places, which meant:

- An invoice with `expiration_date = 2025-11-28` was considered overdue on November 28th itself
- Customers received overdue notifications on the expiration date
- Invoicing issues were created on the expiration date, not the day after
- Overdue reports included invoices that were technically not yet overdue

**Example of the problem:**

```python
# Previous logic (INCORRECT)
expired_invoices = Invoice.objects.filter(
    expiration_date__lte=date.today(),  # Includes invoices expiring TODAY
    paid=False,
    debited=False,
    canceled=False,
    uncollectible=False,
)
```

If today is 11/28/2025 and an invoice expires on 11/28/2025:

- ❌ Invoice is considered overdue on 11/28
- ❌ Customer receives overdue notification on 11/28
- ❌ Invoicing issue is created on 11/28

### Expected Behavior (Correct)

An invoice expiring on 11/28/2025 should:

- ✅ Be considered valid throughout the entire day of 11/28
- ✅ Be considered overdue starting 11/29
- ✅ Generate notifications/issues only starting 11/29

## Solution Implemented

Changed **all** overdue invoice queries from `__lte` to `__lt` in the following files:

### 1. Contact Model Methods

**File:** `core/models.py`

```python
# Line 661: Contact debt calculation
sum_import = self.invoice_set.filter(
    expiration_date__lt=date.today(),  # Changed from __lte to __lt
    paid=False,
    debited=False,
    canceled=False,
    uncollectible=False,
)

# Line 2363: Subscription overdue check
invoices.filter(
    expiration_date__lt=date.today(),  # Changed from __lte to __lt
    paid=False,
    debited=False,
    canceled=False,
    uncollectible=False
)

# Line 2938: Campaign debtor contacts filter
subscriptions.filter(
    contact__invoice__expiration_date__lt=date.today(),  # Changed from __lte to __lt
    contact__invoice__paid=False,
    contact__invoice__debited=False,
    contact__invoice__canceled=False,
    contact__invoice__uncollectible=False,
)
```

### 2. Invoice Management Command

**File:** `support/management/commands/generate_invoicing_issues.py`

```python
# Line 33: Query for expired invoices to create issues
Contact.objects.filter(
    invoice__paid=False,
    invoice__debited=False,
    invoice__canceled=False,
    invoice__uncollectible=False,
    invoice__expiration_date__lt=today(),  # Changed from __lte to __lt
)
```

**Impact:** Invoicing issues are now created the day after expiration, not on the expiration date itself.

### 3. Invoice Filters

**File:** `invoicing/filters.py`

```python
# Line 93: Overdue invoice filter
return queryset.filter(
    paid=False,
    debited=False,
    canceled=False,
    uncollectible=False,
    expiration_date__lt=date.today()  # Changed from __lte to __lt
)
```

### 4. Invoice Views

**File:** `invoicing/views.py`

```python
# Line 329: Invoice filter view - overdue invoices
overdue = invoice_filter.qs.filter(
    canceled=False,
    uncollectible=False,
    paid=False,
    debited=False,
    expiration_date__lt=date.today()  # Changed from __lte to __lt
)
```

### 5. Support Views

**File:** `support/views/all_views.py`

```python
# Line 963: Campaign debtor contacts filter
subscriptions.filter(
    contact__invoice__expiration_date__lt=date.today(),  # Changed from __lte to __lt
    contact__invoice__paid=False,
    contact__invoice__debited=False,
    contact__invoice__canceled=False,
    contact__invoice__uncollectible=False,
)

# Line 1060: Another campaign debtor filter
subscriptions.filter(
    contact__invoice__expiration_date__lt=date.today(),  # Changed from __lte to __lt
    # ... same filters as above
)

# Line 1246: Never paid issues view
contact__invoice__expiration_date__lt=date.today(),  # Changed from __lte to __lt

# Line 1328: Debtor contacts view
invoice__expiration_date__lt=date.today(),  # Changed from __lte to __lt
```

## Impact

### Benefits

✅ **Improved Customer Experience:**

- Customers have the entire expiration day to pay without being considered overdue
- No overdue notifications on the expiration date itself

✅ **Correct Business Logic:**

- An invoice expiring on 11/28 is valid until 11:59 PM on 11/28
- Only considered overdue starting 11/29

✅ **Accurate Reports:**

- Overdue reports correctly reflect invoice status
- Don't include invoices still within payment period

✅ **System Consistency:**

- All overdue invoice queries use the same logic
- Uniform behavior across filters, commands, and views

### Considerations

⚠️ **Behavior Change:**

- Invoicing issues will be created one day later than before
- Overdue reports will show fewer invoices on the expiration date
- Customers effectively get one additional day before being considered overdue

📅 **Practical Example:**

| Expiration Date | Previous Logic (`__lte`) | New Logic (`__lt`) |
|-----------------|--------------------------|---------------------|
| 11/28/2025 | Overdue on 11/28 ❌ | Overdue on 11/29 ✅ |
| 11/29/2025 | Overdue on 11/29 | Overdue on 11/30 |
| 11/30/2025 | Overdue on 11/30 | Overdue on 12/01 |

## Modified Files

### utopia-crm

1. **`core/models.py`**
   - Line 661: Contact debt calculation method
   - Line 2363: Subscription overdue check
   - Line 2938: Campaign debtor contacts filter

2. **`support/management/commands/generate_invoicing_issues.py`**
   - Line 33: Expired invoices query for issue creation

3. **`invoicing/filters.py`**
   - Line 93: Overdue invoice filter

4. **`invoicing/views.py`**
   - Line 329: Invoice filter view (overdue invoices)

5. **`support/views/all_views.py`**
   - Line 963: Campaign debtor contacts filter
   - Line 1060: Another campaign debtor filter
   - Line 1246: Never paid issues view
   - Line 1328: Debtor contacts view

## Testing Scenarios

### Scenario 1: Invoice expiring today

1. Create an invoice with `expiration_date = date.today()`
2. Run the `generate_invoicing_issues` command
3. **Verify:** No issue is created today
4. Wait until tomorrow and run the command again
5. **Verify:** Issue is created the next day

### Scenario 2: Overdue report

1. Have invoices with `expiration_date = date.today()`
2. Access the overdue contacts report
3. **Verify:** Invoices expiring today do NOT appear in the report
4. The next day, verify they now appear

### Scenario 3: Contact debt filter

1. Apply "With debt" filter in contact list
2. **Verify:** Contacts with invoices expiring today are not shown
3. **Verify:** Only contacts with invoices expired yesterday or earlier are shown

## Technical Context

**Difference between `__lte` and `__lt`:**

```python
# __lte (less than or equal)
expiration_date__lte=date(2025, 11, 28)
# Includes: 2025-11-28, 2025-11-27, 2025-11-26, etc.

# __lt (less than)
expiration_date__lt=date(2025, 11, 28)
# Includes: 2025-11-27, 2025-11-26, 2025-11-25, etc.
# Excludes: 2025-11-28
```

**Expiration Date Interpretation:**

- `expiration_date = 2025-11-28` means "valid until the end of day 11/28/2025"
- Therefore, should only be considered overdue starting 11/29/2025
- Using `__lt` with `date.today()` correctly implements this logic

## Lessons Learned

1. **Date Semantics:** Expiration date should be interpreted as "valid until the end of that day"
2. **System Consistency:** Business logic changes must be applied in all relevant places
3. **Customer Impact:** Small changes in date logic can have significant impact on user experience

## Deployment Checklist

- [ ] Review that no overdue invoice queries still use `__lte`
- [ ] Communicate the change to support team (issues will be created one day later)
- [ ] Monitor overdue reports after deployment
- [ ] Verify `generate_invoicing_issues` command works correctly

---

**Date:** 2025-11-28
**Type:** Business logic correction
**Priority:** Medium
**Related to:** Invoicing, issues, overdue reports, customer notifications
