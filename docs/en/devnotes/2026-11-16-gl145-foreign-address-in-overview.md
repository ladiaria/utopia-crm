# The overview shows the city and country of a foreign address

- **Date:** 2026-11-16
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#145
- **Type:** Enhancement
- **Component:** Support (contact detail), Core (Address)
- **Impact:** User Experience

## 🎯 Summary

The Contact information card of the contact's overview lists each address by its street only (`address_1`). That is enough for an address in the deployment's own country, but a foreign one, like a PayPal signup from the United States, read "131 Lake Shore Dr" with no hint of where it was. An address whose country has no states on file now reads with its city and country: "131 Lake Shore Dr, Newnan, Estados Unidos". It follows the rule of it/utopia-crm-ladiaria#144: the code doesn't name any country.

## ✨ Changes

### 1. `Address.is_abroad` and `Address.abroad_label`

**File:** `core/models.py`

```python
@cached_property
def is_abroad(self):
    return self.country_id is not None and not State.objects.filter(country_id=self.country_id).exists()

@cached_property
def abroad_label(self):
    return ", ".join(filter(None, (self.address_1, self.get_city(), self.country_name)))
```

An address is abroad when it has a country and that country has no states on file. An address with no country is not: its state, if any, says where it is. `needs_state` (#144) now reuses `is_abroad`, with the same result as before.

### 2. The overview line

**File:** `support/templates/contact_detail/tabs/_overview.html`

```django
{% if address.is_abroad %}
  {{ address.abroad_label }}
{% else %}
  {{ address.address_1|default:"-" }}
{% endif %}
```

## 📁 Files Modified

- **`core/models.py`** — `Address.is_abroad` and `Address.abroad_label`; `needs_state` reuses `is_abroad`
- **`support/templates/contact_detail/tabs/_overview.html`** — The address line of the Contact information card
- **`tests/test_address_detail_country.py`** — The overview line for a foreign address and for one in a country with states, and `is_abroad`. The foreign case fails with the old template
- **`CHANGELOG.md`** — Entry for this change

## 🧪 Manual Testing

1. **Happy path, a foreign address:**
   - Open the overview of a contact with an address in a country with no states on file (e.g. a PayPal signup from the United States).
   - **Verify:** The Contact information card shows street, city and country.

2. **Edge case, an address in a country with states:**
   - Open the overview of a contact with a Uruguayan address.
   - **Verify:** The card shows only the street, as before.

3. **Edge case, a foreign address with no city:**
   - Open the overview of a contact with a foreign address and an empty city.
   - **Verify:** The card shows street and country, with no empty gap between commas.

## 📝 Deployment Notes

- No migrations, no settings.

## 🎓 Design Decisions

- **Street, city and country, not `str(address)`:** the full string also has the second line and the address name, which make a list line long; city and country are what say where the address is.

---

- **Date:** 2026-11-16
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl145-direccion-exterior-vista-general
- **Type:** Enhancement
- **Modules affected:** core, support
