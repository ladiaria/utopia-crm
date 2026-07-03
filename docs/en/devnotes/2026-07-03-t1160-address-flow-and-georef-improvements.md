# Address Flow Overhaul: Required Fields, One-Step Editing, and Georef Resilience

- **Date:** 2026-07-03
- **Author:** Tanya Tree + Claude Sonnet 5
- **Ticket:** t1160
- **Type:** Enhancement
- **Component:** Support (Addresses), Core Models, Georef Integration
- **Impact:** Data Integrity, User Experience, Operability

## 🎯 Summary

This ticket started from a simple request — make `address_1` and `address_2` required on the address form, since operators kept forgetting to fill them in — and grew into a broader cleanup of the whole address lifecycle (add, edit, normalize). Along the way several real data-integrity bugs surfaced: addresses that stayed marked `verified` after their text was edited out from under the coordinates, a `georef_point` field that "resurrected" stale coordinates after they were supposedly cleared, an unhandled crash in the address-normalization tool, and a contact-detail bug that hid the one button operators needed most (`Normalize`) exactly when the address needed it. The Uruguay georef HTTP calls also had no timeout, so a slow/unresponsive service could hang a worker; that's now handled with a request timeout, error handling, and a DB-backed kill switch that can disable georef on the fly (manually or automatically after repeated failures) without a deploy.

## ✨ Changes

### 1. Required address fields

**File:** `support/forms.py`

`SugerenciaGeorefForm` (used by both `agregar_direccion` and `editar_direccion`) now declares `address_1` and `address_2` as `required=True`, overriding the model's `blank=True`. The model itself is untouched (other flows, like CSV imports, still allow blank `address_2`), so no migration is needed.

### 2. Real `<label>` elements with required markers

**Files:** `support/templates/location/agregar_direccion.html`, `support/templates/location/editar_direccion.html`

Fields previously relied on `placeholder=` text as their only label. They now have proper `<label>` tags, with a red asterisk rendered conditionally from `form.<field>.field.required` — following the same pattern already used elsewhere in the app (`bulk_delete_campaign_status.html`).

### 3. Georef service hardening

**File:** `util/location_utils.py`

All HTTP calls to the Uruguay georef services now go through a single `_georef_get()` helper that adds a `timeout` (`settings.GEOREF_TIMEOUT`, default 5s) and catches `requests.exceptions.RequestException`, returning `None` instead of hanging or raising. A new `georef_habilitado()` function replaces every direct `getattr(settings, "GEOREF_SERVICES", False)` check across both repos (`support/location.py`, `support/views/{all_views,contacts,subscriptions}.py`, `utopia_crm_ladiaria/views/subscriptions.py`):

```python
def georef_habilitado():
    if not getattr(settings, "GEOREF_SERVICES", False):
        return False
    var, _ = Variable.objects.get_or_create(name="georef_services_enabled", defaults={"value": "1"})
    return var.value not in (None, "", "0")
```

The `Variable` model (already used elsewhere for DB-backed settings) acts as a dynamic kill switch on top of the static `GEOREF_SERVICES` setting — editable from the admin without a deploy. `_georef_get()` also tracks consecutive failures in a second `Variable` (`georef_fallos_consecutivos`); after `GEOREF_MAX_FALLOS_CONSECUTIVOS` (default 3, `settings.py`) in a row it auto-disables `georef_services_enabled` and logs an error. Re-enabling after that is manual (set the `Variable` back to `"1"`) — no automatic retry timer, by design.

### 4. Manual-mode checkbox ("I couldn't find the address")

**Files:** `support/templates/location/agregar_direccion.html`, `support/templates/location/editar_direccion.html`

A checkbox now sits above the address search box. Checking it:

- Hides the search box, the lat/long row, and the map; the form column expands to full width.
- Clears and disables `latitude`, `longitude`, `city_georef_id`, `state_georef_id` so they can't be submitted with stale values.
- Unlocks `address_1`/`city`/`state` for editing **without** clearing their current text — whatever was already typed or suggested stays, so the operator only fixes what's wrong instead of retyping everything.
- Reveals a "Guardar sin georreferenciación" button (`name="save_needs_georef"`).

### 5. `editar_direccion` becomes a one-step flow

**File:** `support/location.py`

