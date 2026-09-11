---
name: notebooklm-html-atlas
description: Turn NotebookLM JSON exports into a standalone, citation-linked HTML research atlas. Use when someone needs a readable, shareable report without Obsidian, Mermaid, a server, or copied source transcripts.
---

# NotebookLM HTML Atlas

Create a static research report from a NotebookLM source-list export and zero or more Q&A JSON exports. The repository is agent-neutral: an AI harness can read this file and invoke the included Python script directly.

## Guardrails

- The report builder is offline and standard-library-only. It never signs in to Google, calls NotebookLM, or installs packages.
- Obtain JSON exports only through the user's already-authorized NotebookLM workflow. Never include cookies, account data, full source text, or private exports in a public repository.
- Source cards are link-only: preserve title/type/date and the original URL, but do not copy source summaries or evidence excerpts into the HTML.
- Citations link claims to their source cards. Explain that a citation represents the evidence NotebookLM returned, not independent fact-checking.
- Use native SVG for causal diagrams; do not add Mermaid or a JavaScript chart dependency.

## Build from existing exports

```bash
python3 scripts/build_html_report.py \
  --sources /absolute/path/sources.json \
  --qa /absolute/path/analysis.json \
  --title "Research Atlas" \
  --output ./output/research-atlas.html
```

Add `--qa` again for each additional Q&A export. Open the generated HTML locally and confirm source links before sharing it.

## Optional: export with an already-authorized notebooklm-py CLI

Only use the connector when the user explicitly wants the agent to send the supplied question to their selected NotebookLM notebook. It requires a separately installed and authenticated `notebooklm` command; this repository never installs or bundles it.

```bash
python3 scripts/export_notebooklm_atlas.py \
  --notebook <notebook-id> \
  --question "What are the main findings?" \
  --output-dir ./output/private-notebook-export \
  --title "Research Atlas" \
  --yes
```

The connector uses `notebooklm auth check`, `source list --json`, and `ask --json`. It never uses `ask --new`, which deletes the current server-side conversation. The output directory contains private JSON exports; review it before sharing or committing.

## What the output contains

- an inline SVG import-to-report flow
- a native SVG causal cascade when NotebookLM exports an ASCII bracket-and-arrow relationship block
- semantic HTML for headings, paragraphs, lists, emphasis, code, and citation links
- a compact source library with original-source links only

## Improve safely

Keep the report generator dependency-free unless a concrete need outweighs portability. Add tests for every new rendering behaviour. Do not commit live NotebookLM exports or generated reports containing private research.
