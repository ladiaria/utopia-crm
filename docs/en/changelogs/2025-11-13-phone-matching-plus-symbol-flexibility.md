# Phone Matching Plus Symbol Flexibility

**Date:** 2025-11-13
**Ticket:** t964
**Type:** Bug Fix / Enhancement
**Component:** Contact Check UI
**Impact:** Operator Experience

## Summary

Enhanced the phone number matching logic in `CheckForExistingContactsView` to work seamlessly with or without the `+` symbol. This resolves issues where CSV files exported from certain editors (especially Excel) lose the `+` prefix, preventing successful phone number matching.

## Problem

When operators export CSV files containing phone numbers with the international `+` prefix (e.g., `+59812345678`), some text editors and spreadsheet applications automatically strip the `+` symbol when saving the file. This caused phone number matching to fail because:

1. The database stores phone numbers with `+` prefix (e.g., `+59812345678`)
2. The CSV file contains numbers without `+` prefix (e.g., `59812345678`)
3. The previous matching logic required exact format consistency

This was particularly problematic in Colombian workflows where Excel exports commonly remove the `+` symbol.

## Solution Implemented

### Normalized Phone Number Matching

Modified the `find_matching_contacts_by_phone()` method to normalize phone numbers before matching:

**Key Changes:**

1. **Strip Non-Digit Characters**: Removes all non-digit characters except `+` from input
2. **Dual Version Creation**: Creates both versions of the phone number:
   - With `+` symbol for proper `PhoneNumber` parsing
   - Without `+` symbol for digit-based matching
3. **Flexible Query**: Uses `icontains` to match on digit sequence regardless of `+` presence
4. **Graceful Fallback**: If phone parsing fails, still performs digit-based matching

### Technical Implementation

```python
# Normalize the input phone number
normalized_input = re.sub(r'[^\d+]', '', phone_number)

# Create two versions
phone_with_plus = normalized_input if normalized_input.startswith('+') else f'+{normalized_input}'
phone_without_plus = normalized_input.lstrip('+')

# Build flexible query
query = Q(phone__icontains=phone_without_plus) | Q(mobile__icontains=phone_without_plus)

# Add exact matching if parsing succeeds
if parsed_phone:
    query |= Q(phone=parsed_phone) | Q(mobile=parsed_phone)
```

## Matching Scenarios

The enhanced logic now handles all these scenarios correctly:

| CSV Input | Database Value | Result |
|-----------|---------------|--------|
| `+59812345678` | `+59812345678` | ✅ Match |
| `59812345678` | `+59812345678` | ✅ Match |
| `+59812345678` | `59812345678` | ✅ Match |
| `59812345678` | `59812345678` | ✅ Match |

## Benefits

### For Operators

- ✅ **CSV-Friendly**: Works with files from any editor, regardless of `+` symbol handling
- ✅ **No Manual Editing**: No need to manually add/remove `+` symbols before upload
- ✅ **Consistent Results**: Same matching behavior regardless of CSV source
- ✅ **Colombian Excel Compatible**: Handles Excel exports that strip `+` symbols

### Technical

- ✅ **Backward Compatible**: Still uses proper `PhoneNumber` parsing when possible
- ✅ **Robust Matching**: Falls back to digit-based matching for reliability
- ✅ **Flexible**: Matches phone numbers in any format stored in database
- ✅ **No Breaking Changes**: Existing functionality preserved

## Files Modified

- `support/views/contacts.py`: Updated `CheckForExistingContactsView.find_matching_contacts_by_phone()`

## Usage

Operators can now upload CSV files with phone numbers in any of these formats:

```csv
phone
+59812345678
59812345678
+1234567890
1234567890
```

All formats will successfully match contacts in the database, regardless of how the phone numbers are stored.

## Testing Recommendations

1. **Test with `+` symbol**: Upload CSV with `+59812345678` format
2. **Test without `+` symbol**: Upload CSV with `59812345678` format
3. **Test mixed formats**: Upload CSV with both formats in same file
4. **Test Excel exports**: Export from Excel and verify matching still works

## Related Changes

This enhancement builds on the phone checking functionality introduced in:

- **t955** (2025-11-06): Initial phone number checking feature

## Migration Notes

No database migrations required. This is a pure logic enhancement that works with existing data.
