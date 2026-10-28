# Closing lost schedules from a daily cron

- **Date:** 2026-10-22
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** gl58-cierre-agendas-cron (it/utopia-crm-ladiaria#58)
- **Type:** Enhancement
- **Component:** Core (campaigns), Logistics
- **Impact:** Operations, Cron mail noise

## 🎯 Summary

`close_lost_schedule_activities` (t1175) was built for one-off cuts: it only accepted a fixed `--date`. La diaria now
wants it as a daily routine ("close every schedule more than 30 days overdue", 15 days from 2026-11-30), so the
command gains a relative `--days N`. Cron mails everything a command prints, and the daily summary would land in an
inbox every night, so this command and `create_deliveries` now honour `--verbosity 0`: a normal run prints nothing
and the mail only arrives when something fails. The note written on each closed activity no longer carries the
`t1175` ticket number, which made no sense on a routine that runs every day.

## ✨ Changes

### 1. `--days N`, mutually exclusive with `--date`

**File:** `core/management/commands/close_lost_schedule_activities.py`

The two options live in a required mutually exclusive group, so the command still has no default cutoff: nobody
should close schedules by accident. `--days N` is the same as `--date` with the date N days ago, and goes through the
same `get_cutoff`, so the cutoff day is included in full. A negative `--days` aborts with a `CommandError`.

```bash
python manage.py close_lost_schedule_activities --days 30 --verbosity 0
```

### 2. Silent runs with `--verbosity 0`

**Files:** `core/management/commands/close_lost_schedule_activities.py`,
`logistics/management/commands/create_deliveries.py`

- `close_lost_schedule_activities` gates every informational line behind `verbosity >= 1`: the summary, the
  "not a dry run" warning, the CSV message, "no schedules to close" and the final count. The only exception is the
  list of schedules **without** a `ContactCampaignStatus`: those are an anomaly, so they are printed at any
  verbosity and the cron mail carries them.
- `create_deliveries` used bare `print()`, which ignores `--verbosity`. It now writes with `self.stdout.write` and
  prints nothing at verbosity 0.

Failures are unaffected: an exception still ends in a traceback on stderr, which cron mails.

### 3. The activity note without the ticket number

**Files:** `core/management/commands/close_lost_schedule_activities.py`, `locale/es/LC_MESSAGES/django.po`

The note went from *"Automatically closed due to lost schedule (t1175, YYYY-MM-DD)."* to *"Automatically closed due
to lost schedule (YYYY-MM-DD)."*. The msgid changes, and its Spanish translation with it. Notes already written keep
their old text.

## 📁 Files Modified

- **`core/management/commands/close_lost_schedule_activities.py`** — `--days`, verbosity gating, note without the
  ticket number.
- **`logistics/management/commands/create_deliveries.py`** — `self.stdout.write` instead of `print()`, silent at
  verbosity 0.
- **`locale/es/LC_MESSAGES/django.po`** — New msgid for the note.
- **`tests/test_close_lost_schedule.py`** — The note test checks the date instead of `t1175`; new
  `CloseLostScheduleCronTest` (7 tests: inclusive `--days` cutoff, exclusive options, missing cutoff, negative days,
  silent run, silent run with nothing to close, anomaly still reported).
- **`COMMANDS.md`** — `close_lost_schedule_activities` is now `scheduled`; both rows mention `--verbosity 0`.
- **`CHANGELOG.md`** — Entry for this change.

## 📁 Files Created

- **`tests/test_create_deliveries.py`** — Silent at verbosity 0, still reports the process by default.

## 🧪 Manual Testing

1. **Daily cutoff (happy path):**
   - Run `python manage.py close_lost_schedule_activities --days 30 --dry-run`.
   - **Verify:** the summary counts the schedules dated 30 days ago or older, and nothing is written.

2. **Silent cron run:**
   - Run `python manage.py close_lost_schedule_activities --days 30 --verbosity 0`.
   - **Verify:** no output; the schedules are closed and their note reads "Cerrado automáticamente por agenda
     perdida (date)." with no ticket number.

3. **Missing or conflicting cutoff (edge case):**
   - Run the command with no cutoff, then with `--days 30 --date 2026-05-31`, then with `--days -1`.
   - **Verify:** the three runs abort without touching anything.

4. **`create_deliveries` in silence:**
   - Run `python manage.py create_deliveries --verbosity 0`.
   - **Verify:** no output, and the deliveries of the day are created as before.

## 📝 Deployment Notes

- No database migrations required.
- **Recompile translations** (`python manage.py compilemessages -l es`): the note's msgid changed. Without it the note
  is written in English.
- Cron lines can switch from `--date $(date -d '30 days ago' +\%F)` to `--days 30`, and add `--verbosity 0` to both
  commands. Adding `--verbosity 0` before this deploy is harmless: the old code ignores it.

## 🎓 Design Decisions

- **`--days` as a shorthand for `--date`, not a second code path.** Both end in the same `get_cutoff`, so a cron with
  `--days 30` and a manual run with the equivalent date close exactly the same schedules.
- **Anomalies survive `--verbosity 0`.** The point of the silent mode is that a mail means "look at this". A schedule
  without a campaign status is exactly that, so it is the one thing still printed.

---

- **Date:** 2026-10-22
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl58-cierre-agendas-cron
- **Type:** Enhancement
- **Modules affected:** Core, Logistics
