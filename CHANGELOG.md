# Changelog

## v0.5.1

## 2026-04-29 — t1132 Seller attendance tracking for call center staff

- New `Shift`, `AbsenceReason`, `AttendanceRecord`, and `SellerAttendance` models allow daily attendance and absence tracking for call center sellers
- Two new boolean fields on `Seller`: `call_center` marks who is subject to attendance tracking; `shift` (FK) links to a configurable `Shift` with start and end times editable from the admin
- A new "Seller Attendance" view under Campaign Management lets managers consult daily attendance and admins/superusers record it; statuses are Present or Absent, with a required justified/unjustified reason for absences
- `BreadcrumbsMixin` in `core/mixins.py` now has full docstring explaining usage and the `@cached_property` / plain-method / `get_context_data` interaction
- Migrations required; load `support/fixtures/shifts.json` after migrating to seed the two default shifts (Matutino 09:00–17:00, Vespertino 17:00–21:00)
- **Author:** Tanya Tree + Claude Sonnet 4.6

## v0.5.0 (2026-04-29)

## 2026-04-24 — t1126 SalesRecord creation for product change, additional product, and retention flows

- Product change, additional product, and retention discount views now always create a `SalesRecord` (type PARTIAL) so sales appear in the manager sales filter — they were previously invisible there
- In the ladiaria `edit_subscription` view, multiple products added in one session now produce a single PARTIAL `SalesRecord` instead of one per product
- The validate-sale form (`can_be_commissioned` checkbox) now defaults to checked for all sale types; an explanatory note was added so managers understand the commission implications
- Fixed an `AttributeError` bug: `SalesRecord.TYPES.PARTIAL` corrected to `SalesRecord.SALE_TYPE.PARTIAL` in `book_additional_product`
- No migrations required
- **Author:** Tanya Tree + Claude Sonnet 4.6

## 2026-04-08 — t0243 Canceled invoices report view in invoicing app

- A new `CanceledInvoicesReportView` is available in the base CRM, replacing the function view that previously existed only in the ladiaria customisation layer
- Access is restricted to the Admins group, the Finances group, and superusers
- A date-range form renders a CSV download of canceled invoices with prefetched line items and credit notes to avoid slow queries on large datasets
- All column headers are marked for translation
- No migrations required
- **Author:** Tanya Tree + Claude Sonnet 4.6

## 2026-04-07 — t1093 added_products field on Subscription

- Added `added_products` M2M field to `Subscription` (mirrors `unsubscription_products` on the departing subscription)
- Extended `add_product()` with an optional `track_as_added=False` parameter; when `True`, the product is also recorded in `added_products`
- `book_additional_product()` and `product_change()` in `support/views/subscriptions.py` now pass `track_as_added=True` for genuinely new products (copied products are unaffected)
- **Migration:** `0118_subscription_added_products`
- **Author:** Tanya Tree + Claude Sonnet 4.6

## 2026-04-06 — t1091 Campaign status edit for managers and admins

- Managers, Admins, and superusers can now edit the campaign status (status, resolution, and resolution reason) of a contact directly from the contact detail page
- A dedicated edit view shows the campaign info read-only alongside a small form restricted to the editable fields
- Non-authorised staff see the campaigns tab as before — no change to their experience
- No migrations required
- **Author:** Tanya Tree + Claude Sonnet 4.6

## 2026-04-06 — t1088 Campaign statistics: count sold products only

- Campaign statistics detail view now counts only products registered as sold via SalesRecord, not all products currently on the subscription linked to the campaign
- CSV export of campaign statistics fixed with the same approach, accumulating products across multiple sale records per contact when present
- No migrations required
- **Author:** Tanya Tree + Claude Sonnet 4.6

## 2026-04-01 - t1082 Bugfix

- Reactivate subscription was not marking it as active
- No migration required

## 2026-03-31 — t1081 Invoice detail view UX improvements

- Improved layout and readability of the invoice detail view
- No migrations required

## 2026-03-26 — t1071 Campaign statistics rate redefinitions

- Redefined campaign statistics rates and centralised contacted statuses logic
- No migrations required

## 2026-03-25 — t1069 Open issues panel in seller console + safe message fixes

- Added open issues summary panel to the seller console
- Fixed safe message rendering issues
- No migrations required

## 2026-03-24 — t1065 Email bounce warnings

- Added email bounce warnings to contact views and forms
- No migrations required

## 2026-03-23 — t1063 Do-not-call warnings

- Added do-not-call warnings to phone fields across views
- No migrations required

## 2026-03-23 — t1062 Subscription reactivation improvements

- Fixed billing date shift on reactivation; added payment method editing
- No migrations required

## 2026-03-20 — t1060 Contact detail overview UX and performance

- Redesigned overview tab with compact layout and expand/collapse functionality
- Optimized contact detail view queries
- No migrations required

## 2026-03-10 — t1052 Campaign statistics CSV export

- Added CSV export to the campaign statistics detail view with optimized queries
- No migrations required

## 2026-03-06 — Issue confirmation messages

- Added confirmation dialogs to issue state-change actions
- No migrations required

## 2026-03-05 — t1047 Issue detail view UX refinements

- Follow-up UX improvements to the issue detail view redesign
- No migrations required

## 2026-03-04 — t1044 Issue detail view redesign + date_modified field

