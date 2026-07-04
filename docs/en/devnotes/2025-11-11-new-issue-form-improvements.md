# New Issue Form User Experience Improvements

**Date:** 2025-11-11
**Type:** Feature Enhancement & UX Improvement
**Component:** Issue Creation Form
**Impact:** User Experience, Data Quality, Form Validation

## Summary

Enhanced the new issue creation form with improved user guidance through helper text for related objects and a required activity type field with a translatable placeholder. These changes improve data quality by ensuring users understand what information is needed and provide proper activity tracking for all issues.

## Motivation

The issue creation form (`NewIssueView`) is a critical tool for tracking customer issues. User feedback and testing revealed two areas for improvement:

1. **Unclear Related Objects Selection:** Users were unsure about which related objects (subscription product, subscription, or product) they should select, leading to incomplete issue records
2. **Activity Type Confusion:** The activity type field had no clear guidance, and there was uncertainty about whether an activity should always be created

## Key Features Implemented

### 1. Helper Text for Related Objects Section

**Problem:**
Users creating issues didn't understand that they needed to select at least one related object (subscription product, subscription, or product) to provide context about what the contact had issues with.

**Solution:**
Added descriptive helper text below the "Related Items" section title in the template.

**File:** `support/templates/new_issue.html`

**Implementation:**

```html
<!-- Related Items Section -->
<div class="form-section">
  <div class="form-section-title">
    <i class="fas fa-link mr-1"></i>
    {% trans "Related Items" %}
  </div>
  <small class="form-help-text d-block mb-3">
    <i class="fas fa-info-circle mr-1"></i>
    {% trans "Please select at least one related item to provide information about what the contact had issues with." %}
  </small>
  <div class="form-group id_subscription_product">
    <label for="id_subscription_product">{{ form.subscription_product.label }}</label>
    {{ form.subscription_product }}
    <span class="error invalid-feedback">{{ form.subscription_product.errors }}</span>
  </div>
  <!-- More fields... -->
</div>
```

**Benefits:**

- **Clear Guidance:** Users understand they need to select at least one related item
- **Better Data Quality:** More complete issue records with proper context
- **Reduced Errors:** Fewer incomplete issues missing critical relationship data
- **Professional Appearance:** Consistent with other help text in the form

### 2. Required Activity Type with Translatable Placeholder

**Problem:**
The activity type field initially had an optional configuration, but business requirements determined that every issue should have an associated activity for proper tracking. The field lacked clear guidance about what to select.

**Solution:**
Made the activity type field required and added a translatable placeholder to guide users.

**File:** `support/forms.py`

**Implementation:**

```python
activity_type = forms.ChoiceField(
    label=_("Activity Type (Required)"),
    widget=forms.Select(attrs={"class": "form-control"}),
    choices=[('', _('Select an activity type'))] + list(get_activity_types()),
    required=True,
)
```

**Key Changes:**

1. **Translatable Placeholder:** Changed from generic `'---------'` to `_('Select an activity type')`
2. **Required Field:** Set `required=True` to enforce activity type selection
3. **Updated Label:** Changed to "Activity Type (Required)" for clarity
4. **Visual Indicator:** Added `required-field` class to form group in template

**Template Update:**

```html
<div class="form-group required-field">
  <label for="id_activity_type">{{ form.activity_type.label }}</label>
  {{ form.activity_type }}
  <span class="error invalid-feedback">{{ form.activity_type.errors }}</span>
</div>
```

**Benefits:**

- **Internationalization:** Placeholder text translates to user's language
- **Clear Expectations:** Users know they must select an activity type
- **Data Consistency:** All issues now have associated activities for tracking
- **Better UX:** Meaningful placeholder instead of generic dashes

### 3. Conditional Activity Creation Logic

**File:** `support/views/all_views.py`

**Implementation:**

Although the field is now required, the view logic was updated to handle activity creation conditionally, providing flexibility for future requirements:

```python
# Create related activity only if activity_type is provided
if form.cleaned_data.get("activity_type"):
    Activity.objects.create(
        datetime=datetime.now(),
        contact=self.contact,
        issue=issue,
        notes=_("See related issue"),
        activity_type=form.cleaned_data["activity_type"],
        status="C",  # completed
        direction="I",
    )
```

**Benefits:**

- **Defensive Programming:** Handles edge cases gracefully
- **Future Flexibility:** Easy to make field optional again if requirements change
- **Clean Code:** Explicit conditional logic is more maintainable

### 4. Removed Default Activity Type

**File:** `support/views/all_views.py`

**Change:**

Removed the default `'activity_type': 'C'` from the `get_initial()` method to ensure users make an explicit selection:

```python
def get_initial(self):
    initial = super().get_initial()
    initial.update({
        'copies': 1,
        'contact': self.contact,
        'category': self.category,
        # Removed: 'activity_type': 'C',
    })
    return initial
```

**Benefits:**

