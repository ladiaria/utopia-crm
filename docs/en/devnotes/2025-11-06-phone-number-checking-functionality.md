# Phone Number Checking Functionality for CheckForExistingContactsView

**Date:** 2025-11-06
**Ticket:** t955
**Type:** Feature Enhancement
**Component:** Contact Check UI
**Impact:** Operator Experience

## Summary

Extended the `CheckForExistingContactsView` to support phone number verification in addition to email verification. Operators can now check for existing contacts using either email addresses or phone numbers, providing greater flexibility for duplicate detection and contact management workflows.

## Motivation

Previously, the Check for Existing Contacts tool only supported email-based matching. However, many contact lists contain phone numbers without email addresses, or operators may want to verify contacts by phone number. This enhancement addresses that gap by adding full phone number checking capabilities.

## Key Features Implemented

### 1. Phone Number Matching

**New Functionality:**

- Search for contacts using phone numbers from CSV files
- Matches against both `phone` and `mobile` fields in the Contact model
- Uses `phonenumberfield` for intelligent phone number parsing
- Fallback to substring matching if parsing fails
- Displays which field matched (Phone, Mobile, or both)

### 2. Dual Verification Buttons

**Enhanced Interface:**

- **"Check by Email"** button (primary blue): Verifies using 'email' column from CSV
- **"Check by Phone"** button (info cyan): Verifies using 'phone' column from CSV
- Single upload form with two submission options
- Clear visual distinction between verification types

### 3. Separate CSV Templates

**Two Downloadable Templates:**

- **Email Template** (`contact_check_email_template.csv`):
  - Contains 'email' column header
  - Sample data: `example1@company.com`, `example2@domain.org`, `user@example.net`

- **Phone Template** (`contact_check_phone_template.csv`):
  - Contains 'phone' column header
  - Sample data: `+59899123456`, `+59898765432`, `+1234567890`

### 4. Collapsible Instructions

**UX Improvement:**

- Instructions now in a collapsible card (starts collapsed)
- Operators can expand if they need guidance
- Direct access to upload form without scrolling
- Updated instructions explain both email and phone verification methods

## Technical Implementation

### File: `support/views/contacts.py`

#### 1. New Method: `find_matching_contacts_by_phone()` (lines 732-803)

```python
def find_matching_contacts_by_phone(self, phone_number):
    """
    Find matching contacts based on phone or mobile number.
    Returns a list of contacts that match the given phone number.
    Uses phonenumberfield for matching.
    """
    from phonenumber_field.phonenumber import PhoneNumber

    # Try to parse the phone number
    try:
        parsed_phone = PhoneNumber.from_string(phone_number)
    except Exception:
        # If parsing fails, try direct string matching
        contacts = (
            Contact.objects.filter(
                Q(phone__icontains=phone_number) | Q(mobile__icontains=phone_number)
            )
            .prefetch_related(
                Prefetch('subscriptions', queryset=Subscription.objects.filter(active=True, status__in=['OK', 'G']))
            )
            .prefetch_related('contactcampaignstatus_set')
            .annotate(
                is_phone_match=Case(
                    When(phone__icontains=phone_number, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                ),
                is_mobile_match=Case(
                    When(mobile__icontains=phone_number, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                ),
                active_campaign_count=Count(
                    'contactcampaignstatus',
                    filter=Q(contactcampaignstatus__campaign__active=True),
                    distinct=True
                )
            )
            .distinct()
        )
        return contacts

    # Use parsed phone number for matching
    contacts = (
        Contact.objects.filter(
            Q(phone=parsed_phone) | Q(mobile=parsed_phone)
        )
        .prefetch_related(
            Prefetch('subscriptions', queryset=Subscription.objects.filter(active=True, status__in=['OK', 'G']))
        )
        .prefetch_related('contactcampaignstatus_set')
        .annotate(
            is_phone_match=Case(
                When(phone=parsed_phone, then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            ),
            is_mobile_match=Case(
                When(mobile=parsed_phone, then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            ),
            active_campaign_count=Count(
                'contactcampaignstatus',
                filter=Q(contactcampaignstatus__campaign__active=True),
                distinct=True
            )
        )
        .distinct()
    )

    return contacts
```

**Key Features:**

- Searches both `phone` and `mobile` fields using OR query
- Uses `PhoneNumber.from_string()` for intelligent parsing
- Falls back to substring search if parsing fails
- Annotates results with `is_phone_match` and `is_mobile_match` flags
- Prefetches active subscriptions and campaigns for performance

#### 2. Enhanced Method: `process_file()` (lines 805-873)

