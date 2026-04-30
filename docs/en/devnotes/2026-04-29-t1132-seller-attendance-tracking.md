# Seller Attendance Tracking for Call Center Staff

- **Date:** 2026-04-29
- **Author:** Tanya Tree + Claude Sonnet 4.6
- **Ticket:** t1132
- **Type:** Feature
- **Component:** Support — Sellers, Campaign Management
- **Impact:** Operator Workflow, HR Tracking, Future Commission Calculations

## 🎯 Summary

Call center managers needed a way to record daily attendance and absences for sellers who work in the call center, in order to feed future statistics and adjust each seller's count of billable working days (justified absences reduce the expected target). This ticket introduces four new models (`Shift`, `AbsenceReason`, `AttendanceRecord`, `SellerAttendance`), two new fields on `Seller`, a dedicated view accessible from the Campaign Management sidebar, and a full unit test suite. It also adds comprehensive documentation to `BreadcrumbsMixin` to clarify a subtle interaction between `@cached_property`, plain methods, and Django's template callable resolution.

## ✨ Changes

### 1. `Shift` model and new fields on `Seller`

**File:** `support/models.py`

A new `Shift` model stores named work shifts with configurable start and end times, editable from the Django admin without a code deploy. Two default shifts are seeded via fixture: Matutino (09:00–17:00) and Vespertino (17:00–21:00).

Two fields were added to `Seller`:

- `call_center` (`BooleanField`, default `False`) — flags sellers subject to attendance tracking.
- `shift` (`ForeignKey` to `Shift`, nullable) — the seller's assigned shift; used to pre-fill time inputs in the attendance view.

### 2. `AbsenceReason`, `AttendanceRecord`, and `SellerAttendance` models

**File:** `support/models.py`

`AbsenceReason` stores configurable absence categories. Each reason is marked as justified or unjustified (this distinction will drive future commission logic). Its `__str__` appends the justification label in parentheses so operators always see it at a glance. The FK from `SellerAttendance` to `AbsenceReason` uses `on_delete=PROTECT`, preventing deletion of a reason that has records attached — the admin surfaces the error automatically.

`AttendanceRecord` is a header keyed by date (`unique=True`). `SellerAttendance` stores one row per seller per day (`unique_together`) with status (Present / Absent), an optional absence reason, and the actual shift start/end times (which can differ from the assigned shift defaults).

### 3. Admin registrations and `SellerAdmin` improvements

**File:** `support/admin.py`

All four new models are registered following the existing `@admin.register` pattern. `SellerAdmin` was enhanced with `list_filter` on `internal`, `call_center`, and `shift`; `search_fields` on name and username; and `call_center` and `shift` added to `list_display`.

### 4. `SellerAttendanceView`

**File:** `support/views/all_views.py`

A class-based view (`LoginRequiredMixin + UserPassesTestMixin + BreadcrumbsMixin + TemplateView`) at `/seller_attendance/`.

- **GET:** reads a `date` query param (defaults to today), loads all `call_center=True` sellers, fetches any existing `AttendanceRecord` for that date, and builds a row per seller pre-filled with saved state or shift defaults.
- **POST:** restricted to superusers and users with the `support.change_sellerattendance` permission. Rows where status is left blank are skipped (operators may fill attendance incrementally throughout the day). Validates that absent rows have a reason and that all saved rows have shift times. Uses `update_or_create` on `SellerAttendance` so repeated saves on the same date are safe.

Sellers without a shift assigned show an inline warning badge and cannot be saved until the shift is configured in the admin.

The view calls `self.get_context_data()` (which runs the `BreadcrumbsMixin` injection) and merges view-specific keys into it, making breadcrumbs work correctly even though `get` and `post` use `render()` directly instead of delegating to `TemplateView.get`.

### 5. `seller_attendance.html` template

**File:** `support/templates/support/seller_attendance.html`

AdminLTE card with an HTML5 `<input type="date">` date selector that triggers a GET on change. The attendance table columns are: Seller, Status (select), Absence Reason (select, enabled only when Absent is chosen), Shift Start (time input), Shift End (time input). Shift inputs are hidden via inline `display:none` when status is blank.

JavaScript in `{% block extra_js %}` wires up the status selects on load and on change, and performs client-side validation before submit (missing shift times, absent without reason) to give immediate feedback without a round-trip.

Messages are rendered exclusively by the base template's `{% block messages %}` — no duplicate block in this template.

### 6. Sidebar menu entry

**File:** `templates/components/sidebar_items/_campaign_management.html`

"Seller Attendance" added before the `{% include_if_exists %}` hook, following the existing `{% url ... as ... %}` pattern for active-link detection.

### 7. Fixture and URL

**Files:** `support/fixtures/shifts.json`, `support/urls.py`

The two default shifts are provided as a fixture loadable with `manage.py loaddata`. The URL `seller_attendance/` is registered under the `support` app with name `seller_attendance`.

### 8. Unit tests

**File:** `tests/test_seller_attendance.py`

14 tests covering: `AbsenceReason.__str__` (justified/unjustified labels), `AttendanceRecord` date uniqueness, `PROTECT` deletion prevention, GET with and without prior data, call-center-only filter, POST present/absent happy paths, POST validation failures (absent without reason, missing shift times, non-admin POST → 403, no active reasons), and upsert safety.

### 9. `BreadcrumbsMixin` documentation

**File:** `core/mixins.py`

A full docstring was added explaining: how to define breadcrumbs in a subclass, why `@cached_property` vs a plain method both work (Django templates call callables automatically), and the explicit pattern needed when `get`/`post` bypass `get_context_data`.

## 📁 Files Modified

