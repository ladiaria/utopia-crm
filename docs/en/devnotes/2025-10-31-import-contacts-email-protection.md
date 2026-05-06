# Import Contacts - Email Protection Analysis and Documentation

**Date:** 2025-10-31
**Type:** Documentation / Code Review
**Component:** ImportContactsView
**Impact:** Data Integrity

## Summary

Analyzed the `ImportContactsView` to verify that existing contact emails cannot be accidentally deleted during CSV imports. Added explicit documentation to protect against future modifications that could introduce data loss.

## Question Investigated

**Can ImportContactsView delete the email of an existing contact?**

## Answer: NO (Currently Protected)

The current implementation **does NOT delete emails** from existing contacts, but the protection is implicit. This document adds explicit safeguards and documentation.

## Current Protection Mechanisms

### 1. Email Match Scenario

When a contact is matched by email:

```python
# Line 558: Try to match by email first
matches = self.find_matching_contacts_by_email(email) if email else Contact.objects.none()

# Line 568-569: If matched by email, only phones are updated
if matches.exists():
    self.update_existing_contacts(matches, contact_data, tags, results)
```

**Result**: Only phone numbers are updated via `update_contact_phone()`. Email is never touched.

### 2. Phone Match Scenario

When a contact is matched by phone (no email match):

```python
# Line 561-566: If no email match, try phone match
if not matches.exists() and phone:
    matches = self.find_matching_contacts_by_phone(phone)
    if matches.exists():
        # Matched by phone - update email if contact doesn't have one
        self.update_existing_contacts(matches, contact_data, tags, results, matched_by_phone=True)
        return
```

Then in `update_existing_contacts`:

```python
# Line 584-590: Only add email if contact doesn't have one
if matched_by_phone and not contact.email:
    email_from_csv = contact_data.get('email')
    if email_from_csv:
        contact.email = email_from_csv
        contact.save()
        results['added_emails'] += 1
```

**Result**: Email is only **added** if the contact has no email. Existing emails are never overwritten.

### 3. No Match Scenario

When no contact is matched:

```python
# Line 571: Create new contact
self.create_new_contact(contact_data, tags, results)
```

**Result**: New contact is created with all CSV data, including email (which can be `None`).

## Potential Risks (Prevented)

### Risk 1: Empty Email in CSV

**Scenario:**

- Database contact: `phone="123456"`, `email="john@example.com"`
- CSV row: `phone="123456"`, `email=""` (empty)

**What Happens:**

1. `parse_row` converts empty email to `None` (line 539)
2. No email match (email is None)
3. Phone match found
4. `matched_by_phone=True` is set
5. Check: `if matched_by_phone and not contact.email` → **FALSE** (contact has email)
6. Only phone is updated via `update_contact_phone()`

**Result**: ✅ Email is preserved

### Risk 2: Multiple Matches

**Scenario:**

- Multiple contacts with same phone number

**What Happens:**

```python
# Line 582: Only update if exactly one match
if matches.count() == 1:
    # ... update logic
```

**Result**: ✅ No updates if multiple matches (prevents ambiguous updates)

### Risk 3: Future Code Modifications

**Risk**: Someone might modify the code to update more fields without realizing the data loss implications.

**Mitigation**: Added explicit comment on line 584:

```python
# IMPORTANT: Never overwrite existing emails to prevent data loss
```

## Database Schema Protection

The Contact model email field is defined as:

```python
email = models.EmailField(blank=True, null=True, unique=True, verbose_name=_("Email"))
```

- `blank=True`: Can be empty in forms
- `null=True`: Can be NULL in database
- `unique=True`: Prevents duplicate emails (important for matching)

This means:

- ✅ Contacts can exist without emails
- ✅ Empty CSV emails won't cause database errors
- ✅ Email uniqueness is enforced at database level

## Code Flow Summary

```text
CSV Row Processing:
├─ Parse row → email = None if empty
├─ Try email match
│  ├─ Match found → Update phones only ✅ EMAIL SAFE
│  └─ No match → Try phone match
│     ├─ Match found
│     │  ├─ Contact has email → Update phones only ✅ EMAIL SAFE
│     │  └─ Contact has no email → Add email from CSV ✅ EMAIL SAFE
│     └─ No match → Create new contact ✅ EMAIL SAFE
```