```python
def process_file(self, file, check_type='email'):
    """
    Process CSV file with automatic delimiter detection.
    Processes email or phone column for contact matching based on check_type.

    Args:
        file: CSV file to process
        check_type: 'email' or 'phone' - determines which column to check
    """
    results = []
    non_matches = []

    # Detect delimiter automatically
    delimiter = detect_csv_delimiter(file)

    for row_number, row in enumerate(csv.DictReader(file, delimiter=delimiter, quotechar='"')):
        if check_type == 'email':
            value = row.get('email', '').strip()
            if not value:
                non_matches.append({'value': value or 'N/A', 'row_number': row_number + 1})
                continue
            contacts = self.find_matching_contacts_by_email(value)

            if contacts:
                for contact in contacts:
                    results.append({
                        'contact': contact,
                        'count': contacts.count(),
                        'email_matches': contact.is_email_match,
                        'has_active_subscription': bool(contact.subscriptions.all()),
                        'is_in_active_campaign': contact.active_campaign_count > 0,
                        'csv_value': value,
                        'csv_row': row_number + 1,
                        'check_type': 'email',
                    })
            else:
                non_matches.append({'value': value, 'row_number': row_number + 1})

        elif check_type == 'phone':
            value = row.get('phone', '').strip()
            if not value:
                non_matches.append({'value': value or 'N/A', 'row_number': row_number + 1})
                continue
            contacts = self.find_matching_contacts_by_phone(value)

            if contacts:
                for contact in contacts:
                    results.append({
                        'contact': contact,
                        'count': contacts.count(),
                        'phone_matches': getattr(contact, 'is_phone_match', False),
                        'mobile_matches': getattr(contact, 'is_mobile_match', False),
                        'has_active_subscription': bool(contact.subscriptions.all()),
                        'is_in_active_campaign': contact.active_campaign_count > 0,
                        'csv_value': value,
                        'csv_row': row_number + 1,
                        'check_type': 'phone',
                    })
            else:
                non_matches.append({'value': value, 'row_number': row_number + 1})

    return results, non_matches, delimiter
```

**Changes:**

- Added `check_type` parameter to determine verification method
- Processes 'email' or 'phone' column based on check type
- Returns match type information (phone vs mobile)
- Maintains automatic delimiter detection for both types

#### 3. Separate Template Download Methods (lines 883-915)

```python
def download_email_template(self):
    """
    Generate and return an email CSV template file for users to download.
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="contact_check_email_template.csv"'

    writer = csv.writer(response)
    writer.writerow(['email'])
    writer.writerow(['example1@company.com'])
    writer.writerow(['example2@domain.org'])
    writer.writerow(['user@example.net'])

    return response

def download_phone_template(self):
    """
    Generate and return a phone CSV template file for users to download.
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="contact_check_phone_template.csv"'

    writer = csv.writer(response)
    writer.writerow(['phone'])
    writer.writerow(['+59899123456'])
    writer.writerow(['+59898765432'])
    writer.writerow(['+1234567890'])

    return response
```

#### 4. Updated Method: `form_valid()` (lines 917-937)

```python
def form_valid(self, form):
    csvfile = form.cleaned_data['file']
    decoded_file = io.StringIO(csvfile.read().decode('utf-8'))

    # Determine check type based on which button was pressed
    check_type = 'phone' if 'check_phone' in self.request.POST else 'email'

    results, non_matches, delimiter = self.process_file(decoded_file, check_type=check_type)

    context = self.get_context_data(form=form)
    context['results'] = results
    context['non_matches'] = non_matches
    context['detected_delimiter'] = 'semicolon (;)' if delimiter == ';' else 'comma (,)'
    context['check_type'] = check_type

    active_subscriptions = sum(1 for result in results if result['has_active_subscription'])
    context['active_subscriptions'] = active_subscriptions
    active_campaigns = sum(1 for result in results if result['is_in_active_campaign'])
    context['active_campaigns'] = active_campaigns

    return self.render_to_response(context)
```

**Changes:**

- Detects which button was pressed (`check_email` vs `check_phone`)
- Passes `check_type` to context for dynamic template rendering
- Maintains all existing functionality (counters, delimiter detection)

### File: `support/templates/check_for_existing_contacts.html`

#### 1. Collapsible Instructions Card (lines 37-116)

```html
<div class="card card-info collapsed-card mb-3">
  <div class="card-header">
    <h3 class="card-title">
      <i class="fas fa-info-circle"></i>
      {% trans "Instructions - How Contact Matching Works" %}
    </h3>
    <div class="card-tools">
      <button type="button" class="btn btn-tool" data-card-widget="collapse">
        <i class="fas fa-plus"></i>
      </button>
    </div>
  </div>
  <div class="card-body" style="display: none;">
    <!-- Full instructions here -->
  </div>
</div>
```

**Features:**