- Redesigned issue detail view with compact layout
- Added `date_modified` field to the Issue model
- Migrations required

## 2026-03-02 — Seller console scheduled activity fixes

- Fixed scheduled activity display and date filtering in the seller activities page
- No migrations required

## 2026-02-27 — Seller console "Not found" button

- Added "Not found" action to the seller console with visual indicators
- No migrations required

## 2026-02-23 — t1034 Community manager dashboard and assignment

- Added community manager dashboard with issue assignment and team overview
- Improved issue assignment with status handling and optimized saves
- No migrations required

## 2026-02-10 — t1030 Community management console

- Added community management console with permission-based access and temporal issue grouping
- Migrations required

## 2026-02-06 — t1026 Invoice filter view modernization

- Modernized invoice filter view with additional contact search fields and improved UI
- No migrations required

## 2026-01-28 — t1017 Issue resolution field integration

- Added IssueResolution model with dynamic subcategory-based filtering and admin interface
- Migrations required

## 2026-01-26 — Subscription route change with special route automation

- Added individual subscription route change system with automatic issue creation for special routes
- Migrations required

## 2026-01-21 — Issue next action date automation and filtering

- Added automatic next_action_date setting on status change
- Added advanced filtering and sortable columns to issue management
- No migrations required

## 2026-01-19 — Address merge functionality

- Added side-by-side address merge with field selection
- No migrations required

## 2025-12-29 — Campaign editing in sales validation

- Allowed campaign editing within the sales validation workflow
- No migrations required

## 2025-12-18 — t990 Subscription reactivation feature

- Added subscription reactivation workflow from the contact detail view
- No migrations required

## 2025-12-17 — t989 Fix contact update field clearing

- Fixed a bug where updating a contact incorrectly cleared unrelated fields
- No migrations required

## 2025-12-16 — t988 Corporate/affiliate subscriptions

- Added support for corporate and affiliate subscription types
- Migrations required

## 2025-12-16 — Sales record filter enhancements

- Improved filtering options in the sales record view
- No migrations required

## 2025-12-11 — Campaign resolution tracking

- Added resolution tracking to campaign outcomes
- No migrations required

## 2025-12-08 — Campaign statistics filterview enhancement

- Improved filtering and display in the campaign statistics view
- No migrations required

## 2025-12-04 — Retention discount product addition

- Extended retention discounts to support adding products
- No migrations required

## 2025-12-01 — Retention discount management

- Added retention discount management to the subscription workflow
- Migrations required

## 2025-11-28 — Invoice expiration date logic correction

- Fixed incorrect expiration date calculation for invoices
- No migrations required

## 2025-11-27 — Never-paid issues dedicated page

- Added a dedicated page for contacts with unpaid issues
- No migrations required

## 2025-11-26 — Sales record breadcrumbs and template blocks

- Improved breadcrumb navigation and template block structure in sales record views
- No migrations required

## 2025-11-14 — Bulk delete campaign status

- Added bulk delete for campaign status records
- No migrations required

## 2025-11-13 — Phone matching plus symbol flexibility

- Phone number matching now handles leading `+` symbols correctly
- No migrations required

## 2025-11-12 — Free subscription management

- Added management interface for free subscriptions
- No migrations required

## 2025-11-10 — Contact list CSV export, UI enhancements, issue forms modernization

- Added CSV export to the contact list with optimized queries
- Modernized issue forms UI
- Added email uniqueness validation in promo forms
- Contact list UI enhancements
- No migrations required

## 2025-11-06 — Phone number checking functionality

- Added phone number format checking across contact forms
- No migrations required

## 2025-11-05 — Fix seller preservation in subscription products

- Fixed a bug where seller assignment was lost when modifying subscription products
- No migrations required

## 2025-11-04 — Choices modernization + populate SubscriptionProduct original_datetime

- Modernized Django choices usage across models
- Added management command to backfill `original_datetime` on SubscriptionProduct records
- No migrations required

## 2025-10-31 — Contact detail UI improvements + import contacts enhancements

- Multiple UI improvements to the contact detail view
- Email protection added to import contacts flow
- Updated promo view and subscription UI
- No migrations required

## 2025-10-30 — Product model and subscription form fixes

- Fixed various issues in the product model and subscription form
- No migrations required

## 2025-10-29 — Subscription form UI improvements

- UI polish and usability improvements to the subscription form
- No migrations required

## 2025-10-28 — Import contacts enhancements

- Improved import contacts functionality and documentation
- No migrations required

## 2025-10-21 — Modernize views, optimize performance, seller console UI

- Modernized several views and improved query performance
- UI improvements to the seller console and templates
- No migrations required

## 2025-10-16 — Fix test failures (history and import)

- Fixed failing tests related to contact history and import functionality
- No migrations required

---

## version 0.4.7 (2023-12-31)

- Email validation using a better python module.
- Migration fixes.
- Import contacts fixes.
- Address management fixes.
- Many other minor fixes and improvements.

## version 0.4.6 (2023-10-17)

- First "tagged" release, this "first" version number was set to the same version number that Utopia-CMS will release today, we will use this convention to know better the compatibility of both systems (api calls, custom sync scripts, etc).
- The most important change in this commit is the settings improvements, removing unnecessary settings, adding others that are used in code without specifing a default value, and updating samples files accordingly.
