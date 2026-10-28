# Daily exchange rates, loaded from the BCU

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
day, and an `update_exchange_rates` command that loads the rates every day from the Central Bank of Uruguay (BCU). No
invoice uses it yet: currencies on invoices come in a later change. Part of la diaria's US dollar subscriptions paid
through PayPal (it/utopia-crm-ladiaria#64, #71).

## ✨ Changes

### 1. The `ExchangeRate` model

**Files:** `invoicing/models.py`, `invoicing/migrations/0032_exchangerate.py`

One row per currency (ISO 4217 code) and day, unique on `(currency, date)`, with the `rate` as published by the
source (`DecimalField(12, 6)`: the BCU publishes 6 decimals), the `source` that loaded it and `created_at`. Only the
days the source publishes have a row, so the table is also the history of which rate applied on any date.

### 2. Which rate applies to a date

**File:** `invoicing/exchange_rates.py`

`get_exchange_rate(currency, for_date)` returns the last rate **before** `for_date`. Sources only publish on business
days, so the previous row is already the previous business day's: weekends and holidays are skipped with no calendar
to maintain.

It raises `ExchangeRateNotAvailable` when there is no previous rate, or when it is older than
`EXCHANGE_RATE_MAX_AGE_DAYS` calendar days (default 6). A document issued with a stale rate would be wrong, so it is
better that it waits until the rate is loaded.

### 3. The BCU source

**File:** `invoicing/exchange_rates.py`

`fetch_bcu(currency, date_from, date_to)` calls the BCU's public SOAP web service (`awsbcucotizaciones`, no key
needed) and returns `(date, rate)` pairs. It uses the buying rate (`TCC`) of currency 2225, "DLS. USA BILLETE", the
interbank US dollar, for which the BCU publishes the same buying and selling value. Only `USD` is mapped for now
(`BCU_CURRENCY_CODES`).

The BCU answers error code 100 when the range has no published day (a weekend, a holiday, today before it closes):
that is an empty result, not an error. Any other error code raises.

The source is pluggable: `EXCHANGE_RATE_SOURCE` takes the dotted path of any callable with the same signature, and its
optional `source_name` attribute is stored on the rows it loads.

### 4. The `update_exchange_rates` command

**File:** `invoicing/management/commands/update_exchange_rates.py`

For each currency in `EXCHANGE_RATE_CURRENCIES` (or `--currency`), it fetches the last `--days` days (default 10) and
creates the missing rows, so a day the source failed is caught up the next one. It never overwrites an existing row:
if one differs from the source (for instance, a rate loaded by hand), it is reported. At the end it checks that the
rate for today is available, so it should run before billing.

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

- **`invoicing/exchange_rates.py`** — `get_exchange_rate`, `ExchangeRateNotAvailable` and the BCU source.
- **`invoicing/management/commands/update_exchange_rates.py`** — The daily load.
- **`invoicing/migrations/0032_exchangerate.py`** — Creates the table and its unique constraint.
- **`tests/test_exchange_rates.py`** — Previous business day rule, max age, parsing of a real BCU answer (and its
  error answers), and the command with a fake source.

## 📚 Technical Details

**Settings**, all optional:

```python
EXCHANGE_RATE_CURRENCIES = ["USD"]  # Default: [] (the command does nothing).
EXCHANGE_RATE_SOURCE = "invoicing.exchange_rates.fetch_bcu"  # Default.
EXCHANGE_RATE_MAX_AGE_DAYS = 6  # Default.
```

**Why 6 days.** In Uruguay the longest gaps between published days are Carnival (Monday and Tuesday are bank
holidays, so Wednesday uses Friday's rate, 5 days old) and Tourism Week. 6 leaves one day of slack and still fails
when the daily load has stopped working.

**What the BCU answers**, checked against the live service on 2026-10-28: a range spanning a weekend returns only the
business days (2026-10-23 to 2026-10-26 returns the 23rd and the 26th); a holiday is missing (2026-10-12); a range
with no published day returns status 0 with error 100, "No existe cotización para la fecha indicada"; a malformed
date returns error 102. Values come with 6 decimals (`40.214000`), while the BCU's web page rounds them to 2.

**Why a table and not a single setting or variable.** A single value loses the history: it would not be possible to
tell which rate applied to a date, or to audit a document afterwards.

## 🧪 Manual Testing

1. **Daily load (happy path):**
   - With `EXCHANGE_RATE_CURRENCIES = ["USD"]`, run `python manage.py update_exchange_rates`.
   - **Verify:** it prints one "loaded" line per business day of the last 10 days, and the rates appear in the admin
     under Invoicing → Exchange rates with source `bcu`. Running it again loads nothing and prints nothing.

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

## 📝 Deployment Notes

- **Migrations required:** `invoicing.0032_exchangerate`.
- **Recompile translations:** `python manage.py compilemessages -l es`.
- To use it, set `EXCHANGE_RATE_CURRENCIES` and add `update_exchange_rates --verbosity 0` to the cron, early in the
  morning and before billing. The server needs outbound HTTPS to `cotizaciones.bcu.gub.uy`.
- Without `EXCHANGE_RATE_CURRENCIES`, nothing changes.

## 🚀 Future Improvements

- `currency` and the issue-time `exchange_rate` on invoices, taken from `get_exchange_rate` when the invoice is
  created.
- More currencies in `BCU_CURRENCY_CODES` if they are ever needed.

## 🎓 Design Decisions

- **Rows are never overwritten.** Once a rate is used to issue a document, silently changing it would make the table
  disagree with the documents. A difference is reported, and a person decides.
- **The BCU is queried directly, not through third-party APIs** that republish its data: a rate used in tax documents
  should not depend on an intermediary.

---

- **Date:** 2026-10-28
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl71-cotizaciones-bcu
- **Type:** Feature
- **Modules affected:** Invoicing
