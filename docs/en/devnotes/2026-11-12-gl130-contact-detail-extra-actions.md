# The contact detail button bar gets an extension block

- **Date:** 2026-11-12
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#130
- **Type:** Enhancement
- **Component:** Support (contact detail)
- **Impact:** Extensibility

## 🎯 Summary

The customization package needed a button in the contact detail: «Sell a one-time product», for sellers (it/utopia-crm-ladiaria#130). The button bar above the tabs (New Activity, New Issue, …) had no extension point, so the only way to add a button was to copy the whole `content` block. A new empty block, `extra_actions`, sits at the end of that bar. It is the same idea as `extra_sale_actions` in the seller console.

## ✨ Changes

### 1. `extra_actions` in the contact detail

**File:** `support/templates/contact_detail/detail.html`

```django
      {% block extra_actions %}{% endblock extra_actions %}
    </div>
  </section>
```

An empty block inside the button bar, after the buttons that only Support and Managers see. It is **outside** that group check: each button a package adds checks its own permission. A package's `contact_detail/detail.html`, extending the base one, fills it.

### 2. Documented with the other extension points

**File:** `CLAUDE.md`

"Extra contact detail actions" joins the list of extension patterns, next to the extra tabs and the extra subscription card sections.

## 📁 Files Modified

- **`support/templates/contact_detail/detail.html`** — The `extra_actions` block
- **`CLAUDE.md`** — The new extension point
- **`CHANGELOG.md`** — Entry for this change

## 🧪 Manual Testing

No automated tests here: the block is empty. The customization package fills it, and its tests check that the button shows for a user who can sell and not for one who can't (`utopia_crm_ladiaria/tests/test_venta_oneshot.py`).

1. **Happy path, with a package filling the block:**
   - At la diaria, log in as a seller and open a contact.
   - **Verify:** «Vender producto de una única vez» shows at the end of the button bar.

2. **Edge case, without a package:**
   - Open a contact with no package extending `contact_detail/detail.html`.
   - **Verify:** The button bar looks exactly as before.

## 📝 Deployment Notes

- No migrations, no settings.
- **Order with the package:** either can go first. Without this block nothing breaks, but the package's button doesn't show in the contact detail until this is deployed.

## 🎓 Design Decisions

- **Outside the Support/Managers check:** the buttons that already live there are for those groups; a package's button may be for other users (sellers), so it decides who sees it.
- **At the end of the bar:** the base buttons keep their place.

---

- **Date:** 2026-11-12
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl130-ficha-extra-actions
- **Type:** Enhancement
- **Modules affected:** support
