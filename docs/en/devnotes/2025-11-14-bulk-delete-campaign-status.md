# Bulk Delete Campaign Status Records

**Date:** 2025-11-14
**Ticket:** t968
**Type:** New Feature
**Component:** Campaign Management
**Impact:** Manager Operations
**Access:** Managers Group Only

## Summary

Implemented a new bulk deletion tool that allows managers to remove multiple contacts from campaigns by uploading a CSV file with contact IDs. This feature provides a safe, efficient way to clean up campaign assignments without manual one-by-one deletion.

## Problem

Managers needed a way to remove large numbers of contacts from campaigns efficiently. Previously, there was no bulk operation available for deleting `ContactCampaignStatus` records, requiring:

1. Manual deletion through Django admin (one at a time)
2. Direct database access for bulk operations
3. Custom scripts for each cleanup task

This was time-consuming and error-prone, especially when cleaning up campaigns with hundreds or thousands of contacts.

## Solution Implemented

### New Bulk Delete View

Created a dedicated view accessible only to users in the **Managers** group that allows:

1. **CSV Upload**: Upload a file with contact IDs to remove from a campaign
2. **Campaign Selection**: Select the target campaign using a searchable dropdown
3. **Bulk Deletion**: Delete all matching `ContactCampaignStatus` records in a single transaction
4. **CSV Template**: Download a pre-formatted template for easy file preparation

### Key Features

#### 1. Manager-Only Access

```python
def test_func(self):
    """Only users in the Managers group can access this view."""
    return self.request.user.groups.filter(name='Managers').exists()
```

- Uses `UserPassesTestMixin` to restrict access
- Only members of the "Managers" group can use this feature
- Prevents accidental or unauthorized bulk deletions

#### 2. Flexible CSV Format

The system accepts multiple column name variations (case-insensitive):

- `contact_id`
- `id`
- `contact id`
- `contactid`

**Example CSV:**

```csv
contact_id
123
456
789
```

#### 3. Automatic Delimiter Detection

Uses the existing `detect_csv_delimiter()` utility to handle:

- Comma-delimited files (`,`)
- Semicolon-delimited files (`;`)
- Automatically detects the correct format

#### 4. Searchable Campaign Dropdown

Implemented with Select2 for enhanced UX:

- Search campaigns by name or ID
- Full-width dropdown with proper Bootstrap 4 styling
- Shows all active campaigns
- Real-time filtering as you type

#### 5. Downloadable CSV Template

Users can download a ready-to-use template:

- Click "Download CSV Template" button
- Get a file with proper headers and example data
- Filename: `bulk_delete_campaign_status_template.csv`

#### 6. Transaction Safety

All deletions occur within a database transaction:

```python
with transaction.atomic():
    deleted_count, _unused = ContactCampaignStatus.objects.filter(
        contact_id__in=contact_ids, campaign=campaign
    ).delete()
```

- Either all records are deleted or none
- Prevents partial deletions on errors
- Maintains database integrity

## Technical Implementation

### Files Created

1. **`support/views/campaign_management.py`**
   - New module for campaign management views
   - `BulkDeleteCampaignStatusView` class
   - CSV template download functionality
   - Manager group permission checking

2. **`support/templates/campaign_management/bulk_delete_campaign_status.html`**
   - User-friendly interface with instructions
   - Warning alerts about permanent deletion
   - CSV format examples and guidelines
   - Select2-enabled campaign dropdown
   - Form validation and error display

### Files Modified

3. **`support/forms.py`**
   - Added `BulkDeleteCampaignStatusForm`
   - CSV file upload field with validation
   - Campaign selection with Select2 widget
   - File type validation (CSV only)

4. **`support/urls.py`**
   - Added URL pattern: `bulk_delete_campaign_status/`
   - Imported view from campaign_management module

5. **`templates/components/sidebar_items/_campaign_management.html`**
   - Added "Bulk Delete Campaign Status" menu item
   - Positioned after "Sales Records"
   - Trash icon for visual clarity
   - Active state highlighting

### View Architecture

```python
class BulkDeleteCampaignStatusView(BreadcrumbsMixin, UserPassesTestMixin, FormView):
    """
    View for bulk deleting ContactCampaignStatus records.

    Access: Only users in the 'Managers' group can access this view.
    """
    template_name = 'campaign_management/bulk_delete_campaign_status.html'
    form_class = BulkDeleteCampaignStatusForm
    success_url = reverse_lazy('bulk_delete_campaign_status')
```

## User Interface

### Navigation

Access via sidebar: **Campaign Management → Bulk Delete Campaign Status**

### Workflow

1. **Download Template** (optional)
   - Click "Download CSV Template" button
   - Get pre-formatted file with examples

2. **Prepare CSV File**
   - Add contact IDs to the file (one per row)
   - Save as CSV format

3. **Upload and Select**
   - Upload the CSV file
   - Search and select the target campaign

4. **Execute Deletion**
   - Click "Delete Campaign Status Records"
   - System processes all IDs in transaction
   - Shows success message with deletion count