- Starts collapsed (`collapsed-card` class + `display: none`)
- Explains both email and phone verification methods
- Includes use cases and expected results

#### 2. Two Template Download Buttons (lines 17-22)

```html
<a href="?download_email_template=1" class="btn btn-success btn-sm mr-2">
  <i class="fas fa-download"></i> {% trans "Download Email CSV Template" %}
</a>
<a href="?download_phone_template=1" class="btn btn-info btn-sm mr-2">
  <i class="fas fa-download"></i> {% trans "Download Phone CSV Template" %}
</a>
```

#### 3. Two Submit Buttons (lines 135-142)

```html
<div class="btn-group" role="group">
  <button type="submit" name="check_email" class="btn btn-primary">
    <i class="fas fa-envelope"></i> {% trans "Check by Email" %}
  </button>
  <button type="submit" name="check_phone" class="btn btn-info">
    <i class="fas fa-phone"></i> {% trans "Check by Phone" %}
  </button>
</div>
```

#### 4. Dynamic Results Table (lines 174-229)

```html
<thead>
  <tr>
    <th>{% trans "Contact ID" %}</th>
    <th>{% trans "CSV Row" %}</th>
    <th>{% trans "Contact" %}</th>
    {% if check_type == 'email' %}
      <th>{% trans "Email" %}</th>
    {% elif check_type == 'phone' %}
      <th>{% trans "Phone Number" %}</th>
      <th>{% trans "Match Type" %}</th>
    {% endif %}
    <th>{% trans "Has Active Subscription" %}</th>
    <th>{% trans "In Active Campaign" %}</th>
  </tr>
</thead>
<tbody>
  {% for result in results %}
    <tr>
      <td>{{ result.contact.id }}</td>
      <td>{{ result.csv_row }}</td>
      <td>
        <a href="{% url 'contact_detail' result.contact.id %}">{{ result.contact }}</a>
      </td>
      {% if check_type == 'email' %}
        <td>{{ result.csv_value }}</td>
      {% elif check_type == 'phone' %}
        <td>{{ result.csv_value }}</td>
        <td>
          {% if result.phone_matches %}
            <span class="badge bg-info">{% trans "Phone" %}</span>
          {% endif %}
          {% if result.mobile_matches %}
            <span class="badge bg-success">{% trans "Mobile" %}</span>
          {% endif %}
        </td>
      {% endif %}
      <!-- ... subscription and campaign columns ... -->
    </tr>
  {% endfor %}
</tbody>
```

**Features:**

- Dynamic columns based on check type
- "Match Type" column shows Phone/Mobile badges
- Visual indicators for which field matched

#### 5. Check Type Indicators (lines 154-158, 239-243)

```html
{% if check_type == 'email' %}
  - <span class="badge bg-primary">
      <i class="fas fa-envelope"></i> {% trans "Email Check" %}
    </span>
{% elif check_type == 'phone' %}
  - <span class="badge bg-info">
      <i class="fas fa-phone"></i> {% trans "Phone Check" %}
    </span>
{% endif %}
```

## Use Cases

### Use Case 1: Pre-Import Phone Number Validation

**Scenario:** Operator has a list of phone numbers from a marketing campaign

1. Download phone CSV template
2. Fill with phone numbers from campaign
3. Upload and click "Check by Phone"
4. Review which contacts already exist
5. Export "No Matches" to import only new contacts

**Benefit:** Prevents duplicate contact creation

### Use Case 2: Duplicate Detection by Phone

**Scenario:** Operator suspects duplicate contacts with different emails but same phone

1. Upload CSV with phone numbers
2. Click "Check by Phone"
3. System shows matches with indicator (Phone or Mobile field)
4. Review existing contacts before creating duplicates

**Benefit:** Identifies duplicates that email checking would miss

### Use Case 3: Mixed Verification Workflow

**Scenario:** Operator has partial contact information

1. First, verify by email
2. Export "No Matches"
3. Verify no-matches by phone
4. Identify contacts that have phone but no email registered

**Benefit:** Comprehensive duplicate checking using multiple criteria

## Benefits

### For Operators

✅ **Greater Flexibility:** Check contacts by email or phone number
✅ **Duplicate Prevention:** Identify duplicates using multiple criteria
✅ **Better UX:** Collapsible instructions, direct form access
✅ **Clear Feedback:** Visual indicators show verification type and match type
✅ **Template Guidance:** Separate templates for each verification method

### For System Administrators

✅ **Reduced Duplicates:** More comprehensive checking before import
✅ **Better Data Quality:** Operators can verify using available information
✅ **Flexible Workflows:** Support for different data sources (email lists, phone lists)

## Comparison: Email vs Phone Verification