- **Explicit Selection:** Users must consciously choose the activity type
- **Better Data Quality:** No automatic defaults that might be incorrect
- **User Awareness:** Forces users to think about the appropriate activity type

## Technical Details

### Files Modified

1. **support/templates/new_issue.html**
   - Added helper text to Related Items section
   - Added `required-field` class to activity type form group
   - Enhanced user guidance with info icon

2. **support/forms.py**
   - Updated `activity_type` field with translatable placeholder
   - Set field to `required=True`
   - Updated label to indicate required status
   - Changed choices to include `_('Select an activity type')`

3. **support/views/all_views.py**
   - Added conditional check before creating activity
   - Removed default activity type from `get_initial()`
   - Improved code defensiveness

### Internationalization

The placeholder text uses Django's translation system:

```python
choices=[('', _('Select an activity type'))] + list(get_activity_types())
```

This ensures the placeholder displays in the user's selected language:

- **English:** "Select an activity type"
- **Spanish:** "Seleccione un tipo de actividad"
- **Other languages:** Translates according to `.po` files

### Form Validation

With `required=True`, Django automatically validates that:

1. The field is not empty
2. The selected value exists in the choices
3. Proper error messages display if validation fails

The CSS class `required-field` adds a visual asterisk (*) to the label:

```css
.required-field label::after {
  content: " *";
  color: #dc3545;
}
```

## User Experience Improvements

### Before

- **Related Items:** No guidance on what to select or why
- **Activity Type:** Optional field with generic placeholder
- **Confusion:** Users unsure if they needed to select related items
- **Inconsistency:** Some issues created without activities

### After

- **Related Items:** Clear helper text explaining the purpose and requirement
- **Activity Type:** Required field with meaningful, translated placeholder
- **Clarity:** Users understand what information is needed
- **Consistency:** All issues have associated activities for tracking

## Benefits

1. **Improved Data Quality:**
   - More complete issue records with proper related objects
   - Consistent activity tracking for all issues
   - Better context for issue resolution

2. **Enhanced User Experience:**
   - Clear guidance reduces confusion
   - Translatable placeholder supports international users
   - Visual indicators (asterisk, help text) guide users

3. **Better Maintainability:**
   - Conditional logic provides flexibility
   - Explicit validation rules
   - Self-documenting code with clear intent

4. **Internationalization:**
   - Placeholder text translates properly
   - Consistent with Django i18n best practices
   - Supports multi-language deployments

5. **Data Consistency:**
   - All issues have activity tracking
   - Related objects properly linked
   - Better reporting and analytics capabilities

## Migration Notes

- **No database migration required** - Only form and template changes
- **Backward compatible** - Existing issues unaffected
- **Immediate effect** - Changes active as soon as deployed
- **No data migration needed** - Works with existing data

## Testing Recommendations

### Manual Testing

1. **Test helper text display:**
   - Navigate to new issue form
   - Verify helper text appears below "Related Items" title
   - Check text is properly translated in different languages
   - Verify info icon displays correctly

2. **Test activity type field:**
   - Verify placeholder shows "Select an activity type"
   - Confirm field is marked as required (red asterisk)
   - Test form submission without selecting activity type
   - Verify error message displays correctly

3. **Test form validation:**
   - Submit form without activity type (should fail)
   - Submit form with activity type (should succeed)
   - Verify activity is created in database
   - Check activity has correct type and status

4. **Test internationalization:**
   - Switch to Spanish language
   - Verify placeholder translates to "Seleccione un tipo de actividad"
   - Check helper text translates properly
   - Test form submission in different languages

5. **Test related objects:**
   - Create issue with subscription product
   - Create issue with subscription
   - Create issue with product
   - Verify all relationships save correctly

### Browser Compatibility

Test in:

- Chrome/Edge (Chromium)
- Firefox
- Safari
- Mobile browsers (iOS Safari, Chrome Mobile)

### Accessibility Testing

- Verify screen readers announce helper text
- Test keyboard navigation to activity type field
- Confirm required field indicator is accessible
- Check color contrast for helper text

## Future Considerations

1. **Validation Rules:** Add backend validation to ensure at least one related object is selected
2. **Dynamic Help Text:** Show different help text based on selected category
3. **Activity Type Presets:** Pre-select common activity types based on issue category
4. **Related Object Validation:** Warn if no related objects are selected before submission
5. **Activity Notes:** Allow users to add custom notes to the created activity

## Related Components

- **Issue Model:** `support/models.py` - Defines issue data structure
- **Activity Model:** `core/models.py` - Stores activity records
- **Issue Views:** `support/views/all_views.py` - Handles issue creation logic
- **Issue Forms:** `support/forms.py` - Form validation and field definitions

## Conclusion

These targeted improvements enhance the new issue form's usability and data quality without requiring database changes or complex migrations. The addition of clear helper text for related objects and a required activity type field with translatable placeholder ensures users understand what information is needed and provides consistent activity tracking across all issues. These changes align with Django best practices for internationalization and form validation while maintaining backward compatibility with existing code.
