# Campaign Editing in Sales Validation

**Date:** 2025-12-29
**Type:** Feature Enhancement, UI Improvement
**Component:** Sales Records, Subscription Validation
**Impact:** Sales Management, Data Accuracy, User Experience

## Summary

Enhanced the subscription validation view to allow managers to edit the campaign associated with a sales record during the validation process. Implemented Select2 for both seller and campaign dropdowns to provide a modern, searchable interface with improved usability.

## Motivation

Previously, when validating a subscription and its sales record, managers could only modify:

1. The seller assigned to the sale
2. The commission value
3. Whether the sale can be commissioned

However, there was no way to edit the **campaign** associated with the sales record during validation. This created issues when:

- A sale was incorrectly attributed to the wrong campaign
- The campaign needed to be updated after the initial sale was recorded
- Data corrections were needed for reporting accuracy

Managers had to either:

- Accept incorrect campaign data
- Edit the sales record separately in the admin interface
- Leave the validation incomplete

This workflow was inefficient and error-prone, especially for campaign-based reporting and analytics.

## Implementation

### 1. Enhanced ValidateSubscriptionForm

**File:** `support/forms.py`

Added a campaign field to the form with proper queryset filtering:

```python
class ValidateSubscriptionForm(forms.ModelForm):
    override_commission_value = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": _("Override amount"), "min": 0}),
    )
    seller = forms.ModelChoiceField(
        queryset=Seller.objects.filter(internal=True),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    campaign = forms.ModelChoiceField(
        queryset=Campaign.objects.filter(active=True),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    class Meta:
        model = SalesRecord
        fields = ("can_be_commissioned", "override_commission_value", "seller", "campaign")
        widgets = {
            "can_be_commissioned": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
```

**Key Features:**

- **Active campaigns only:** Filters to show only active campaigns to avoid selecting inactive ones
- **Optional field:** Campaign can be left blank if not applicable
- **Form control styling:** Consistent with other form fields

### 2. Implemented Select2 for Enhanced UX

**File:** `support/templates/validate_subscription_sales_record.html`

Added Select2 library and initialization for both seller and campaign fields:

**CSS Added:**

```html
{% block stylesheets %}
  {{ block.super }}
  <link href="{% static 'admin-lte/plugins/select2/css/select2.min.css' %}" rel="stylesheet" />
  <link href="{% static 'admin-lte/plugins/select2-bootstrap4-theme/select2-bootstrap4.min.css' %}" rel="stylesheet" />
{% endblock stylesheets %}
```

**JavaScript Initialization:**

```javascript
{% block extra_js %}
  <script src="{% static 'admin-lte/plugins/select2/js/select2.full.min.js' %}"></script>
  <script>
  $(function() {
    $('#id_seller').select2({
      theme: 'bootstrap4',
      width: '100%',
      placeholder: '{% trans "Select seller" %}',
      allowClear: false
    });

    $('#id_campaign').select2({
      theme: 'bootstrap4',
      width: '100%',
      placeholder: '{% trans "Select campaign" %}',
      allowClear: true
    });
  });
  </script>
{% endblock extra_js %}
```

**Select2 Configuration:**

- **Seller field:** `allowClear: false` (required field)
- **Campaign field:** `allowClear: true` (optional field with X button to clear)
- **Bootstrap 4 theme:** Consistent styling with AdminLTE
- **Searchable:** Type to filter options
- **Translatable placeholders:** User-friendly hints

### 3. Restructured Form Layout

**File:** `support/templates/validate_subscription_sales_record.html`

Reorganized the form using Bootstrap grid system for better spacing and alignment:

**Before:**

- Used flexbox with inconsistent widths
- Fields had varying spacing
- Labels and inputs not properly aligned

**After:**

```html
<div class="row mb-3">
  <div class="col-md-3">
    <label for="seller_id" class="form-label">{% trans "Seller" %}</label>
    {% render_field form.seller class="form-control" %}
  </div>
  <div class="col-md-3">
    <label for="campaign_id" class="form-label">{% trans "Campaign" %}</label>
    {% render_field form.campaign class="form-control" %}
  </div>
  <div class="col-md-3">
    <label for="override" class="form-label">{% trans "Add Commission Value Manually" %}</label>
    {% render_field form.override_commission_value class="form-control" %}
  </div>
  <div class="col-md-3">
    <div class="form-check mt-4 pt-2">
      {% render_field form.can_be_commissioned class="form-check-input" %}
      <label for="can_be_commissioned_id" class="form-check-label">{% trans "Can be commissioned" %}</label>
    </div>
  </div>
</div>
```

**Layout Improvements:**

- **Equal width columns:** Each field occupies 25% width (`col-md-3`)
- **Consistent spacing:** Bootstrap margin utilities (`mb-3`, `mt-4`, `pt-2`)
- **Proper alignment:** Labels above inputs, checkbox aligned with other fields
- **Responsive design:** Adapts to different screen sizes

## Technical Details

### Form Field Configuration

**Campaign Field:**

