# Management Commands — utopia-crm

This file documents all management commands in the base `utopia-crm` repo.
It is used to track which commands are needed for automated setup (e.g. Docker entrypoint),
which run on a schedule, and which are one-shot scripts that can be archived.

## Classification legend

| Label | Meaning |
| --- | --- |
| `bootstrap` | Must run on every fresh DB creation |
| `scheduled` | Runs on a cron schedule in production |
| `on-demand` | Run manually when needed |
| `one-shot` | Was run once in production history; should be archived |
| `unknown` | Classification pending — needs review |

---

## core

| Command | Classification | Notes |
| --- | --- | --- |
| `cleanup_country_state_data` | `unknown` | Normalizes country/state ISO codes. Likely one-shot — verify if it was ever re-run or if data is already clean |
| `close_old_pending_activities_and_campaign_status` | `scheduled` | Closes expired activities and campaign statuses older than a given date |
| `disable_expired_campaigns` | `scheduled` | Disables campaigns that have passed their end date |
| `emailfix` | `on-demand` | Applies approved email replacement rules to contacts |
| `expire_old_pending_activities` | `scheduled` | Marks pending activities as expired; meant to run nightly at midnight |
| `fix_duplicate_subscriptionproducts` | `unknown` | Detects and removes duplicate SubscriptionProducts. Likely one-shot tied to a specific bug — verify |
| `populate_seller_console_actions` | `bootstrap` | Creates/updates SellerConsoleAction records from hardcoded definitions; idempotent |
| `populate_subscriptionproduct_original_date` | `one-shot` | Backfills `original_datetime` on SubscriptionProduct; traces subscription chains. Likely already done in production |
| `synchronize_contact_filters_mailtrain` | `scheduled` | Syncs active DynamicContactFilter objects with Mailtrain |

## invoicing

| Command | Classification | Notes |
| --- | --- | --- |
| `daily_billing` | `scheduled` | Bills all subscriptions due today or earlier |

## logistics

| Command | Classification | Notes |
| --- | --- | --- |
| `activate_subscriptions_by_start_date` | `scheduled` | Activates subscriptions on or one day before their start date |
| `create_deliveries` | `scheduled` | Creates delivery records for today's weekday products |
| `disable_subscriptions_by_end_date` | `scheduled` | Deactivates subscriptions that have reached their end date |

## support

| Command | Classification | Notes |
| --- | --- | --- |
| `close_invoicing_issues` | `scheduled` | Auto-closes billing collection issues |
| `detect_duplicate_seller_users` | `on-demand` | Reports users assigned to more than one seller; diagnostic only |
| `generate_invoicing_issues` | `scheduled` | Creates follow-up issues for contacts with overdue invoices |
| `run_scheduled_tasks` | `scheduled` | Executes pending ScheduledTask records due today |
| `sync_all_filters` | `scheduled` | Syncs all autosync-enabled DynamicContactFilter objects with Mailtrain |
| `sync_one_filter` | `on-demand` | Syncs a single DynamicContactFilter with Mailtrain by ID |

---

## Archive

Commands moved to `core/management/commands/archive/` (or equivalent) after being confirmed as one-shot:

_(none yet)_

---

## Bootstrap sequence for fresh DB

Commands to run in order on a new database, after `migrate`:

1. `python manage.py loaddata default_groups` — creates auth groups with base permissions (no `utopia_crm_ladiaria` permissions). If running a ladiaria install, skip this and run `loaddata ladiaria_groups` instead — it covers all groups in full.
2. `python manage.py populate_seller_console_actions` — creates SellerConsoleAction records

> All other bootstrap data (products, price rules, issue statuses, routes, etc.) lives in fixtures
> in `utopia-crm-ladiaria` — see that repo's `COMMANDS.md` for the full loaddata sequence.
