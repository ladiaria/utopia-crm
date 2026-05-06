# Open Issues Panel in Seller Console and Safe Message Rendering

- **Date:** 2026-03-25
- **Author:** Tanya Tree + Claude Sonnet 4.6
- **Ticket:** t1069
- **Type:** UX Improvement
- **Component:** Support, Seller Console, Issue Management
- **Impact:** User Experience, Seller Workflow

## 🎯 Summary

Sellers working the console had no visibility into whether the contact they were calling had any open issues tracked in the system. This change adds two complementary indicators: a red badge next to the contact's name in the console header warns at a glance when open issues exist and instructs the seller to check the right panel, and a new "Contact's open issues" card appears in the right-hand sidebar listing every non-terminal issue with its category, subcategory, status, date, and notes. As a separate fix in the same branch, the base message template was updated to honour the `safe` extra tag already used by the issue creation confirmation message — previously, the HTML link in that message was displayed as raw text instead of a rendered hyperlink.

## ✨ Changes

### 1. Open Issues Badge in the Console Header

**File:** `support/templates/seller_console.html`

A red `badge-danger` badge is conditionally rendered next to the contact name whenever `open_issues_count > 0`. The badge includes a count and a prompt to check the right panel:

```html
{% if open_issues_count > 0 %}
  <span class="badge badge-danger ml-2"
        title="{% trans "This contact has open issues — check the right panel" %}">
    <i class="fas fa-exclamation-circle"></i>
    {% blocktrans with count=open_issues_count %}{{ count }} open issue(s) — check right panel{% endblocktrans %}
  </span>
{% endif %}
```

The badge sits alongside the existing "No encontrado" and "Llamar más tarde" status badges, keeping the header visually consistent.

### 2. Open Issues Panel in the Right Sidebar

**File:** `support/templates/seller_console.html`

A new `card card-danger card-outline` card is appended to the right column below the `last_read_articles` HTMX partial. It is only rendered when `open_issues` is non-empty. Each issue displays its category and subcategory, status badge, creation date, a link to the issue detail view (opens in a new tab), and the full issue notes without truncation:

```html
{% if open_issues %}
  <div class="card card-danger card-outline mt-2">
    ...
    {% for issue in open_issues %}
      <div class="list-group-item py-2 px-3">
        <span class="font-weight-bold">{{ issue.get_category }}{% if issue.get_subcategory %} – {{ issue.get_subcategory }}{% endif %}</span>
        <span class="badge badge-secondary">{{ issue.get_status|default_if_none:"" }}</span>
        <span class="text-muted">{{ issue.date_created|date:"d/m/Y" }}</span>
        <a href="{% url "view_issue" issue.id %}" target="_blank">...</a>
        {% if issue.notes %}
          <div class="text-muted mt-1"><small>{{ issue.notes }}</small></div>
        {% endif %}
      </div>
    {% endfor %}
  </div>
{% endif %}
```

Notes are shown in full — not truncated — because sellers are expected to see them in their entirety and contacts are unlikely to have many open issues at once.

### 3. Open Issues Context in the Seller Console View

**File:** `support/views/seller_console.py`

Inside `SellerConsoleView.get_context_data()`, the open issues queryset is built by filtering all `Issue` records for the current contact and excluding those whose status slug is listed in `settings.ISSUE_STATUS_FINISHED_LIST`. This mirrors the same pattern used in `all_views.py` for the community console and issue dashboards:

```python
terminal_statuses = getattr(settings, 'ISSUE_STATUS_FINISHED_LIST', [])
open_issues = Issue.objects.filter(contact=contact).exclude(
    status__slug__in=terminal_statuses
).order_by("-date_created")

context.update({
    ...
    'open_issues': open_issues,
    'open_issues_count': open_issues.count(),
})
```

Both `open_issues` (for the panel) and `open_issues_count` (for the badge) are passed so the template can render each independently without re-evaluating the queryset.

