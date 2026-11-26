# Class-based views that checked nothing

- **Date:** 2026-11-25
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#185
- **Type:** Bug Fix
- **Component:** Support, Core API
- **Impact:** Security, Permissions

## 🎯 Summary

The access review of it/utopia-crm-ladiaria#183 covered the routed function views. This change finishes it with the
class-based ones: every routed view was walked looking for class-based views with no access mixin nor decorator, and
for DRF views with no `permission_classes`. The base does not set `REST_FRAMEWORK`, so DRF's default is `AllowAny`.

Four views and one API endpoint checked nothing. They now ask for what their buttons already asked for.

## ✨ Changes

### 1. Free subscriptions

**File:** `support/views/subscriptions.py`

`FreeSubscriptionMixin` defined a `test_func` asking for `core.can_add_free_subscription`, but neither
`CreateFreeSubscriptionView` nor `UpdateFreeSubscriptionView` inherited `UserPassesTestMixin`, so nothing ever called
it. Anyone with the link could open both views, logged in or not. The mixin now inherits `UserPassesTestMixin`, so
the existing `test_func` runs.

The «Create free subscription» button already checked `perms.core.can_add_free_subscription`, so nobody who sees it
loses access. The «Update free subscription» buttons of the contact page (the subscription card and the overview
list) checked the Managers group instead: they now check the same permission, so a Manager without it no longer sees
a button that would answer 403.

### 2. Corporate subscription and subscription update

**File:** `support/views/subscriptions.py`

- `CorporateSubscriptionCreateView` asks for `core.can_add_corporate_subscription`, the same permission as its button.
- `SubscriptionUpdateView` asks for staff, the same as `SubscriptionCreateView`.

A customization package may override these URLs with its own views (`URLS_CUSTOM_MODULE`), but the base views must
be safe for any deployment that uses them as they are.

### 3. API log entry endpoint

**File:** `core/serializers.py`

`ApiLogEntryViewSet` took POSTs without an API key and wrote an `ApiLogEntry` row. It now has
`permission_classes = [HasAPIKey]`, the same as the other base APIs called by other systems.

`document-types` stays open on purpose: it is a read-only catalogue of ID document types.

## 📁 Files Modified

- **`support/views/subscriptions.py`**: `UserPassesTestMixin` on `FreeSubscriptionMixin`, and `test_func` on the
  corporate and update views
- **`core/serializers.py`**: `HasAPIKey` on `ApiLogEntryViewSet`
- **`support/templates/contact_detail/tabs/includes/_subscription_card.html`**,
  **`support/templates/contact_detail/tabs/includes/_overview_subscription_list_item.html`**: the «Update free
  subscription» button checks the permission
- **`tests/test_access_checks.py`**: tests for the four views and the endpoint
- **`CHANGELOG.md`**

## 🧪 Manual Testing

1. **Happy path:**
   - As a user with «Can add free subscription», open a contact and click «Create free subscription»
   - **Verify:** the form opens and the subscription is created as before
2. **Edge case:**
   - As a staff user without the permission, open `/support/contact/<id>/create-free-subscription/` by hand
   - **Verify:** 403. Logged out, the same URL sends to the login page
3. **Edge case:**
   - `POST /api/api-log-entry/` without the `Authorization: Api-Key …` header
   - **Verify:** 403, and no `ApiLogEntry` row is created

## 📝 Deployment Notes

- **No migrations required.**
- Before merging, la diaria's production logs (8 days) showed no requests to `/api/api-log-entry/`, and the only free
  subscriptions created in that time were made by a user who has the permission.

## 🎓 Design Decisions

- **The tests call the views directly**, through `RequestFactory`, instead of their URLs: `test_settings` loads
  `local_settings`, and a deployment's `URLS_CUSTOM_MODULE` can route the same URLs to its own views.
- **The views keep their own `dispatch`**, which loads the contact or subscription before `UserPassesTestMixin` runs.
  That is the pattern `SubscriptionCreateView` already followed, and that code only reads.

---

- **Date:** 2026-11-25
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl185-vistas-de-clase-sin-chequeo
- **Type:** Bug Fix
- **Modules affected:** support, core
