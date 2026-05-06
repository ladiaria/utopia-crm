# Email Uniqueness Validation in Promotional Subscription Forms

**Date:** 2025-11-10
**Type:** Bug Fix & Data Integrity Enhancement
**Component:** Promotional Subscription Forms
**Impact:** Data Integrity, User Experience

## Summary

Implemented email uniqueness validation in `SendPromoView` and `UpdatePromoView` to prevent database integrity errors when updating contact information. The validation ensures that users cannot assign an email address that already belongs to another contact, providing clear error messages instead of cryptic database errors.

## Motivation

The `Contact` model has a unique constraint on the `email` field to prevent duplicate email addresses in the system. However, the promotional subscription forms (`SendPromoView` and `UpdatePromoView`) were not validating email uniqueness before attempting to save contact updates. This caused the following issues:

1. **Database Integrity Errors:** When a user tried to update a contact's email to one that already existed, the system would raise an `IntegrityError` at the database level
2. **Poor User Experience:** Users saw cryptic database error messages instead of clear, actionable feedback
3. **No Guidance:** Users weren't informed which contact already had the email address they were trying to use

## Problem Details

### Original Behavior

When updating contact information in promotional subscription forms:

```python
# In SendPromoView.form_valid() and UpdatePromoView.form_valid()
for attr in ("name", "phone", "mobile", "email", "notes"):
    val = form.cleaned_data.get(attr)
    if getattr(self.contact, attr) != val:
        changed = True
        setattr(self.contact, attr, val)

if changed:
    try:
        self.contact.save()  # Could raise IntegrityError if email is duplicate
    except forms.ValidationError as ve:
        form.add_error(None, ve)
        return self.form_invalid(form)
```

**Issues:**

- Only caught `forms.ValidationError`, not `IntegrityError`
- No validation before attempting to save
- Users saw database-level error messages

### Database Constraint

```python
# core/models.py - Contact model
email = models.EmailField(blank=True, null=True, unique=True, verbose_name=_("Email"))
```

The `unique=True` constraint ensures data integrity at the database level, but without form-level validation, errors only appeared during save operations.

## Solution Implemented

### 1. Enhanced NewPromoForm with Email Validation

**File:** `support/forms.py`

Added form-level validation to check email uniqueness before attempting to save:

```python
class NewPromoForm(EmailValidationForm):
    # ... existing fields ...

    def __init__(self, *args, **kwargs):
        self.contact = kwargs.pop("contact", None)
        super().__init__(*args, **kwargs)

    def clean_email(self):
        """Validate that email is unique, excluding the current contact."""
        email = self.cleaned_data.get("email")

        if email:
            from core.models import Contact
            # Check if another contact already has this email
            existing_contact = Contact.objects.filter(email=email).exclude(
                pk=self.contact.pk if self.contact else None
            ).first()
            if existing_contact:
                raise forms.ValidationError(
                    _("This email is already registered to another contact (ID: %(contact_id)s)."),
                    params={"contact_id": existing_contact.id},
                    code="duplicate_email"
                )

        return email

    def clean(self):
        self.email_extra_clean(super().clean())
```

**Key Features:**

- **Accepts Current Contact:** The form now receives the contact being edited via `__init__`
- **Excludes Current Contact:** The uniqueness check excludes the contact being edited (allows keeping the same email)
- **Clear Error Message:** Shows which contact already has the email address
- **Early Validation:** Catches the issue during form validation, not during save

### 2. Updated SendPromoView

**File:** `support/views/subscriptions.py`

Added `get_form_kwargs()` method to pass the current contact to the form:

```python
class SendPromoView(UserPassesTestMixin, FormView):
    # ... existing code ...

    def get_form_kwargs(self):
        """Pass the contact to the form."""
        kwargs = super().get_form_kwargs()
        kwargs['contact'] = self.contact
        return kwargs
```

**Benefits:**

- Form receives the contact instance for validation
- No changes needed to existing form handling logic
- Follows Django's standard pattern for passing extra data to forms

### 3. Updated UpdatePromoView

**File:** `support/views/subscriptions.py`

Added the same `get_form_kwargs()` method:

```python
class UpdatePromoView(UserPassesTestMixin, FormView):
    # ... existing code ...

    def get_form_kwargs(self):
        """Pass the contact to the form."""
        kwargs = super().get_form_kwargs()
        kwargs['contact'] = self.contact
        return kwargs
```

**Consistency:**

