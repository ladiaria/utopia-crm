# Extension points for extra tabs in the contact detail

- **Date:** 2026-10-08
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** gl21-contact-detail-extra-tabs
- **Type:** Enhancement
- **Component:** Support (contact detail)
- **Impact:** Extensibility

## 🎯 Summary

The list of tabs in the contact detail page is written by hand in the base template, and its only hook was the
`whatsapp_messages_count` block, which lives inside the link of the WhatsApp tab. A customization package that
wanted a tab of its own had to override the whole `content` block, copying around 125 lines of a template that
changes often. This change adds two empty blocks, one for extra tabs and one for their panes, so a package can add
tabs by overriding only those blocks. The motivation is la diaria's radio WhatsApp tab, which is specific to that
deployment and does not belong in the base.

## ✨ Changes

### 1. `extra_tabs` and `extra_tab_panes` blocks

**File:** `support/templates/contact_detail/detail.html`

- `{% block extra_tabs %}` goes in the tab bar (`#contact-detail-tabs`), right after the WhatsApp tab and before
  the Invoices tab, which stays last because it is styled as a button.
- `{% block extra_tab_panes %}` goes at the end of `.tab-content`, after the Invoices pane.

Both are empty in the base, so the page renders exactly as before. A package overrides them from its own
`contact_detail/detail.html`, which already extends the base one:

```html
{% extends "contact_detail/detail.html" %}

{% block extra_tabs %}
  <li class="nav-item">
    <a class="nav-link" href="#my_tab" data-toggle="tab">My tab
      <div class="ml-1 badge badge-pill badge-primary">{{ count }}</div>
    </a>
  </li>
{% endblock extra_tabs %}

{% block extra_tab_panes %}
  <div class="tab-pane" id="my_tab">{% include "contact_detail/tabs/_my_tab.html" %}</div>
{% endblock extra_tab_panes %}
```

The `href` of each tab must match the `id` of its pane, as with the base tabs.

## 📁 Files Modified

- **`support/templates/contact_detail/detail.html`** — Two empty blocks, `extra_tabs` and `extra_tab_panes`.
- **`CHANGELOG.md`** — Entry for this change.

## 🎓 Design Decisions

- **Empty blocks instead of a placeholder tab.** The WhatsApp tab follows another pattern: the base renders a tab
  with a "This is not configured" placeholder and the package overrides the included template. That forces every
  deployment to show a tab it may not use. Empty blocks add nothing unless a package fills them.
- **Before Invoices, not at the very end.** Invoices is styled as a red or green button and works as the closing
  element of the bar; tabs added after it would look out of place.
- **Two blocks and not one.** The tab and its pane live in different parts of the markup (`.card-header` and
  `.card-body`), so a single block cannot hold both.

## 🧪 Manual Testing

1. **Contact detail without a package using the blocks (happy path):**
   - Open any contact's detail page.
   - **Verify:** the same tabs as before, in the same order, and every tab opens its pane.

2. **Package adding a tab:**
   - In a package template that extends `contact_detail/detail.html`, override both blocks as in the example above.
   - Open a contact's detail page.
   - **Verify:** the new tab appears between "WhatsApp Messages" and "Invoices", and clicking it shows its pane.

3. **Package that overrides the template but not these blocks (edge case):**
   - With a package whose `contact_detail/detail.html` extends the base one and only fills other blocks (as
     `utopia_crm_ladiaria` does today), open a contact's detail page.
   - **Verify:** the page is identical to the one before this change: same number of tabs and panes.

## 📝 Deployment Notes

- No database migrations required.
- No translations to compile.
- No configuration changes.

---

- **Date:** 2026-10-08
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl21-contact-detail-extra-tabs
- **Type:** Enhancement
- **Modules affected:** Support