- **`support/models.py`** — Added `Shift` model; added `call_center` and `shift` fields to `Seller`; added `AbsenceReason`, `AttendanceRecord`, `SellerAttendance` models with constants
- **`support/admin.py`** — Improved `SellerAdmin`; registered `Shift`, `AbsenceReason`, `AttendanceRecord`, `SellerAttendance`
- **`support/views/all_views.py`** — Added `SellerAttendanceView` and its model imports
- **`support/urls.py`** — Registered `seller_attendance/` URL and imported `SellerAttendanceView`
- **`templates/components/sidebar_items/_campaign_management.html`** — Added "Seller Attendance" menu item
- **`core/mixins.py`** — Added full docstring to `BreadcrumbsMixin`
- **`templates/components/_footer.html`** — Version bumped to 0.5.1
- **`locale/es/LC_MESSAGES/django.po`** — New strings extracted and compiled

## 📁 Files Created

- **`support/migrations/0040_absencereason_attendancerecord_shift_and_more.py`** — Migration for all new models and fields
- **`support/fixtures/shifts.json`** — Default shifts: Matutino and Vespertino
- **`support/templates/support/seller_attendance.html`** — Attendance view template
- **`tests/test_seller_attendance.py`** — 14 unit tests

## 📚 Technical Details

- `SellerAttendance.absence_reason` uses `on_delete=PROTECT`. Attempting to delete an `AbsenceReason` that has attendance rows linked raises a Django `ProtectedError`, which the admin displays as a user-friendly error. No custom logic required.
- The permission check in `post` uses `request.user.is_superuser or request.user.has_perm("support.change_sellerattendance")`. Staff-only users (who pass `test_func`) can GET but not POST, giving read-only access to managers without granting edit rights.
- Shift times in `SellerAttendance` are stored independently of `Seller.shift` — the shift FK only provides defaults. Operators can adjust actual times per day (e.g. a seller arrived late), and those times are what gets persisted.
- The `get_or_create` return value's second element (`created`) was named `_created` to avoid shadowing the `_` alias for `gettext_lazy`, which would cause an `UnboundLocalError` when Python's bytecode compiler detects the local assignment.

## 🧪 Manual Testing

1. **Happy path — record attendance for a present seller:**
   - Mark a `Seller` as `call_center=True` and assign a `Shift` in the admin.
   - Create at least one active `AbsenceReason`.
   - Navigate to `/seller_attendance/` as a superuser.
   - Select today's date; the seller appears with shift times pre-filled.
   - Set status to "Present" and click "Save attendance".
   - **Verify:** Page redirects back, success message appears once (top of page only), and reloading the same date shows "Present" pre-selected.

2. **Happy path — record an absence with a reason:**
   - Set the seller's status to "Absent"; the absence reason select becomes enabled.
   - Choose a reason and save.
   - **Verify:** `SellerAttendance` row exists with `status="A"` and the correct `absence_reason`.

3. **Happy path — manager (staff, non-superuser) can only view:**
   - Log in as a staff user without `change_sellerattendance` permission.
   - Navigate to `/seller_attendance/`.
   - **Verify:** Page loads (200), status and shift fields are read-only, no "Save attendance" button is shown.

4. **Edge case — absent without reason is rejected:**
   - Select "Absent" but leave the reason blank and submit.
   - **Verify:** The form re-renders with an error message; no `SellerAttendance` row is created.

5. **Edge case — seller without shift shows warning:**
   - Set a seller's `shift` to null in the admin.
   - Load the attendance view.
   - **Verify:** The seller row shows a yellow "No shift" badge; inputs for that row are disabled.

6. **Edge case — saving twice on the same date updates, does not duplicate:**
   - Save attendance for a date marking a seller as Present.
   - Return to the same date, change the seller to Absent with a reason, and save again.
   - **Verify:** `SellerAttendance.objects.filter(seller=seller, record__date=date).count()` is 1 and `status="A"`.

7. **Edge case — deleting an absence reason in use is blocked:**
   - In the admin, attempt to delete an `AbsenceReason` that has linked `SellerAttendance` rows.
   - **Verify:** Django displays a "Cannot delete" error listing the protected objects.

## 📝 Deployment Notes

- **Migration required:** `support/0040_absencereason_attendancerecord_shift_and_more`
- After migrating, load the default shifts:

  ```bash
  python manage.py loaddata support/fixtures/shifts.json
  ```

- After loading, go to the admin and mark the relevant `Seller` records with `call_center=True` and assign a `Shift`.
- Create at least one `AbsenceReason` before operators start using the view — the view blocks saving if none exist.
- No new settings required.

## 🎓 Design Decisions

`Shift` was implemented as a model (rather than hardcoded constants or settings) so that administrators can adjust shift hours without a code deploy. Two default shifts are seeded via fixture; adding more is done through the admin.

The header/detail split (`AttendanceRecord` + `SellerAttendance`) keeps the date unique at the record level and makes it easy to query "all absences for a given date" or "all absences for a given seller" efficiently, and sets the foundation for future aggregate statistics.

Blank status rows are silently skipped on save rather than raising a validation error, because operators may enter the tool multiple times during a day (e.g. morning supervisor fills in early arrivals, afternoon supervisor completes the rest). Forcing all rows to be filled before saving would make incremental use impossible.

## 🚀 Future Improvements

- Add date-range absence reports per seller (total absences, justified vs unjustified breakdown) for use in commission and performance calculations.
- Expose a bulk-import flow (CSV) for retroactive absence data entry.
- Use justified absences to automatically reduce each seller's target working-day count in the performance statistics view.

---

**Date:** 2026-04-29
**Author:** Tanya Tree + Claude Sonnet 4.6
**Branch:** t1132
**Type:** Feature
**Modules affected:** Support, Core
