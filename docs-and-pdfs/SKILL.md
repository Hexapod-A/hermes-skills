---
name: docs-and-pdfs
description: Turn notes into clean branded PDF and DOCX files.
version: 1.0.0
author: John (Hexapod-A), 3xAgentic
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [pdf, docx, documents, markdown, branding, playwright]
    category: productivity
    related_skills: [outreach-and-proposals, flyer-studio]
---

# Docs and PDFs Skill

Converts Markdown (or HTML) notes into a branded document: black cover band with the logo, title and meta, clean white pages, the brand fonts, orange accents, tables, page numbers. Renders to PDF with headless Chromium and optionally to DOCX with pandoc. Checks fonts, contrast, overflowing tables/images and unfilled placeholders.

## When to Use

- "Make this into a PDF", reports, one-pagers, meeting notes, case studies, proposals, SOWs, invoices-as-documents.
- A Word version for a client who wants to edit (`--docx`).

## Prerequisites

- Repo Node deps (`npm install` in the repo root + `npx playwright install --with-deps chromium`).
- Optional: `pandoc` for DOCX, `poppler-utils` for PNG page previews and page counts.
- Brand kits are shared with flyer-studio (`../flyer-studio/brands/<brand>/brand.json`).

## How to Run

    node ${HERMES_SKILL_DIR}/scripts/build.mjs ~/docs/notes.md --out ~/docs/notes.pdf --brand 3xagentic --preview --docx

Prints JSON: `pdf`, `pages`, `errors`, `warnings`, `previews` (PNG per page), `docx`. Exit `2` on errors (and on warnings with `--strict`).

## Quick Reference

- Front matter at the top of the Markdown makes the cover:

      ---
      title: Q4 Automation Report
      subtitle: What we shipped and what's next
      client: Acme Dental
      prepared_by: John, 3xAgentic
      date: 2026-10-04
      ---

- `{{name}}` placeholders are filled from front matter or `--var name=value` (repeatable).
- `--page A4` for non-US clients (default Letter). HTML input is accepted as-is.
- Extra blocks in Markdown: `<div class="callout">…</div>`, `<div class="page-break"></div>`, `<div class="signature"><div>Client</div><div>3xAgentic</div></div>`.
- Example input: `examples/notes-example.md`.

## Procedure

1. Write or clean up the content as Markdown with `write_file`: short sections, `##` headings, tables for numbers, no walls of text.
2. Build with `--preview`.
3. Fix every `errors` item; resolve `unfilled placeholders` (ask the user for the missing facts; never invent them).
4. If your model has vision, check page 1 and the busiest page with `vision_analyze`: cover legible, no table running off the page, no orphan heading at a page bottom.
5. Deliver the PDF path (and DOCX if asked). Add `[[as_document]]` on the last line so it arrives as a file.

## Pitfalls

- The cover uses the light logo on black; a dark-on-light logo would vanish there. Keep the brand's dark-background logo as `logo.svg`.
- Very wide tables: split columns or switch to `--page A4` landscape via a custom `@page` rule in the HTML.
- DOCX is a plain, editable version (pandoc); the PDF is the designed one.

## Verification

- `node ${HERMES_SKILL_DIR}/scripts/build.mjs ${HERMES_SKILL_DIR}/examples/notes-example.md --out /tmp/notes.pdf` prints `"errors": []` and a page count.
