# Daily exchange rates table

- **Date:** 2026-10-28
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** gl71-cotizaciones-bcu
- **Type:** Feature
- **Component:** Invoicing (models, admin, management commands)
- **Impact:** Data model, new cron job, new settings

## 🎯 Summary

Invoices in a foreign currency need the exchange rate that applies to the day they are issued, and that rate has to
be the same one the tax authority uses. This change adds the groundwork: an `ExchangeRate` table with one row per
currency and day, a `get_exchange_rate(currency, for_date)` helper that returns the rate of the previous business
day, and an `update_exchange_rates` command that loads the rates every day from a source that each installation
provides, since where the official rate is published depends on the country. No invoice uses it yet: currencies on
invoices come in a later change. Part of la diaria's US dollar subscriptions paid through PayPal
(it/utopia-crm-ladiaria#64, #71), whose customization package provides the Central Bank of Uruguay as the source.

## ✨ Changes

### 1. The `ExchangeRate` model

**Files:** `invoicing/models.py`, `invoicing/migrations/0032_exchangerate.py`

One row per currency (ISO 4217 code) and day, unique on `(currency, date)`, with the `rate` as published by the
source (`DecimalField(12, 6)`), the `source` that loaded it and `created_at`. Only the days the source publishes have
a row, so the table is also the history of which rate applied on any date.

### 2. Which rate applies to a date

**File:** `invoicing/exchange_rates.py`

`get_exchange_rate(currency, for_date)` returns the last rate **before** `for_date`. Official sources only publish on
business days, so the previous row is already the previous business day's: weekends and holidays are skipped with no
calendar to maintain.

It raises `ExchangeRateNotAvailable` when there is no previous rate, or when it is older than
`EXCHANGE_RATE_MAX_AGE_DAYS` calendar days (default 6). A document issued with a stale rate would be wrong, so it is
better that it waits until the rate is loaded.

### 3. The source, provided by each installation

**File:** `invoicing/exchange_rates.py`

`EXCHANGE_RATE_SOURCE` is the dotted path of a callable `(currency, date_from, date_to)` that returns `(date, rate)`
pairs, one per published day in the range, both ends included. Its optional `source_name` attribute is stored on the
rows it loads. There is no default: the base app does not pick a country.

### 4. The `update_exchange_rates` command

**File:** `invoicing/management/commands/update_exchange_rates.py`

For each currency in `EXCHANGE_RATE_CURRENCIES` (or `--currency`), it fetches the last `--days` days (default 10) and
creates the missing rows, so a day the source failed is caught up the next one. It never overwrites an existing row:
if one differs from the source (for instance, a rate loaded by hand), it is reported. At the end it checks that the
rate for today is available, so it should run before billing.

Without `EXCHANGE_RATE_CURRENCIES` it does nothing. With currencies but no `EXCHANGE_RATE_SOURCE`, it fails saying so.

Like `close_lost_schedule_activities`, with `--verbosity 0` it only prints anomalies, and it exits with an error if
there is any, so a cron only mails when something needs attention.

### 5. Admin

**File:** `invoicing/admin.py`

`ExchangeRateAdmin` lists the rates by currency and date. Loading a rate here is the fallback when the source fails;
its `source` is `manual`.

## 📁 Files Modified

- **`invoicing/models.py`** — `ExchangeRate` model.
- **`invoicing/admin.py`** — `ExchangeRateAdmin`.
- **`locale/es/LC_MESSAGES/django.po`** — Spanish translations of the new strings.
- **`CHANGELOG.md`** — Entry for this change.

## 📁 Files Created

- **`invoicing/exchange_rates.py`** — `get_exchange_rate`, `ExchangeRateNotAvailable` and `get_exchange_rate_source`.
- **`invoicing/management/commands/update_exchange_rates.py`** — The daily load.
- **`invoicing/migrations/0032_exchangerate.py`** — Creates the table and its unique constraint.
- **`tests/test_exchange_rates.py`** — Previous business day rule, max age, and the command with a fake source.

## 📚 Technical Details

**Settings:**

```python
EXCHANGE_RATE_CURRENCIES = ["USD"]  # Default: [] (the command does nothing).
EXCHANGE_RATE_SOURCE = "mypackage.exchange_rates.fetch"  # No default; required with currencies.
EXCHANGE_RATE_MAX_AGE_DAYS = 6  # Default.
```

**A source** is any function with this shape:

```python
def fetch(currency, date_from, date_to):
    return [(date(2026, 10, 23), Decimal("40.078")), (date(2026, 10, 26), Decimal("40.214"))]


fetch.source_name = "mysource"
```

It should return nothing for days it does not publish (a range with only a weekend returns `[]`), and raise on real
failures: the command reports the exception and goes on with the next currency.

**Why 6 days.** Long bank holidays leave gaps between published days: in Uruguay, Carnival (Monday and Tuesday are
bank holidays, so Wednesday uses Friday's rate, 5 days old). 6 leaves one day of slack and still fails when the daily
load has stopped working.

**Why a table and not a single setting or variable.** A single value loses the history: it would not be possible to
tell which rate applied to a date, or to audit a document afterwards.

## 🧪 Manual Testing

1. **Daily load (happy path):**
   - With `EXCHANGE_RATE_CURRENCIES = ["USD"]` and `EXCHANGE_RATE_SOURCE` set, run
     `python manage.py update_exchange_rates`.
   - **Verify:** it prints one "loaded" line per published day of the last 10 days, and the rates appear in the admin
     under Invoicing → Exchange rates with the source's name. Running it again loads nothing and prints nothing.

2. **Previous business day:**
   - In `python manage.py shell`, run `get_exchange_rate("USD", <a Monday>)`.
   - **Verify:** it returns the previous Friday's rate.

3. **Edge case — a manual rate that differs:**
   - In the admin, change the rate of one of the loaded days, then run the command again.
   - **Verify:** the command reports that day as an anomaly, exits with an error, and the row keeps the manual value.

4. **Edge case — stale rates:**
   - With the table empty, run `python manage.py update_exchange_rates --currency USD --days 0`.
   - **Verify:** it reports that there is no USD rate before today and exits with an error: today's own rate, even if
     already published, is not the one that applies to today.

5. **Edge case — no source:**
   - Remove `EXCHANGE_RATE_SOURCE` and run `python manage.py update_exchange_rates --currency USD`.
   - **Verify:** it fails saying that `EXCHANGE_RATE_SOURCE` is not set.

## 📝 Deployment Notes

- **Migrations required:** `invoicing.0032_exchangerate`.
- **Recompile translations:** `python manage.py compilemessages -l es`.
- To use it, set `EXCHANGE_RATE_CURRENCIES` and `EXCHANGE_RATE_SOURCE`, and add `update_exchange_rates --verbosity 0`
  to the cron, early in the morning and before billing.
- Without `EXCHANGE_RATE_CURRENCIES`, nothing changes.

## 🚀 Future Improvements

- `currency` and the issue-time `exchange_rate` on invoices, taken from `get_exchange_rate` when the invoice is
  created.

## 🎓 Design Decisions

- **The source lives outside the base app.** Which rate is official, and where it is published, depends on the country
  and on the tax authority; the base app keeps what every installation shares (the table, the previous business day
  rule, the daily load) and lets each one plug its source in.
- **Rows are never overwritten.** Once a rate is used to issue a document, silently changing it would make the table
  disagree with the documents. A difference is reported, and a person decides.

---

- **Date:** 2026-10-28
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl71-cotizaciones-bcu
- **Type:** Feature
- **Modules affected:** Invoicing