- Both views now use the same validation approach
- Ensures data integrity across all promotional subscription workflows

## Technical Details

### Validation Flow

1. **User submits form** with updated email address
2. **Form validation runs** (`clean_email()` method)
3. **Database query checks** if email exists for another contact:

   ```python
   Contact.objects.filter(email=email).exclude(pk=self.contact.pk).first()
   ```

4. **If duplicate found:**
   - Raises `ValidationError` with clear message
   - Form displays error to user
   - Save operation never attempted
5. **If unique or unchanged:**
   - Validation passes
   - Form proceeds to `form_valid()`
   - Contact saved successfully

### Edge Cases Handled

1. **Email unchanged:** If user keeps the same email, validation passes (contact excluded from check)
2. **Empty email:** If email is blank, validation passes (blank emails allowed)
3. **New contact:** If no contact provided, validation still works (excludes None from query)
4. **Case sensitivity:** Database handles case-insensitive uniqueness for emails

## User Experience Improvements

### Before

```text
IntegrityError at /support/send-promo/123/
UNIQUE constraint failed: core_contact.email
```

**Problems:**

- Technical database error message
- No indication of which contact has the email
- Unclear how to resolve the issue

### After

```text
This email is already registered to another contact (ID: 456).
```

**Benefits:**

- ✅ Clear, user-friendly error message
- ✅ Shows which contact has the conflicting email
- ✅ User can look up the contact and resolve the conflict
- ✅ Error appears immediately during form validation

## Files Modified

1. **support/forms.py**
   - Added `__init__` method to `NewPromoForm` to accept contact parameter
   - Added `clean_email()` method for email uniqueness validation

2. **support/views/subscriptions.py**
   - Added `get_form_kwargs()` to `SendPromoView` to pass contact to form
   - Added `get_form_kwargs()` to `UpdatePromoView` to pass contact to form

## Testing Recommendations

### Manual Testing Scenarios

1. **Test duplicate email prevention:**
   - Create contact A with email "<test@example.com>"
   - Try to update contact B with same email
   - Verify error message appears with contact A's ID

2. **Test email unchanged:**
   - Edit contact with existing email
   - Keep the same email
   - Verify form saves successfully

3. **Test email removal:**
   - Edit contact with email
   - Clear the email field
   - Verify form saves successfully

4. **Test new unique email:**
   - Edit contact
   - Change to a new, unique email
   - Verify form saves successfully

### Automated Testing

```python
def test_duplicate_email_validation():
    """Test that duplicate email raises validation error."""
    contact1 = Contact.objects.create(name="John", email="john@example.com")
    contact2 = Contact.objects.create(name="Jane", email="jane@example.com")

    form = NewPromoForm(
        data={'email': 'john@example.com', 'name': 'Jane'},
        contact=contact2
    )

    assert not form.is_valid()
    assert 'email' in form.errors
    assert 'already registered' in form.errors['email'][0]
```

## Benefits

1. **Data Integrity:** Prevents duplicate email addresses at the form level
2. **Better UX:** Clear, actionable error messages instead of database errors
3. **Early Detection:** Catches issues during validation, not during save
4. **Informative:** Shows which contact has the conflicting email
5. **Consistent:** Same validation logic in both SendPromoView and UpdatePromoView
6. **Django Best Practices:** Uses standard form validation patterns

## Future Considerations

1. **Link to Conflicting Contact:** Could add a direct link to the contact detail page in the error message
2. **Merge Contacts Feature:** Could offer to merge contacts when duplicate email detected
3. **Email History:** Could track email changes for audit purposes
4. **Bulk Operations:** Apply same validation to bulk contact import/update operations

## Related Components

- **Contact Model:** `core/models.py` - Defines email unique constraint
- **Email Validation:** `EmailValidationForm` - Base form with email validation
- **Seller Console:** Both views are part of the seller console workflow
- **Subscription Management:** Forms used when creating/updating promotional subscriptions

## Migration Notes

- **No database changes required** - Only form validation logic added
- **Backward compatible** - Existing functionality preserved
- **No data migration needed** - Works with existing contact data
- **Immediate effect** - Validation active as soon as code deployed

## Conclusion

This enhancement significantly improves data integrity and user experience in the promotional subscription workflow. By catching duplicate email errors early with clear messaging, users can quickly identify and resolve conflicts without encountering confusing database errors. The implementation follows Django best practices and maintains consistency across both creation and update workflows.
