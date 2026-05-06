# Campaign Status Edit for Managers and Admins

- **Date:** 2026-04-06
- **Author:** Tanya Tree + Claude Sonnet 4.6
- **Ticket:** t1091
- **Type:** Feature
- **Component:** Support, Campaign Management, Contact Detail
- **Impact:** User Experience, Access Control

## 🎯 Summary

Managers, Admins, and superusers can now edit the `ContactCampaignStatus` (CCS) record of a contact directly from the contact detail page, without going through the Django admin. A small dedicated view exposes only the three editable fields — status, campaign resolution, and resolution reason — while displaying the rest of the campaign info read-only. Regular staff (sellers, support) see no change. Access is controlled both in the view (hard redirect on unauthorised access) and in the template (the button is hidden for non-authorised users).

## ✨ Changes

### 1. Permission helper and edit view

**File:** `support/views/contacts.py`

A standalone helper function `user_can_edit_campaign_status()` centralises the permission check, keeping the logic in one place:

```python
def user_can_edit_campaign_status(user):
    return user.is_active and (
        user.is_superuser or user.groups.filter(name__in=["Managers", "Admin"]).exists()
    )
```

`ContactCampaignStatusEditView` is an `UpdateView` that:

- Calls the helper in `dispatch()` and redirects unauthorised users back to the contact detail page with an error message.
- Shows campaign info (contact name, seller, dates) read-only in the template header.
- Saves only the `status`, `campaign_resolution`, and `resolution_reason` fields.
- Redirects to the contact detail page on success with a confirmation message.

`ContactDetailView.get_context_data()` now also sets `can_edit_campaign_status` in context so the template can show or hide the button without additional queries per campaign card:

```python
context["can_edit_campaign_status"] = user.is_superuser or user.groups.filter(
    name__in=["Managers", "Admin"]
).exists()
```

### 2. Edit form

**File:** `support/forms.py`

`ContactCampaignStatusEditForm` is a `ModelForm` restricted to the three editable fields, each rendered with a Bootstrap `form-control` widget:

```python
class ContactCampaignStatusEditForm(forms.ModelForm):
    class Meta:
        model = ContactCampaignStatus
        fields = ("status", "campaign_resolution", "resolution_reason")
```

### 3. URL registration

**File:** `support/urls.py`

A new named URL `edit_campaign_status` maps `campaign_status/<int:pk>/edit/` to the new view.

### 4. Campaign status edit template

**File:** `support/templates/contact_detail/edit_campaign_status.html`

A two-panel page following AdminLTE conventions:

- Top card: read-only summary of the CCS record (campaign name, contact, seller, dates).
- Bottom card: the edit form with Save and Cancel buttons. Cancel returns to the contact detail page.

### 5. "Edit status" button in the campaigns tab

**File:** `support/templates/contact_detail/tabs/_campaigns.html`

Each campaign card header now includes an "Edit status" button that links to `edit_campaign_status` with the CCS `pk`. The button is wrapped in `{% if can_edit_campaign_status %}` so it only renders for authorised users.

## 📁 Files Modified

- **`support/forms.py`** — Added `ContactCampaignStatusEditForm`; added `ContactCampaignStatus` to model imports
- **`support/views/contacts.py`** — Added `user_can_edit_campaign_status()` helper, `ContactCampaignStatusEditView`, `can_edit_campaign_status` context in `ContactDetailView`, and updated imports (`Group`, `ContactCampaignStatusEditForm`)
- **`support/urls.py`** — Added `campaign_status/<int:pk>/edit/` URL and import of `ContactCampaignStatusEditView`
- **`support/templates/contact_detail/tabs/_campaigns.html`** — Added "Edit status" button gated by `can_edit_campaign_status` context variable

## 📁 Files Created

- **`support/templates/contact_detail/edit_campaign_status.html`** — Edit page for campaign status, showing read-only CCS info alongside the edit form

## 🧪 Manual Testing

1. **Happy path — manager edits a campaign status:**
   - Log in as a user in the "Managers" group.
   - Open any contact detail page that has at least one campaign entry in the Campaigns tab.
   - Click the "Edit status" button on a campaign card.
   - **Verify:** The edit page loads, showing the campaign name, contact, seller, and dates read-only. The status, resolution, and reason fields are editable.
   - Change the status and click Save.
   - **Verify:** You are redirected to the contact detail page and a success message is displayed. The campaign card reflects the new status badge.

2. **Access control — seller cannot reach the edit view:**
   - Log in as a user in the "Sellers" group (not in Managers or Admin, not a superuser).
   - Open any contact detail page with a campaign entry.
   - **Verify:** No "Edit status" button is visible in the campaign cards.
   - Attempt to access the edit URL directly (`/campaign_status/<pk>/edit/`).
   - **Verify:** You are redirected to the contact detail page with an error message and no change is saved.

3. **Edge case — superuser access:**
   - Log in as a superuser.
   - **Verify:** The "Edit status" button is visible on all campaign cards, and the edit view works as in the happy path.

4. **Edge case — only three fields are editable:**
   - Open the edit view as a manager.
   - **Verify:** Only `status`, `campaign_resolution`, and `resolution_reason` fields appear in the form. Seller, dates, and contact are displayed read-only in the info card, not as form inputs.

## 📝 Deployment Notes

- No database migrations required.
- No configuration changes required.
- The permission check uses group names `"Managers"` and `"Admin"` — ensure these groups exist in the target environment.

## 🎓 Design Decisions

A dedicated edit view was chosen over linking directly to the Django admin for two reasons: it fits the existing CRM UI (AdminLTE cards, breadcrumbs, messages), and it allows restricting the editable fields to only those that make sense to change manually (`status`, `campaign_resolution`, `resolution_reason`). The admin would expose all fields, including `seller`, `date_assigned`, `times_contacted`, and `last_console_action`, which should not be edited by hand.

The permission check is duplicated intentionally between `ContactDetailView` (for the template button) and `ContactCampaignStatusEditView.dispatch()` (for the URL guard). The template check avoids rendering the button for non-authorised users; the view check ensures the URL cannot be accessed directly. Both use the same `user_can_edit_campaign_status()` helper to stay in sync.

## 🚀 Future Improvements

- Add an audit trail (activity log entry) when a manager manually overrides a campaign status.
- Consider adding inline HTMX editing directly in the campaign card to avoid a full page navigation.

---

- **Date:** 2026-04-06
- **Author:** Tanya Tree + Claude Sonnet 4.6
- **Branch:** t1091
- **Type:** Feature
- **Modules affected:** Support, Campaign Management, Contact Detail