| Feature | Email Verification | Phone Verification |
|---------|-------------------|-------------------|
| **CSV Column** | 'email' | 'phone' |
| **Fields Searched** | Contact.email | Contact.phone, Contact.mobile |
| **Matching** | Case-insensitive exact match | Parsed phone number or substring |
| **Match Indicator** | Email address | Phone/Mobile badge |
| **Use Case** | Email-based contact lists | Phone-based contact lists |
| **Parsing** | None (direct string match) | phonenumberfield parsing |
| **Fallback** | N/A | Substring match if parsing fails |

## Technical Details

### Phone Number Parsing

**Primary Method:**

- Uses `phonenumberfield.PhoneNumber.from_string()`
- Normalizes phone numbers for consistent matching
- Handles international formats (+598, +1, etc.)

**Fallback Method:**

- If parsing fails, uses `__icontains` substring search
- Allows matching partial or malformed numbers
- Useful for local numbers without country code

### Query Optimization

**Prefetch Strategy:**

- Prefetch active subscriptions in single query
- Prefetch campaign statuses in single query
- Annotate match flags to avoid additional queries
- Use `Q()` objects for efficient OR queries

**Performance:**

- Single database query per phone number
- Prefetch prevents N+1 query problems
- Annotations eliminate template-level queries

### Backward Compatibility

✅ **Email verification unchanged:** All existing functionality preserved
✅ **Template structure maintained:** Same layout and export features
✅ **Delimiter detection:** Works for both email and phone CSVs
✅ **No breaking changes:** Existing workflows continue to work

## Files Modified

### utopia-crm (base repository)

1. **`support/views/contacts.py`**
   - Lines 732-803: New `find_matching_contacts_by_phone()` method
   - Lines 805-873: Enhanced `process_file()` with `check_type` parameter
   - Lines 875-881: Updated `get()` to handle two template types
   - Lines 883-898: New `download_email_template()` method
   - Lines 900-915: New `download_phone_template()` method
   - Lines 917-937: Updated `form_valid()` to detect check type

2. **`support/templates/check_for_existing_contacts.html`**
   - Lines 17-22: Two template download buttons
   - Lines 37-116: Collapsible instructions card
   - Lines 118-143: Form with two submit buttons
   - Lines 147-232: Dynamic results table with match type column
   - Lines 234-282: Dynamic non-matches table

## Testing Recommendations

### Functional Testing

1. **Email Verification (Existing):**
   - Upload email CSV
   - Click "Check by Email"
   - Verify matches display correctly

2. **Phone Verification (New):**
   - Upload phone CSV with international format (+598...)
   - Click "Check by Phone"
   - Verify matches show Phone/Mobile badges

3. **Phone Fallback:**
   - Upload phone CSV with local format (099...)
   - Click "Check by Phone"
   - Verify substring matching works

4. **Contact with Both Fields:**
   - Contact has phone=+59899111111 and mobile=+59899222222
   - Upload CSV with +59899111111
   - Verify shows "Phone" badge
   - Upload CSV with +59899222222
   - Verify shows "Mobile" badge

5. **Collapsible Instructions:**
   - Load page
   - Verify instructions start collapsed
   - Click expand button
   - Verify instructions display

### Edge Cases

1. **Empty phone field:** Should add to non-matches
2. **Invalid phone format:** Should use fallback substring search
3. **Duplicate phone numbers in CSV:** Should show multiple rows
4. **Phone matches multiple contacts:** Should show all matches

## Future Enhancements

Potential improvements for future iterations:

1. **Combined Verification:** Check by both email AND phone in single operation
2. **Advanced Matching:** Fuzzy phone number matching for typos
3. **Bulk Actions:** Select matches and add to campaign directly
4. **Export Enhancement:** Include match type in CSV export
5. **Statistics Dashboard:** Show matching statistics (% found by email vs phone)

## Migration Notes

**No database migrations required** - This is a pure UI/logic enhancement.

**No configuration changes required** - Works with existing Contact model.

**Dependencies:**

- Requires `phonenumberfield` package (already in requirements.txt)
- Requires Contact model to have `phone` and `mobile` fields using PhoneNumberField

## Conclusion

This enhancement significantly expands the utility of the Check for Existing Contacts tool by:

- Adding phone number verification alongside email verification
- Providing clear visual feedback on verification type and match type
- Improving UX with collapsible instructions and separate templates
- Maintaining backward compatibility with existing workflows

Operators now have flexible options for checking contacts using whatever information is available (email or phone), reducing duplicates and improving data quality.

---

**Related Documentation:**

- [Check for Existing Contacts Documentation Improvements (2025-10-31)](2025-10-31-check-existing-contacts-documentation-improvements.md)
- [Import Contacts Enhancements (2025-10-28)](2025-10-28-import-contacts-enhancements.md)
