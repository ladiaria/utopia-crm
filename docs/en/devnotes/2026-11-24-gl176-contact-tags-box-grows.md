# Contact tags: the Tagify box grows, so every tag's x removes it

- **Date:** 2026-11-24
- **Author:** Tanya Tree + Claude Opus 5.5
- **Ticket:** it/utopia-crm-ladiaria#176
- **Type:** Bug Fix
- **Component:** support (contact edit form, contact list filter)
- **Impact:** Anyone editing contact tags

## 🎯 Summary

The Tags field of the contact edit form is a Tagify box. The template renders the input with `class="form-control"`, and Tagify copies the input's classes to its box (`<tags class="tagify … form-control">`). Bootstrap gives `.form-control` a fixed one-line height, so the box showed one row of tags behind a scroll: 32 px for 327 px of content, on a test contact with 41 tags. Clicking the x of a tag outside the last row did nothing visible except scroll to the bottom. On mousedown Tagify focuses its text input, which sits after the last tag, so the browser scrolled the box to it and the click landed elsewhere. To remove `eliminar` from contact 705442 in production, every tag after it had to be deleted from the keyboard. The box now grows with its tags.

## ✨ Changes

### 1. The Tagify box grows with its tags

**Files:** `support/templates/create_contact/create_contact.html`, `support/templates/contact_list.html`

The page `<style>` drops `max-height: 150px`, `overflow-y: auto` and the scroll bar padding, and adds:

```css
.tagify.form-control {
  height: auto;
}
```

The border and the background gradient stay. The contact list filter had the same style and the same `form-control`, so it gets the same fix. With no tags it is as tall as the other filters.

### 2. The scroll hint goes away

**Files:** `support/templates/create_contact/tabs/_data.html`, `locale/es/LC_MESSAGES/django.po`

"Scroll to view all tags" is removed from the form, and its entry from the `.po`.

## 📁 Modified Files

- **`support/templates/create_contact/create_contact.html`** — Tagify box style
- **`support/templates/contact_list.html`** — Same style for the tag filter
- **`support/templates/create_contact/tabs/_data.html`** — Scroll hint removed
- **`locale/es/LC_MESSAGES/django.po`** — Entry of the removed hint
- **`CHANGELOG.md`** — Entry for this change

## 🧪 Manual Testing

1. **Normal case:** open «Edit contact» for a contact with about 40 tags. **Check:** every tag is visible, with no scroll inside the field. Click the x of a tag in the first row. **Check:** it disappears at once. Save. **Check:** the contact no longer has it.
2. **Edge case, few tags:** a contact with one tag, and one with none. **Check:** the field is as tall as the other inputs.
3. **Edge case, contact list:** open the contact list. **Check:** the Tags filter looks like the other filters; add and remove a couple of tags.

Done locally on 2026-11-24: before the fix the box was 32 px for 327 px of content, and the x of a first-row tag only moved `scrollTop` from 0 to 295. After it the box is 327 px and the x removes the tag on the first click, which the save keeps.

## 📝 Deployment Notes

- No migrations, no settings.
- `compilemessages` is not needed: an unused entry was removed.

## 🎓 Design Decisions

- **No height limit.** A contact with 40 tags makes the field about ten rows tall, which is better than any scroll: with a scroll, the click problem comes back as soon as the content is taller than the limit.
- **CSS, not a different widget.** A search inside the field or select2 could make large tag lists easier to handle, but the reported problem was removing tags, and this fixes it without changing how the field works.

---

- **Date:** 2026-11-24
- **Author:** Tanya Tree + Claude Opus 5.5
- **Branch:** gl176-etiquetas-contacto
- **Type:** Bug Fix
- **Modules affected:** support