`editar_direccion` used to force a redirect to `normalizar_direccion` after any raw text edit. It now embeds the same search-box-plus-suggestion-picker UI as `agregar_direccion`: picking a suggestion resolves coordinates in the same request and shows a "Guardar cambios" button, with no forced hop through a second screen. `normalizar_direccion` was **not** removed — it's still linked directly from the contact detail tabs and from the mass-georef batch tool, both of which need it standalone.

The button row was restructured to mirror `agregar_direccion`'s mutually-exclusive `if`/`elif` branches (resolved state → "Guardar cambios"; search failed → danger buttons; georef off → "Guardar cambios"), so the plain save button and the "not found" buttons never show at the same time.

### 6. Data integrity fixes

**Files:** `core/models.py`, `support/location.py`

Several related bugs were found and fixed:

- **`Address.save()`** set `verified = True` when state/city ids and the geo point were present, but never cleared `needs_georef` — an address could be simultaneously "verified" and flagged "needs georef", which the contact-detail UI renders as red (a bug in itself, see #8). Fixed by also setting `needs_georef = False` in that branch.
- **`Address.reset_georef()`** cleared `latitude`/`longitude`/`georef_point` but not `state_georef_id`/`city_georef_id`. Now clears all four.
- **Stale `georef_point` resurrection:** `georef_point` isn't a form field, so clearing `latitude`/`longitude` via the manual-mode checkbox left `georef_point` untouched on the instance. `Address.save()` has logic to *derive* lat/long from `georef_point` when they're missing — which silently resurrected the old coordinates on save. The `save_needs_georef` branches in both `agregar_direccion` and `editar_direccion` now call `reset_georef()` (which clears `georef_point` too) instead of manually setting `needs_georef = True` and saving.
- **Text/coordinate mismatch:** `address_1`/`city`/`state` were only locked read-only when a suggestion had *just* been resolved in the current request (`resolved_now`), not whenever the address already had valid coordinates. That meant opening `editar_direccion` for an already-verified address let you retype `address_1` freely while the old, now-mismatched coordinates stayed attached and `verified` stayed `True`. Fixed by locking those fields whenever `lat and lng` are present, and further simplified to lock them whenever `georef_activated` is true at all (regardless of whether a suggestion has been picked yet) — the only way to type in them is via the search flow or the manual-mode checkbox, so operators can't start typing into fields that won't actually be saved.

### 7. `normalizar_direccion` fixes

**Files:** `support/location.py`, `support/templates/location/normalizar_direccion.html`

- `form_nuevo.address_1` was the only editable field among the suggestion's data (city/state/lat/long were already read-only). That let an operator change the street number after picking a suggestion and save with the *old* suggestion's coordinates still attached — `verified = True` with mismatched data. Now read-only, like the rest.
- When the selected suggestion had no resolvable department (`seleccionar_sugerencia` returns its failure dict, empty strings), the view slugified an empty string, failed to match any `State`, and raised `StopIteration` — which redirected to `agregar_direccion` (wrong flow, creates an unrelated new address) with a confusing message. Now handled gracefully: falls back to the address's current state, shows the address's own "no georref data for this suggestion" message, and stays on the page so the operator can try another suggestion from the dropdown or use the existing "Edit address" escape hatch.
- The suggestion `<select>` navigates via `window.location = ...` on change, which triggered the page's `beforeunload` "Leave site?" dialog every time (the handler only skips the warning if the *form* was submitted, not this in-page navigation). Fixed by setting `submitButtonPressed = true` before navigating.
- Both cards got clearer titles: left card is "Dirección actual (guardada)" (a read-only reference to what's currently saved) with a Normalized/Unnormalized badge; right card is "Ubicación en el mapa" (already verified) or "Normalizar dirección" (picking a suggestion) — previously both states showed the same misleading "Dirección normalizada" header.

### 8. Contact detail overview tab: hidden Normalize button

**File:** `support/templates/contact_detail/tabs/_overview.html`

The address list showed a red ⊗ icon when `address.needs_georef` and a "Normalize" link only in the `elif not address.verified` branch — mutually exclusive by construction. Since an address needing georef is (almost) always unverified, the button was hidden precisely when it was needed most. Restructured so the icon and the link can coexist: verified → green check only; not verified → red ⊗ (if `needs_georef`) *and* the Normalize link together.

## 📁 Files Modified

- **`core/models.py`** — `Address.save()` clears `needs_georef` alongside `verified`; `Address.reset_georef()` also clears `state_georef_id`/`city_georef_id`
- **`settings.py`** — Added `GEOREF_TIMEOUT` and `GEOREF_MAX_FALLOS_CONSECUTIVOS`
- **`support/forms.py`** — `address_1`/`address_2` required in `SugerenciaGeorefForm`
- **`support/location.py`** — `editar_direccion` rewritten into a one-step search/resolve flow; `normalizar_direccion` no longer crashes on a suggestion with no department; `save_needs_georef` branches use `reset_georef()`
- **`support/templates/contact_detail/tabs/_overview.html`** — Normalize link no longer hidden by `needs_georef`
- **`support/templates/location/agregar_direccion.html`** — labels, required asterisks, manual-mode checkbox, empty-map-card fix, readonly gating fixes
- **`support/templates/location/editar_direccion.html`** — same as above, plus embedded search UI replacing the old raw-edit form
- **`support/templates/location/normalizar_direccion.html`** — `address_1` read-only, `beforeunload` fix, card titles
- **`support/views/all_views.py`**, **`support/views/contacts.py`**, **`support/views/subscriptions.py`** — use `georef_habilitado()` instead of the raw settings check
- **`util/location_utils.py`** — `_georef_get()` wrapper (timeout, error handling), `georef_habilitado()`, consecutive-failure tracking

## 🧪 Manual Testing

1. **Add an address end-to-end:**
   - With `GEOREF_SERVICES = True`, go to a contact's "Add address", type a street in the search box, pick a suggestion.
   - **Verify:** `address_1`/`city`/`state` become read-only with the resolved values, a map appears, and "Guardar" saves with `verified=True`, `needs_georef=False`.

2. **Edit an already-verified address without searching:**
   - Open "Edit address" for an address that already has valid coordinates. Don't touch the search box.
   - **Verify:** `address_1`/`city`/`state` are read-only from the start (no way to retype the street without a fresh search or manual mode), and a single "Guardar cambios" button is visible — not both that and the danger buttons.

3. **Edge case — manual mode on a previously-verified address:**
   - On that same address, check "cargar manualmente", then "Guardar sin georreferenciación".
   - **Verify:** `latitude`, `longitude`, `georef_point`, `state_georef_id`, `city_georef_id` are all `None` afterward, `verified=False`, `needs_georef=True` — no stale coordinates survive.

4. **Edge case — suggestion with no department in `normalizar_direccion`:**
   - Navigate to `normalizar_direccion` for an address whose top suggestion resolves with an empty department (mock `seleccionar_sugerencia`'s failure path, or find one against the real service).
   - **Verify:** the page renders normally (200, not a redirect) showing the "no georref data" fallback and the suggestion dropdown, instead of crashing out with `StopIteration`.

5. **Edge case — georef service down:**
   - Point `SERVICIO_DIRECCION_AUTOCOMPLETADO` at an unreachable host, trigger 3+ consecutive lookups.
   - **Verify:** each call returns gracefully (no hang, no 500), and the `Variable` `georef_services_enabled` flips to `"0"` after the 3rd failure; `georef_habilitado()` then returns `False` until someone resets it.

## 📝 Deployment Notes

- No database migrations required.
- The `Variable` rows (`georef_services_enabled`, `georef_fallos_consecutivos`) are created lazily on first use via `get_or_create` — no fixture or data migration needed.
- `GEOREF_TIMEOUT` and `GEOREF_MAX_FALLOS_CONSECUTIVOS` have sane defaults in `settings.py`; override in `local_settings.py` only if needed.
- If georef ever needs to be disabled quickly in production without a deploy, set the `Variable` `georef_services_enabled` to `"0"` from the Django admin.

## 🚀 Future Improvements

- Consider an automatic re-enable (TTL-based) for the georef kill switch instead of requiring a manual reset, if repeated outages become common.
- The three address templates (`agregar_direccion.html`, `editar_direccion.html`, and the shared JS) are now near-duplicates; extracting a shared `{% include %}` for the search/manual-mode block was deliberately deferred (see conversation) but would reduce drift risk.
- `normalizar_direccion.html`'s remaining rough edges (mentioned by the user as "also needing fixes") were out of scope for this ticket beyond the specific bugs listed above.

---

- **Date:** 2026-07-03
- **Author:** Tanya Tree + Claude Sonnet 5
- **Branch:** t1160
- **Type:** Enhancement
- **Modules affected:** Support (Addresses), Core Models, Contact Detail