### User Feedback

The system provides clear feedback:

- **Success**: "Successfully deleted {count} ContactCampaignStatus record(s) for campaign '{campaign}' with {total} contact ID(s) from CSV."
- **Warning**: "Could not find contact_id column in CSV. Expected column names: 'contact_id', 'id', 'contact id', or 'contactid'"
- **Warning**: "No valid contact IDs found in the CSV file."
- **Error**: Form validation errors for invalid files

### Visual Design

- **Warning alerts** about permanent deletion
- **Info cards** with step-by-step instructions
- **CSV format examples** with code blocks
- **Bootstrap 4 styling** matching AdminLTE theme
- **Select2 dropdown** with search functionality
- **Responsive layout** for all screen sizes

## Benefits

### For Managers

- ✅ **Efficient Bulk Operations**: Remove hundreds of contacts in seconds
- ✅ **Safe Deletions**: Transaction-based, all-or-nothing approach
- ✅ **Easy to Use**: Simple CSV upload with clear instructions
- ✅ **Template Provided**: No need to create CSV format from scratch
- ✅ **Search Functionality**: Quickly find campaigns by name or ID
- ✅ **Clear Feedback**: Detailed success/error messages

### Technical

- ✅ **Access Control**: Restricted to Managers group only
- ✅ **Transaction Safety**: Database integrity maintained
- ✅ **Flexible CSV Format**: Multiple column name variations accepted
- ✅ **Automatic Detection**: Handles different CSV delimiters
- ✅ **Breadcrumbs Navigation**: Consistent with application patterns
- ✅ **Reusable Utilities**: Uses existing `detect_csv_delimiter()` function

## Security Considerations

### Access Control

- **Group-based restriction**: Only "Managers" group members
- **No bypass**: `UserPassesTestMixin` enforces permission check
- **Clear separation**: Regular users cannot access this feature

### Data Safety

- **Transaction wrapping**: Prevents partial deletions
- **Validation**: CSV file type checking
- **Warning messages**: Clear alerts about permanent deletion
- **No cascade issues**: Deletes only `ContactCampaignStatus` records

## Usage Example

### Scenario: Clean up old campaign

A manager needs to remove 500 contacts from a completed campaign.

**Steps:**

1. Export contact IDs from database or reporting tool
2. Format as CSV with `contact_id` column
3. Navigate to Campaign Management → Bulk Delete Campaign Status
4. Upload CSV file
5. Search and select the campaign
6. Click "Delete Campaign Status Records"
7. Review success message confirming 500 deletions

**Result:** All 500 `ContactCampaignStatus` records removed in one operation.

## Testing Recommendations

### Functional Testing

1. **Access Control**
   - Verify non-managers cannot access the view
   - Confirm managers can access successfully

2. **CSV Upload**
   - Test with different column names (contact_id, id, etc.)
   - Test with comma and semicolon delimiters
   - Test with invalid file types (should reject)

3. **Campaign Selection**
   - Verify search functionality works
   - Confirm only active campaigns shown
   - Test dropdown styling and responsiveness

4. **Deletion Process**
   - Upload valid CSV with existing contact IDs
   - Verify correct number of records deleted
   - Confirm success message accuracy

5. **Template Download**
   - Download template and verify format
   - Ensure example data is helpful

### Edge Cases

1. **Empty CSV**: Should show warning about no valid IDs
2. **Invalid Column Names**: Should show warning about expected columns
3. **Non-existent Contact IDs**: Should complete without error (no records to delete)
4. **Large Files**: Test with 1000+ contact IDs
5. **Special Characters**: Test with various CSV encodings

## Related Features

This feature complements existing campaign management tools:

- **Assign Campaigns** (`assign_campaigns`): Add contacts to campaigns
- **Assign to Sellers** (`assign_to_seller`): Distribute campaign contacts
- **Campaign Statistics** (`campaign_statistics_list`): View campaign performance
- **Release Seller Contacts** (`release_seller_contacts`): Remove seller assignments

## Migration Notes

No database migrations required. This feature works with existing `ContactCampaignStatus` model and tables.

## Future Enhancements

Potential improvements for future iterations:

1. **Preview Mode**: Show which records will be deleted before executing
2. **Dry Run**: Test CSV without actually deleting
3. **Export Results**: Download list of deleted contact IDs
4. **Undo Functionality**: Restore recently deleted records
5. **Batch Processing**: Handle very large files in chunks
6. **Email Confirmation**: Send summary email after bulk deletion

## Documentation

### URL Pattern

```text
/bulk_delete_campaign_status/
```

### View Name

```python
'bulk_delete_campaign_status'
```

### Template Location

```text
support/templates/campaign_management/bulk_delete_campaign_status.html
```

### Form Class

```python
support.forms.BulkDeleteCampaignStatusForm
```

## Conclusion

This feature provides managers with a powerful, safe tool for bulk campaign cleanup operations. The combination of access control, transaction safety, and user-friendly interface makes it an essential addition to the campaign management toolkit.