## Changes Made

### 1. Added Explicit Comment

Added comment in `update_existing_contacts` method (line 584):

```python
# IMPORTANT: Never overwrite existing emails to prevent data loss
if matched_by_phone and not contact.email:
```

This serves as a warning to future developers.

### 2. Documentation

Created this comprehensive changelog documenting:

- Current protection mechanisms
- Potential risks and how they're prevented
- Code flow analysis
- Database schema constraints

## Testing Recommendations

To verify email protection, test these scenarios:

### Test 1: Empty Email in CSV (Phone Match)

**Setup:**

- Database: Contact with `phone="123456"`, `email="test@example.com"`
- CSV: `phone="123456"`, `email=""` (empty)

**Expected Result:**

- Contact matched by phone
- Email remains `test@example.com`
- Phone may be updated/added to mobile

### Test 2: Different Email in CSV (Phone Match)

**Setup:**

- Database: Contact with `phone="123456"`, `email="old@example.com"`
- CSV: `phone="123456"`, `email="new@example.com"`

**Expected Result:**

- Contact matched by phone
- Email remains `old@example.com` (not changed to <new@example.com>)
- Phone may be updated

### Test 3: Email in CSV, No Email in Database (Phone Match)

**Setup:**

- Database: Contact with `phone="123456"`, `email=None`
- CSV: `phone="123456"`, `email="new@example.com"`

**Expected Result:**

- Contact matched by phone
- Email updated to `new@example.com`
- Success message: "1 emails were added to existing contacts"

### Test 4: Email Match

**Setup:**

- Database: Contact with `email="test@example.com"`, `phone="111111"`
- CSV: `email="test@example.com"`, `phone="222222"`

**Expected Result:**

- Contact matched by email
- Email remains `test@example.com`
- Phone updated (111111 → phone, 222222 → mobile)

## Recommendations for Future Development

### 1. Add Explicit Email Protection Flag

Consider adding a setting or flag:

```python
IMPORT_CONTACTS_ALLOW_EMAIL_OVERWRITE = False  # Default: never overwrite
```

### 2. Add Warning Messages

When CSV has different email than database:

```python
if matched_by_phone and contact.email and email_from_csv and contact.email != email_from_csv:
    messages.warning(
        self.request,
        f"Contact {contact.id} has email {contact.email} but CSV has {email_from_csv}. Email not updated."
    )
```

### 3. Add Audit Log

Log all email changes:

```python
if contact.email != email_from_csv:
    Activity.objects.create(
        contact=contact,
        activity_type="email_updated",
        notes=f"Email updated from {contact.email} to {email_from_csv} via CSV import"
    )
```

### 4. Add Unit Tests

Create comprehensive unit tests for all email scenarios:

```python
class ImportContactsEmailProtectionTestCase(TestCase):
    def test_email_not_deleted_when_csv_empty(self):
        # Test that existing emails are preserved
        pass

    def test_email_added_when_contact_has_none(self):
        # Test that emails are added when missing
        pass

    def test_email_not_overwritten_on_phone_match(self):
        # Test that different emails don't overwrite
        pass
```

## Conclusion

**Current Status**: ✅ **SAFE** - Existing contact emails cannot be deleted

**Protection Level**: Implicit (relies on conditional logic)

**Recommendation**: The added comment provides explicit documentation, but consider implementing the additional safeguards mentioned above for defense-in-depth.

## Related Code References

- **ImportContactsView.parse_row** (line 523): Converts empty emails to `None`
- **ImportContactsView.process_contact** (line 552): Matching logic
- **ImportContactsView.update_existing_contacts** (line 579): Update logic with email protection
- **ImportContactsView.update_contact_phone** (line 604): Phone-only updates
- **Contact model** (core/models.py line 450): Email field definition

## Files Modified

- `support/views/contacts.py`: Added explicit comment on line 584
- `docs/en/changelogs/2025-10-31-import-contacts-email-protection.md`: This documentation
