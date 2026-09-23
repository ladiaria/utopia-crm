# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

`utopia-crm` is the open-source base Django CRM app: contacts, subscriptions, billing, logistics and
call-center support. It contains `manage.py`, all settings files and the core Django apps.

It is designed to be **extended without being modified**. A deployment typically installs a private
customization package into the same virtualenv in developer mode (`pip install -e`) and registers it
from `local_settings.py`. See [Extension patterns](#extension-patterns) below — when a behaviour
looks missing or hardcoded, the answer is usually a hook rather than a patch to this repo.

## Common commands

```bash
# Development server
python manage.py runserver

# Run a single test module
python -W ignore manage.py test --settings=test_settings --keepdb tests.test_contact

# Migrations — use migration_settings so local_settings does not bleed into generated migrations
python manage.py makemigrations --settings=migration_settings [app]
python manage.py migrate

# System check (no --settings needed; local_settings is loaded automatically)
python manage.py check
```

## Settings hierarchy

Settings are layered:

| File | Purpose |
| --- | --- |
| `settings.py` | Base settings for all environments |
| `local_settings.py` | Local/dev/production overrides (not committed) — also registers the customization package in `INSTALLED_APPS` and sets `URLS_CUSTOM_MODULE` |
| `local_migration_settings.py` | Optional overrides for clean migration generation |
| `migration_settings.py` | Minimal settings for `makemigrations` — imports base then `local_migration_settings` only |
| `test_settings.py` | Imports `settings` + `local_settings`, overrides `ALLOWED_HOSTS` and language; imports `local_test_settings` if present |
| `ci_test_settings.py` | CI-only test settings |

`local_settings.py` is gitignored: never stage or commit it.

**Why `migration_settings` exists:** running `makemigrations` with `local_settings` loaded produces
migrations contaminated with local configuration. Always pass `--settings=migration_settings`.

## Django apps

- **`core`** — the heart of the CRM: contacts, subscriptions, products, campaigns, pricing rules,
  discounts, email replacements. Also contains DRF serializers/router, Mailtrain integration
  utilities, and web-user sync logic (`updatewebuser`, signals).
- **`invoicing`** — billing cycles and invoice generation, including MercadoPago data.
- **`support`** — support issues, scheduled tasks, sellers, and sales records.
- **`logistics`** — delivery route management.
- **`community`** — community-related models.
- **`advertisement`** — advertising management.

## Extension patterns

The base app is designed to be extended without modification:

- **Custom URLs**: set `URLS_CUSTOM_MODULE` (e.g. `'mypackage.urls'`) in `local_settings.py`. This
  makes `urls.py` prepend the custom URL patterns before the base ones, which allows overriding any
  base URL.
- **Custom validation**: set `WEB_UPDATE_USER_VALIDATION_MODULE` to a module with validation
  functions.
- **Custom active-check callbacks**: `CORE_DEFAULT_NEWSLETTERS` maps dotted-path callables to
  newsletter slugs.
- **Feature flags**: many behaviours are toggled via settings (e.g. `WEB_UPDATE_USER_ENABLED`,
  `EFACTURA_ENABLED`, `MERCADOPAGO_ENABLED`, `REQUIRE_ROUTE_FOR_BILLING`).

A customization package is **not** in the base `INSTALLED_APPS`; it is added by `local_settings.py`.
So if you search this repo for where a custom app is installed and find nothing, that is expected —
it is configured outside the repo.

## Tests

- Tests live in `tests/` and are prefixed `test_`.
- Always run with `-W ignore`, `--settings=test_settings` and `--keepdb`.
- Some tests may be tagged `broken`; exclude them with `--exclude-tag broken`.
- Tests that are transactional must be run in isolation.

### Fixtures first

**Prefer existing fixtures over building objects by hand in `setUpTestData`.** Hand-rolled objects
drift from the real catalogue: they get the slugs, prices, priorities and FKs that the test author
guessed, not the ones production actually has, so a test can pass against a fantasy and still break
in production. Declare them on the test class:

```python
fixtures = ["core_product", "core_productbundle", "core_pricerule", "logistics_route"]
```

**The only reason to build objects by hand** is when the test needs data that must *not* behave like
production — an edge case that doesn't exist in the catalogue, a deliberately malformed row, a
product with a price chosen to make an assertion readable. That is a real exception, not an excuse:
if fixture data would do, use the fixture.

Fixtures shipped with this repo live in `fixtures/`: `default_groups`, `email_replacements`.

## UI / frontend

The interface is built on **AdminLTE** with **Bootstrap**. When writing or modifying templates:

- Follow AdminLTE conventions: use its built-in components (cards/boxes, alerts, navbars, sidebars,
  data tables, form layouts) rather than rolling custom equivalents.
- Use Bootstrap utility classes and the grid system consistently — avoid inline styles.
- Keep forms and tables within AdminLTE's `box`/`card` wrappers.
- Prefer AdminLTE's color and icon conventions (`text-primary`, `bg-warning`, Font Awesome icons).
- New pages should feel visually consistent with the rest of the CRM, not like a separate design.
- **Always check `static/admin-lte/plugins/` first** before adding any new JS dependency — run
  `ls static/admin-lte/plugins/` to see what is already bundled.
- **Datepickers**: prefer HTML5 `<input type="date/datetime-local">`. If a richer picker is needed,
  use `tempusdominus-bootstrap-4` (already bundled). A CDN or a new package is a last resort.

### AdminLTE template block order

jQuery loads at the end of `<body>` via `{% block javascript %}` in `templates/adminlte/base.html`.
Block order:

1. `{% block stylesheets %}` — in `<head>`. CSS and `<link>` tags only. **Never put JavaScript
   here** — `$` is not defined yet.
2. `{% block javascript %}` — loads jQuery + AdminLTE libs. Do not override.
3. `{% block extra_js %}` — **all custom JavaScript goes here**.
4. `{% block extra_foot %}` — general use after scripts.

**Breadcrumbs**: use `BreadcrumbsMixin` in class-based views and pass the context directly in
function-based views. Never override the breadcrumbs block in the template.

## Code style

- **Black** formatting for all Python.
- **Line length: 120 characters** (Black and flake8).
- **flake8** linter; follow PEP8 as enforced by it.
- **djlint** for Django HTML templates.

## Known gotchas

### Subscription payment method field

In `Subscription`, the only payment method field in use is `payment_type` — a `CharField` with
choices from `settings.SUBSCRIPTION_PAYMENT_METHODS` (e.g. `"O"`, `"D"`, `"S"`). The FK fields
`payment_method_fk` and `payment_type_fk` exist in the model but are **not wired up** in billing,
filters or forms. Always use `subscription.payment_type`.

### Bulk contact updates

Never call `save()` per row when updating many `Contact` objects: each save triggers the web-user
sync described below. Use `email__in` plus `bulk_update` instead — on real data this is the
difference between minutes and under a second.

## Key integrations configured via settings

- **Web system sync** (`utopia-cms` / ldsocial): subscriber sync over HTTP, configured with
  `LDSOCIAL_URL` and the `WEB_UPDATE_*` settings. Setting `LDSOCIAL_URL` is enough — the individual
  endpoint URIs are derived from it.
- **GeoDjango**: PostGIS is required, along with GDAL/GEOS. On macOS, set `GDAL_LIBRARY_PATH` and
  `GEOS_LIBRARY_PATH` in `local_settings.py`.
