# Documentation Writing Instructions

These instructions define how to document work done in the **utopia-crm** project.

## Two-Tier Documentation System

Every ticket produces **two outputs**:

1. **A short entry in `CHANGELOG.md`** (project root) — 3–5 bullet points summarizing what changed for operators and future developers. Prepended at the top, under a date/ticket heading.
2. **A detailed devnote in `docs/en/devnotes/` and `docs/es/devnotes/`** — full technical documentation of the change, including code context, testing scenarios, deployment notes, and design decisions.

---

## CHANGELOG.md Entry

### Format

Prepend to the top of `CHANGELOG.md` (below the `# Changelog` title if present):

```markdown
## YYYY-MM-DD — t#### Short description of change

- What changed and why (user/operator-facing language)
- Second notable change
- Deployment: migrations required / no migrations required
- **Author:** Name (+ AI model if applicable)
```

### Rules

- 3–5 bullet points maximum
- Plain language — no code snippets, no file paths
- Always include whether migrations are required
- The heading uses the ticket number if available, otherwise a short description

---

## Devnote Files

### File Naming

**English devnotes (`docs/en/devnotes/`)**

Format: `YYYY-MM-DD-descriptive-slug.md`

- Use the date the work was completed
- Use lowercase kebab-case for the slug
- If there is a ticket number, prefix the slug with it: `YYYY-MM-DD-t####-descriptive-slug.md`
- The slug should be a short English description of the change

Examples:

```text
2025-12-18-t990-subscription-reactivation-feature.md
2026-03-06-issue-confirmation-messages.md
2025-11-10-contact-list-csv-export-optimization.md
```

**Spanish devnotes (`docs/es/devnotes/`)**

Format: `YYYY-MM-DD-descriptive-slug.md`

- Use the **same date** as the English version
- If there is a ticket number, prefix the slug with it: `YYYY-MM-DD-t####-descriptive-slug.md`
- The slug should be a short **Spanish** description of the change

Examples:

```text
2025-12-18-t990-funcionalidad-reactivacion-suscripciones.md
2026-03-06-issue-confirmation-messages.md
2025-12-16-mejoras-filtros-registro-ventas.md
```

### Language Guidelines

- **English devnotes:** Written entirely in English
- **Spanish devnotes:** Written entirely in Spanish (neutral/standard Spanish)
- Both versions should contain the **same information** — the Spanish version is a translation, not a summary
- Code snippets, file paths, class names, and technical identifiers remain in their original form (do not translate code)

### Templates

Use the templates located in `docs/_templates/`:

- **English:** `en_devnote_template.md`
- **Spanish:** `es_devnote_template.md`

### Required Sections

Every devnote **must** include:

1. **Title and metadata header** — Title, date, type, component, impact (and ticket if applicable)
2. **🎯 Summary** — One paragraph explaining what and why
3. **✨ Changes** — Grouped by logical unit with file references
4. **📁 Files Modified** — Bulleted list of all changed files with brief descriptions
5. **🧪 Manual Testing** — At least one happy-path scenario and one edge case
6. **📝 Deployment Notes** — Migrations, config changes, post-deploy steps
7. **Footer with metadata** — Separated by `---`, includes date, branch, type, and modules affected

### Optional Sections

Include when relevant:

- **📁 Files Created** — Only if new files were added
- **📚 Technical Details** — For complex changes needing extra context
- **🚀 Future Improvements** — When there are clear enhancement opportunities
- **🎓 Design Decisions** — For architectural choices that may not be obvious

### Content Guidelines

#### Summary

- One concise paragraph
- Explain **what** was done and **why**
- Mention the problem/need that motivated the change

#### Changes

- Group by **logical unit**, not by file
- Number each logical change: `### 1. Name`, `### 2. Name` (under the `## ✨ Changes` heading)
- Reference the file path with each change
- Include code snippets **only** when they clarify key logic — do not dump entire functions
- Prefer showing the pattern or API, not the full implementation

#### Manual Testing

- Write scenarios as numbered lists with clear steps
- Each scenario should have a descriptive name
- End each scenario with a **Verify:** line stating the expected outcome
- Include at least:
  - One happy-path scenario (normal usage)
  - One edge case or validation scenario

#### Files Modified / Files Created

- Use bold for file paths: `**\`path/to/file.py\`**`
- Add a brief description after the em dash
- Separate "Modified" from "Created" into distinct sections

#### Deployment Notes

- Always state whether migrations are required
- List any management commands to run post-deploy
- Note configuration or fixture changes
- Mention dependencies on other branches or changes

#### Future Improvements

- Keep items brief (one line each)
- Focus on practical, actionable improvements
- Do not over-speculate — only include items that are clearly valuable

---

## Emoji in Section Headers

| Emoji | English Section | Spanish Section |
| --- | --- | --- |
| 🎯 | Summary | Resumen |
| ✨ | Changes | Cambios |
| 📁 | Files Modified / Files Created | Archivos Modificados / Creados |
| 📚 | Technical Details | Detalles Técnicos |
| 🧪 | Manual Testing | Pruebas Manuales |
| 📝 | Deployment Notes | Notas de Despliegue |
| 🚀 | Future Improvements | Mejoras Futuras |
| 🎓 | Design Decisions | Decisiones de Diseño |
| 📊 | Impact | Impacto |

## Metadata Footer

Every devnote ends with a metadata footer separated by `---`:

**English:**

```text
---

**Date:** 2026-03-06
**Author:** Jane Smith + Claude Sonnet 4.6
**Branch:** t1047
**Type:** Enhancement
**Modules affected:** Support, Issues
```

**Spanish:**

```text
---

**Fecha:** 2026-03-06
**Autor:** Jane Smith + Claude Sonnet 4.6
**Branch:** t1047
**Tipo de cambio:** Mejora
**Módulos afectados:** Support, Issues
```

## Markdown Formatting Rules

- One blank line before and after headings, lists, and fenced code blocks
- Every fenced code block must specify a language (`python`, `text`, `bash`, `html`, `sql`, etc.)
- Use ATX headings (`#`, `##`, `###`)
- Use `-` for unordered lists
- Use compact GitHub-style tables
- One H1 (`#`) per document (the title)

## Author Detection

```bash
git config user.name
```

- If working solo: `**Author:** John Doe`
- If working with AI: `**Author:** John Doe + Claude Sonnet 4.6`

## Git Branch as Issue Name

If no explicit issue/ticket name is provided, use the **git branch name** as the issue reference in both the CHANGELOG.md entry and the devnote metadata.

## Paired Devnotes

When creating devnotes for utopia-crm, **always create both** English and Spanish versions with the same content. The Spanish version is a full translation, not a subset.