### 4. Safe HTML Rendering in Django Messages

**File:** `templates/adminlte/lib/_messages.html`

The shared messages partial previously rendered all messages through Django's auto-escaping (`{{ message }}`), which caused the HTML link in the issue creation confirmation message to display as raw text. The fix checks whether `'safe'` is present in `message.tags` and applies the `|safe` filter only then:

```html
{% if 'safe' in message.tags %}{{ message|safe }}{% else %}{{ message }}{% endif %}
```

This change applies to all three alert variants (success, danger, info), so any future message that needs HTML rendering can use `extra_tags='safe'` and will be rendered correctly.

## 📁 Files Modified

- **`support/views/seller_console.py`** — Added `open_issues` queryset and `open_issues_count` to `SellerConsoleView.get_context_data()`
- **`support/templates/seller_console.html`** — Added open issues badge in the header and open issues panel in the right sidebar
- **`templates/adminlte/lib/_messages.html`** — Added `safe` tag check so messages sent with `extra_tags='safe'` render as HTML

## 📚 Technical Details

- Terminal statuses are defined by the `ISSUE_STATUS_FINISHED_LIST` setting (a list of status slugs). If the setting is absent, an empty list is used and all issues are shown as open. This is consistent with how all other open-issue queries work across the codebase.
- Both `open_issues` and `open_issues_count` are passed to the template. Calling `.count()` on the queryset executes a `COUNT` SQL query rather than fetching all rows, which is efficient for the badge check. The full queryset is then evaluated only when the template iterates over it in the panel.
- The `|safe` filter is only applied when the `'safe'` tag is explicitly set by the view. Messages without that tag continue to be auto-escaped, preserving XSS protection for all other messages.

## 🧪 Manual Testing

1. **Happy path — contact with open issues:**
   - Open the seller console for a campaign and navigate to a contact that has at least one issue not in a terminal status.
   - **Verify:** A red badge appears next to the contact name showing the count and "check right panel". The right sidebar shows the "Contact's open issues" card with the issue's category, status, creation date, a view link, and full notes.

2. **Happy path — contact with no open issues:**
   - Navigate to a contact that has no issues, or whose issues are all in terminal statuses.
   - **Verify:** No badge appears next to the contact name. No open issues card appears in the right sidebar.

3. **Happy path — issue creation message renders as a link:**
   - From a contact detail page, create a new issue via the New Issue form.
   - **Verify:** After form submission, the success message at the top of the contact detail page shows "Issue #X created for contact Name" where `#X` is a clickable link that opens the issue detail view.

4. **Edge case — contact with a mix of open and terminal issues:**
   - Set up a contact with one open issue (non-terminal status) and one resolved issue (terminal status).
   - **Verify:** The badge shows "1 open issue(s)" and only the open issue appears in the right panel. The resolved issue is not shown.

5. **Edge case — issue with no notes:**
   - Navigate to a contact whose open issue has an empty notes field.
   - **Verify:** The issue appears in the panel with category, status, and date, but no notes block is rendered.

## 📝 Deployment Notes

- No database migrations required.
- No configuration changes needed, provided `ISSUE_STATUS_FINISHED_LIST` is already configured. If it is not set, all issues for the contact will be treated as open.
- Run `python manage.py compilemessages` after deploying if the new translatable strings (`open issue(s) — check right panel`, `Contact's open issues`, etc.) have been translated in the `.po` file.

## 🚀 Future Improvements

- Add a direct "Create issue" shortcut button in the open issues panel for quick issue logging from within the seller console
- Consider showing a count indicator on the contact list buttons in the collapsed "Contacts" card when a contact has open issues

---

- **Date:** 2026-03-25
- **Author:** Tanya Tree + Claude Sonnet 4.6
- **Branch:** t1069
- **Type:** UX Improvement
- **Modules affected:** Support, Seller Console, Issue Management
