# Extension point for extra sale actions in the seller console

- **Date:** 2026-10-20
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** gl45-whatsapp-callcenter
- **Type:** Enhancement
- **Component:** Support (seller console)
- **Impact:** Extensibility

## 🎯 Summary

The seller console had no hooks: a customization package that wanted a button of its own next to the call result
buttons had to override the whole `content` block, copying around 500 lines. This change adds one empty block in the
"Acciones de Venta" column, so a package can add sale actions by overriding only that block. The motivation is la
diaria's call center WhatsApp button (it/utopia-crm-ladiaria#45), which is specific to that deployment and does not
belong in the base.

## ✨ Changes

### 1. `extra_sale_actions` block

**File:** `support/templates/seller_console.html`

`{% block extra_sale_actions %}` goes in the right ("Acciones de Venta") column, after Sell / Send promo (or the
subscription buttons when the contact already has one) and before Schedule. It is empty in the base, so the console
renders exactly as before. A package overrides it from its own `seller_console.html`:

```html
{% extends "seller_console.html" %}

{% block extra_sale_actions %}
  <form method="post" action="{% url 'my_action' contact.id %}">
    {% csrf_token %}
    <button type="submit" class="btn btn-block bg-gradient-success btn-sm mt-1">My action</button>
  </form>
{% endblock extra_sale_actions %}
```

The block sees the console's context: `contact`, `campaign`, `seller`, `console_instance`, `category`, `url` and
`offset`.

### 2. The result buttons sit outside `consoleForm`

HTML does not allow nested forms, and a package action that posts somewhere else needs a form of its own. So
`consoleForm` now closes after the notes and the resolution reason, and the three columns of buttons sit after it:

- The result buttons (`.result-btn`) never needed to be inside: they are `type="button"` and submit `consoleForm`
  through JavaScript, which finds it by id.
- The two Schedule inputs (`call_date`, `call_time`) join `consoleForm` with the HTML `form` attribute, so they are
  still posted with it.
- The rest of the column is links, which do not depend on the form.

## 📁 Files Modified

- **`support/templates/seller_console.html`** — `consoleForm` closes before the buttons; empty `extra_sale_actions`
  block; `form="consoleForm"` on the Schedule inputs. The button columns are reindented one level, so the diff is
  easier to read ignoring whitespace (`git diff -w`).
- **`CLAUDE.md`** — The new hook under *Extension patterns*.
- **`CHANGELOG.md`** — Entry for this change.

## 🎓 Design Decisions

- **In the sale actions column, not below the whole button bar.** Below the three columns it would read as an
  afterthought, far from where the seller is looking. Next to Sell / Send promo it sits with the other actions that
  reach out to the person.
- **Moving the buttons out of the form instead of documenting "no forms here".** A block inside `consoleForm` would
  force every package action to be a link or to post through `formaction`, and a submit button inside `consoleForm`
  would also become the target of implicit submission (pressing Enter in the date field).
- **One block, not one per column.** There is one real use today; more blocks can be added when someone needs them.

## 🧪 Manual Testing

1. **Console without a package using the block (happy path):**
   - Open the seller console of a campaign with contacts.
   - **Verify:** the same buttons as before, in the same place.

2. **Schedule still posts date and time:**
   - Pick a date and a time and press Schedule.
   - **Verify:** the scheduled activity is created at that date and time.

3. **Result buttons still work:**
   - Choose a resolution reason and press "No interesado"; on another contact, press "Llamar más tarde".
   - **Verify:** both register the result and move to the next contact, as before.

4. **Package adding an action:**
   - Override the block as in the example above.
   - **Verify:** the button appears under Sell / Send promo, and submitting it posts its own form, not
     `consoleForm`.

## 📝 Deployment Notes

- No database migrations required.
- No translations to compile.
- No configuration changes.

---

- **Date:** 2026-10-20
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl45-whatsapp-callcenter
- **Type:** Enhancement
- **Modules affected:** Support