- **Model:** SalesRecord
- **Field:** campaign (ForeignKey to Campaign)
- **Queryset:** `Campaign.objects.filter(active=True)`
- **Required:** False (optional)
- **Widget:** Select with form-control class

**Validation:**

- Django's ModelForm handles validation automatically
- Only active campaigns can be selected
- Field can be left blank (NULL in database)

### Select2 Implementation

Used local AdminLTE plugin assets:

- `admin-lte/plugins/select2/css/select2.min.css`
- `admin-lte/plugins/select2-bootstrap4-theme/select2-bootstrap4.min.css`
- `admin-lte/plugins/select2/js/select2.full.min.js`

**Benefits over standard select:**

- Searchable dropdown (type to filter)
- Better visual presentation
- Clear button for optional fields
- Consistent with modern UI patterns
- Mobile-friendly

## Benefits

### 1. Complete Data Management

- **Edit all relevant fields:** Seller, campaign, and commission in one place
- **No admin access needed:** Managers can correct campaign data during validation
- **Single workflow:** No need to switch between views

### 2. Improved Data Accuracy

- **Fix campaign errors:** Correct misattributed campaigns immediately
- **Better reporting:** Accurate campaign attribution for analytics
- **Audit trail:** Changes tracked through validation process

### 3. Enhanced User Experience

- **Searchable dropdowns:** Find sellers and campaigns quickly by typing
- **Visual clarity:** Equal-width fields with proper spacing
- **Clear optional fields:** X button on campaign field indicates it's optional
- **Consistent interface:** Matches other Select2 implementations in the system

### 4. Workflow Efficiency

- **One-step validation:** Edit all fields and validate in single action
- **Reduced context switching:** No need to open admin interface
- **Faster corrections:** Immediate campaign updates during validation

## Usage

### For Managers

Access via: **Campaign Management > Sales Record > Validate**

**Validation Workflow:**

1. Click "Validate" button on an unvalidated sales record
2. Review subscription and sales record details
3. **Edit fields as needed:**
   - **Seller:** Select from internal sellers (searchable)
   - **Campaign:** Select from active campaigns (searchable, optional)
   - **Commission:** Override calculated commission if needed
   - **Can be commissioned:** Check if sale should generate commission
4. Click "Validate" to save changes and mark subscription as validated

**Example Use Cases:**

- **Correct campaign attribution:** Sale was recorded under wrong campaign
- **Add missing campaign:** Sale was created without campaign, add it during validation
- **Remove campaign:** Clear campaign field if it was incorrectly set
- **Update seller and campaign:** Fix both in single validation step

### Search Functionality

**Seller Dropdown:**

- Type seller name to filter list
- Required field (no clear button)
- Shows only internal sellers

**Campaign Dropdown:**

- Type campaign name to filter list
- Optional field (X button to clear)
- Shows only active campaigns
- Can be left blank

## Testing

### Verification Steps

1. **Test campaign selection:**
   - Go to Sales Record list
   - Click "Validate" on an unvalidated record
   - Click on Campaign dropdown
   - Type to search for a campaign
   - Select a campaign
   - Click "Validate"
   - Verify campaign is saved to sales record

2. **Test campaign clearing:**
   - Open validation view for record with campaign
   - Click X button on campaign field
   - Click "Validate"
   - Verify campaign is removed from sales record

3. **Test Select2 search:**
   - Click on Seller dropdown
   - Type partial seller name
   - Verify list filters to matching sellers
   - Repeat for Campaign dropdown

4. **Test form layout:**
   - Verify all four fields have equal width
   - Verify labels are properly aligned
   - Verify checkbox aligns with other fields
   - Test on different screen sizes

5. **Test combined edits:**
   - Change seller, campaign, and commission value
   - Click "Validate"
   - Verify all changes are saved correctly

## Files Modified

- `support/forms.py` - Added campaign field to ValidateSubscriptionForm
- `support/templates/validate_subscription_sales_record.html` - Added Select2, restructured form layout, added campaign field

## Database Impact

**No database changes required** - uses existing SalesRecord.campaign field:

- Field already exists in database
- ForeignKey to Campaign model
- Nullable (can be NULL)

## Backward Compatibility

- All existing validation functionality preserved
- Campaign field is optional - can be left blank
- No breaking changes to validation workflow
- Existing sales records unaffected

## Future Enhancements

Potential improvements for future iterations:

1. **Campaign history:** Track campaign changes in validation history
2. **Bulk campaign updates:** Update campaign for multiple sales records
3. **Campaign validation rules:** Warn if campaign doesn't match subscription dates
4. **Campaign suggestions:** Auto-suggest campaign based on subscription date
5. **Campaign statistics:** Show campaign performance during validation

## Notes

- Select2 uses local AdminLTE plugin assets for better performance
- Campaign field filters to active campaigns only to prevent selecting inactive ones
- Both seller and campaign use Select2 for consistent user experience
- Form layout uses Bootstrap grid for responsive design
- All labels and placeholders are translatable for internationalization

## Related Features

- Sales record validation (ValidateSubscriptionSalesRecord view)
- Campaign management and reporting
- Seller console functionality
- Subscription management
