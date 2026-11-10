# Addresses take the country of their state

- **Date:** 2026-11-10
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#122
- **Type:** Bug fix
- **Component:** Core
- **Impact:** Data Quality

## 🎯 Summary

`Address.country` became a foreign key in migration `0076`, which set the country of every address existing at the time. Since then, none of the paths that create addresses sets it: the new address form, the MercadoPago and Witty signups, adding products to a contact. Only the CSV contact import tries, by name. At la diaria, 13,966 addresses had no country (13,555 of them with a state). The contact screen hid it, because it shows the country through the state (`address.state.country`), but anything reading `address.country` directly left them out. Now an address saved without a country takes its state's, and a data migration fills the existing ones the same way.

## ✨ Changes

### 1. `Address.save` takes the country from the state

**File:** `core/models.py`

```python
if self.country_id is None and self.state_id:
    self.country_id = self.state.country_id
```

A state belongs to a single country, so this is not a guess. There is no blind default country: an address that comes with its own country (a foreign billing address, for instance) keeps it, and one without a state stays without a country.

### 2. A data migration fills the existing ones

**File:** `core/migrations/0125_address_country_from_state.py`

The same rule in a single `UPDATE` with a subquery, without calling `save()` per row (that would trigger the web sync on every address). Addresses without a state are left as they are. Its reverse does nothing.

## 📁 Files Modified

- **`core/models.py`** — `Address.save` takes the country from the state
- **`CHANGELOG.md`** — Entry for this change

## 📁 Files Created

- **`core/migrations/0125_address_country_from_state.py`** — Fills the existing addresses
- **`tests/test_address_country.py`** — Tests

## 🧪 Manual Testing

**Automated tests** (`tests/test_address_country.py`): the country comes from the state, a country that comes with the address is kept, no state means no country, and the migration fills the existing ones and leaves the rest. The whole base suite passes (530 tests, without `test_cmssync`, which needs a running CMS).

1. **Happy path:**
   - Add an address to a contact from the contact screen, choosing a state.
   - **Verify:** In the admin, the address has the state's country.

2. **Edge case, no state:**
   - Add an address without a state.
   - **Verify:** It has no country, as before.

## 📝 Deployment Notes

- **Migrations required:** `core 0125`. At la diaria it fills 13,555 addresses in one query.
- No settings change.

## 🎓 Design Decisions

- **From the state, not a default country:** a default would put the local country on foreign addresses; the state already says where the address is.
- **One query, no `save()` per row:** saving an address can trigger the web sync.

---

- **Date:** 2026-11-10
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl122-pais-de-la-direccion
- **Type:** Bug fix
- **Modules affected:** core
