---
name: reference-html-page
description: Retrieve the HTML page fragment corresponding to a cited PDF source path and page range in D-Concierge validator workspaces. Use when validating answers that cite readonly PDF references and you need to inspect the matching readonly HTML page content.
---

# Reference HTML Page

Use this skill when checking whether an answer is supported by cited PDF pages.
Do not infer PDF page content from filenames, metadata, or memory; inspect the corresponding HTML fragment.

## Workflow

1. Take the cited `references[].locator.path`, `start_page`, and `end_page`.
2. Run the bundled script from the validator workdir where `readonly/` exists:

```bash
python /home/minami/dev/D-Concierge/codex/.codex_validator/skills/custom/reference-html-page/scripts/extract_reference_html_pages.py \
  --pdf-path 'readonly/raw/pdf/<document>.pdf' \
  --start-page 21 \
  --end-page 22
```

3. Treat stdout as the only page content for validation. The script prints only the matching HTML `<section>` fragment(s).
4. If the script fails, the cited page content is not available from the workspace; do not mark the reference as verified.

## Notes

- `readonly/raw/pdf/<document>.pdf` maps to `readonly/html/<document>/index.html`.
- `readonly/<document>.pdf` maps to `readonly/html/<document>/index.html` when that HTML file exists.
- The script rejects absolute paths, parent-directory traversal, non-PDF paths, invalid page ranges, missing HTML, and missing pages.
