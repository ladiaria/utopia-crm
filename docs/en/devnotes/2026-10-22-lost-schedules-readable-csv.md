# Readable CSV for the lost schedule closing

- **Date:** 2026-10-22
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** gl57-csv-legible (it/utopia-crm-ladiaria#57)
- **Type:** UX Improvement
- **Component:** Core (campaigns)
- **Impact:** Auditing, Operations

## 🎯 Summary

`close_lost_schedule_activities --csv` writes the list of schedules it is about to close, so someone can audit it
before running for real. That someone is usually not a developer, and the CSV came out with raw codes (`3`, `5`,
`NF`, `LS`) in an order that interleaved before and after, so a row read as if the contact were already closed. For
the cut of 2026-07-31, la diaria had to build a readable version by hand with a separate script. This change makes the
command produce that version itself: choice labels instead of codes, a translated header, "today" grouped before
"after closing", two extra auditing columns and a file Excel opens with the accents right. The console summary also
moves from hardcoded numbers to labels.

## ✨ Changes

### 1. Labels instead of codes

**File:** `core/management/commands/close_lost_schedule_activities.py`

The status columns use `CAMPAIGN_STATUS(value).label` and the resolution columns `CAMPAIGN_RESOLUTION_CHOICES`. Both go
through `gettext`, so the CSV comes out in the installation's `LANGUAGE_CODE`. The labels are lazy, so they are
turned into `str` before joining or writing them.

- A campaign status with no resolution shows `(no resolution)`.
- A schedule without a `ContactCampaignStatus` leaves the four status and resolution columns empty.

### 2. Column order and translated header

**File:** `core/management/commands/close_lost_schedule_activities.py`

`CSV_HEADER` became `CSV_COLUMNS`, in this order:

```text
Schedule date, Seller, Internal seller, Campaign, Active campaign, Contact ID, Contact,
Status today, Resolution today, Status after closing, Resolution after closing, Activity ID
```

The header row is written from `csv_header()`, which translates each column at write time.

### 3. Two auditing columns

**File:** `core/management/commands/close_lost_schedule_activities.py`

- **Internal seller** (`Seller.internal`): in la diaria, it tells the schedules of sellers who still work there from
  the ones left behind by people who are gone. In the 2026-07-31 cut those were 119 out of 318.
- **Active campaign** (`Campaign.active`).

Both are written as the translated "Yes" / "No".

### 4. Excel-friendly file

**File:** `core/management/commands/close_lost_schedule_activities.py`

The file is written with `encoding="utf-8-sig"`. The BOM is what tells Excel the file is UTF-8; without it, the
accents in the labels come out garbled.

### 5. The console summary with labels

**File:** `core/management/commands/close_lost_schedule_activities.py`

The two transition lines were hardcoded (`Status 2/6/7 -> 4 (ended with contact), resolution LS`).
`print_transitions()` now builds one line per terminal status from `STATUS_MAP`, with labels:

```text
  - Contactado, Pasar a la mañana, Pasar a la tarde -> Finalizado con contacto (Finalizado por agenda perdida): 227
  - No se contactó aún, Llamado, no se pudo contactar -> Finalizado sin contacto (Finalizado por agenda perdida): 91
```

## 📁 Files Modified

- **`core/management/commands/close_lost_schedule_activities.py`** — Labels, column order, translated header, two
  new columns, `utf-8-sig`, summary from `STATUS_MAP`.
- **`locale/es/LC_MESSAGES/django.po`** — Nine new msgids: the new header columns and `(no resolution)`.
- **`tests/test_close_lost_schedule.py`** — New `CloseLostScheduleCsvTest` (6 tests).
- **`CHANGELOG.md`** — Entry for this change.

## 📚 Technical Details

- The tests compare against the choice labels, not against fixed text: they run in `en-us`, and production writes
  Spanish.
- The CSV columns changed. Anything that parsed the old CSV by column name breaks, but nothing in the repos does: it
  is meant for people.

## 🧪 Manual Testing

1. **The 2026-07-31 cut against a production dump (happy path):**
   - Run `python manage.py close_lost_schedule_activities --date 2026-07-31 --dry-run --csv /tmp/agendas.csv` with
     `LANGUAGE_CODE = "es"` and compiled translations.
   - **Verify:** Spanish header, labels in the four status columns, "Sí"/"No" in the two new columns. Done against the
     2026-10-08 dump: 318 rows, identical to the version built by hand.

2. **Open it in Excel:**
   - Open the CSV with a double click.
   - **Verify:** the accents read right ("Resolución", "Campaña").

3. **Schedule without a campaign status (edge case):**
   - Create a pending schedule with a campaign and no `ContactCampaignStatus`, and run the command with `--csv`.
   - **Verify:** the row is there with its four status and resolution columns empty, and the summary reports it under
     "Without ContactCampaignStatus".

## 📝 Deployment Notes

- No database migrations required.
- **Recompile translations** (`python manage.py compilemessages -l es`): without it the header comes out in English.

---

- **Date:** 2026-10-22
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl57-csv-legible
- **Type:** UX Improvement
- **Modules affected:** Core
