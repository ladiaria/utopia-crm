# The address card shows its own country, even without a state

- **Date:** 2026-11-16
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#144
- **Type:** Bug fix
- **Component:** Support (contact detail), Core (Address)
- **Impact:** User Experience

## 🎯 Summary

A subscriber from the United States signed up through PayPal. Their address was saved with its country (United States) and no state, because the only states on file are Uruguay's departments. The state went to the address notes and to the invoice. Yet the contact's Information tab showed "-" and a red warning in the Country line: it read the country through the state (`address.state.country`), not from the address. The Country line now reads the address' own country, and the State line warns only where a state can actually be chosen.

## ✨ Changes

### 1. The Country line reads `address.country`

**File:** `support/templates/contact_detail/tabs/_information.html`

```django
{% if not address.country %}<i class="fas fa-exclamation-triangle text-danger"></i>{% endif %}
{{ address.country_name|default_if_none:"-" }}
```

The warning now depends on the country, not on the state. Since it/utopia-crm-ladiaria#122, an address saved with a state and no country takes its state's country, so Uruguayan addresses show the same as before.

### 2. `Address.needs_state`

**File:** `core/models.py`

```python
@cached_property
def needs_state(self):
    if self.state_id:
        return False
    return self.country_id is None or State.objects.filter(country_id=self.country_id).exists()
```

A missing state is a missing piece of data only when the address has no country, or its country has states on file to choose from. The State line of the card shows its warning with this property instead of `not address.state`. Nothing in the code names Uruguay: if another country's states are ever loaded, its addresses will warn about a missing state too.

## 📁 Files Modified

- **`core/models.py`** — `Address.needs_state`
- **`support/templates/contact_detail/tabs/_information.html`** — Country line from `address.country`; State line warning from `needs_state`
- **`CHANGELOG.md`** — Entry for this change

## 📁 Files Created

- **`tests/test_address_detail_country.py`** — The Country and State lines of the card, and `needs_state`. The two cases of the bug fail with the old template

## 🧪 Manual Testing

1. **Happy path, a foreign address without a state:**
   - Open a contact with an address whose country is not Uruguay and has no state (e.g. a PayPal signup).
   - **Verify:** Country shows the country with no warning; State shows "-" with no warning.

2. **Edge case, a Uruguayan address without a department:**
   - Open a contact with an address in Uruguay and no department.
   - **Verify:** State shows "-" with the red warning; Country shows Uruguay.

3. **Edge case, an address with no country and no state:**
   - Open a contact with an address that has neither.
   - **Verify:** Both lines show "-" with the red warning.

## 📝 Deployment Notes

- No migrations, no settings.

## 🎓 Design Decisions

- **Foreign states are not loaded as `State` rows.** Several lookups list every state or match one by name with no country: the selectors in `support/forms.py`, the filters, the georeferencer (`support/location.py`). Florida is both a Uruguayan department and a US state, so a name lookup could put a Uruguayan address in the wrong one with no error. The foreign state stays in the address notes and in the invoice's `billing_state`.
- **"Its country has states" instead of "it is the default country":** the rule holds in any deployment of the open-source base, and follows the data.

---

- **Date:** 2026-11-16
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl144-pais-direccion-sin-estado
- **Type:** Bug fix
- **Modules affected:** core, support
