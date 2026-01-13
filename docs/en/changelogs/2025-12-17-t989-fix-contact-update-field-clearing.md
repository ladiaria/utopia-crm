# Fix Contact Update Form Field Clearing Issue

**Date:** 2025-12-17
**Ticket:** t989
**Type:** Bug Fix
**Component:** Forms, Views
**Impact:** Contact Management, Data Integrity

## Summary

Fixed a critical bug in `ContactUpdateView` where fields not rendered in the contact update template (such as `cms_date_joined`, `ranking`, `protected`, `protection_reason`, and others) were being accidentally cleared when users updated contact information. Created a dedicated `ContactUpdateForm` that only includes the fields actually visible and editable in the update interface.

## Problem

### Root Cause

The `ContactUpdateView` was using `ContactAdminForm` which includes **all** Contact model fields (`fields = "__all__"`). However, the contact update template (`create_contact/create_contact.html`) only renders a subset of these fields (15 out of 30+ fields).

### What Was Happening

When a Django ModelForm is submitted:

1. Django expects all fields defined in the form to be present in the POST data
2. If a field is not rendered in the template, it won't be in the POST data
3. Django interprets missing fields as "user wants to clear this field"
4. For nullable fields, this results in setting them to `NULL`

### Fields Being Accidentally Cleared

Any field not in the template was at risk of being cleared, including:

- `cms_date_joined` - CMS join date (reported issue)
- `ranking` - Contact ranking
- `protected` / `protection_reason` - Contact protection status
- `ocupation` - Contact occupation
- `person_type` - Person type classification
- `business_entity_type` - Business entity classification
- `phone_extension` / `work_phone_extension` - Phone extensions
- `private_birthdate` - Privacy flag for birthdate
- `no_email` - Flag for contacts without email

## Implementation

### 1. Created Dedicated `ContactUpdateForm`

**File:** `core/forms.py`

Created a new form class that only includes the 15 fields actually rendered in the contact update template:

```python
class ContactUpdateForm(EmailValidationForm, forms.ModelForm):
    class Meta:
        model = Contact
        fields = [
            'name',
            'last_name',
            'email',
            'phone',
            'mobile',
            'work_phone',
            'id_document_type',
            'id_document',
            'birthdate',
            'gender',
            'education',
            'tags',
            'notes',
            'allow_polls',
            'allow_promotions',
        ]
        widgets = {
            "birthdate": forms.TextInput(attrs={"class": "form-control datepicker"}),
        }
```

**Features:**

- Inherits from `EmailValidationForm` for email validation
- Includes all validation logic from `ContactAdminForm`:
  - Email validation and duplicate checking
  - ID document duplicate checking
  - Tag parsing from Tagify JSON format
- Only processes fields that are actually editable in the UI

### 2. Updated `ContactAdminFormWithNewsletters`

**File:** `support/views/contacts.py`

Changed the inheritance from `ContactAdminForm` to `ContactUpdateForm`:

```python
class ContactAdminFormWithNewsletters(ContactUpdateForm):
    newsletters = ModelMultipleChoiceField(
        queryset=Product.objects.filter(type="N", active=True),
        widget=CheckboxSelectMultiple(...),
        required=False,
    )
    # ... rest of the implementation
```

This form is used by `ContactUpdateView` and now only processes the visible fields plus the newsletters field.

### 3. Updated Imports

**File:** `support/views/contacts.py`

Added `ContactUpdateForm` to the imports:

```python
from core.forms import ContactAdminForm, ContactUpdateForm
```

## Benefits

### Data Integrity

- **Protected Fields:** Fields like `cms_date_joined`, `ranking`, and `protected` are now safe from accidental clearing
- **Preserved Data:** All Contact model fields not in the update form remain unchanged during updates
- **No Side Effects:** Updating basic contact info no longer affects CMS integration data or administrative fields

### Maintainability

- **Clear Separation:** `ContactAdminForm` (all fields) vs `ContactUpdateForm` (user-editable fields)
- **Explicit Control:** The form explicitly lists which fields can be updated through the UI
- **Future-Proof:** Adding new Contact model fields won't accidentally expose them in the update form

### User Experience

- **No Behavior Change:** Users see the same interface and functionality
- **Data Consistency:** Contact information remains stable and reliable
- **Trust:** Users can update contacts without worrying about losing data

## Technical Details

### Fields Excluded from Update Form

The following fields are **excluded** from `ContactUpdateForm` and will never be modified during contact updates:

**CMS Integration:**

- `cms_date_joined` - Managed by CMS system

**Administrative:**

- `protected` - Contact protection flag
- `protection_reason` - Reason for protection
- `ranking` - Contact ranking/score

**Classification:**

- `ocupation` - Contact occupation
- `person_type` - Person type classification
- `business_entity_type` - Business entity type

**Phone Extensions:**

- `phone_extension` - Phone extension
- `work_phone_extension` - Work phone extension

**Privacy Flags:**

- `private_birthdate` - Birthdate privacy setting
- `no_email` - No email flag

**System Fields:**

- Any other Contact model fields not explicitly listed in the form

### Forms Architecture

```text
EmailValidationForm (base validation)
    ├── ContactAdminForm (all fields - for Django admin)
    │   └── Used in: Django admin interface
    │
    └── ContactUpdateForm (user-editable fields only)
        └── ContactAdminFormWithNewsletters (adds newsletter management)
            └── Used in: ContactUpdateView
```

## Testing Recommendations

1. **Verify Field Preservation:**
   - Set `cms_date_joined` on a contact
   - Update the contact through the UI
   - Verify `cms_date_joined` remains unchanged

2. **Test All Excluded Fields:**
   - Set values for `ranking`, `protected`, `person_type`, etc.
   - Perform contact updates
   - Confirm all excluded fields retain their values

3. **Validate Form Functionality:**
   - Test email validation and duplicate checking
   - Test ID document duplicate checking
   - Test tag management
   - Test newsletter subscription/unsubscription

## Migration Notes

- **No Database Changes:** This is a code-only fix
- **No Data Migration Required:** Existing data is unaffected
- **Backward Compatible:** All existing functionality preserved
- **Immediate Effect:** Fix applies as soon as code is deployed

## Related Files

- `core/forms.py` - New `ContactUpdateForm` class
- `support/views/contacts.py` - Updated `ContactAdminFormWithNewsletters` and imports
- `support/templates/create_contact/create_contact.html` - Contact update template (unchanged)
- `support/templates/create_contact/tabs/_data.html` - Form fields template (unchanged)

## Conclusion

This fix ensures data integrity by explicitly controlling which Contact fields can be modified through the contact update interface. Fields managed by external systems (like CMS) or used for administrative purposes are now protected from accidental modification, while maintaining all existing functionality for users.
