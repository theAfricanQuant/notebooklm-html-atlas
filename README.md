# NotebookLM HTML Atlas

A small, agent-neutral skill for turning NotebookLM JSON exports into a beautiful, standalone HTML research report.

It has no runtime dependencies beyond **Python 3.10+**. No Obsidian, Mermaid, JavaScript framework, Google login, API key, or package installation is required to build the report.

The generator is deliberately separate from data acquisition: use whichever authorized NotebookLM method you already have to create JSON exports, then give those files to this repository. It never sends data anywhere.

## What people get

- polished, static HTML that can be opened locally or hosted anywhere
- semantic rendering of NotebookLM's Markdown answers
- source-linked citations
- a native SVG causal chart for NotebookLM's exported causal chains
- compact source cards with **original links only** — no copied transcripts, guides, or evidence excerpts
- tests and synthetic inputs that run without an account

## Fast start

```bash
git clone https://github.com/<owner>/notebooklm-html-atlas.git
cd notebooklm-html-atlas
python3 -m unittest tests/test_build_html_report.py -v

python3 scripts/build_html_report.py \
  --sources examples/synthetic-sources.json \
  --qa examples/synthetic-question.json \
  --title "Synthetic research atlas" \
  --output ./output/research-atlas.html
```

Open `output/research-atlas.html` in a browser. The repository includes no private NotebookLM data; the examples are synthetic.

## Optional: connect an already-authorized notebooklm-py CLI

If `notebooklm` is already installed and authenticated on the local machine, the optional bridge can export a notebook's source list, ask one normal question, and build a report in one command:

```bash
python3 scripts/export_notebooklm_atlas.py \
  --notebook <notebook-id> \
  --question "What are the main findings?" \
  --output-dir ./output/private-notebook-export \
  --title "My research atlas" \
  --yes
```

This bridge is not a bundled dependency and does not install `notebooklm-py`. It performs a local authentication check, calls `source list --json`, then `ask --json`; it intentionally never uses `ask --new`, which deletes the active server-side conversation. `--yes` is required because asking adds a normal conversation turn. The resulting `sources.json` and `analysis.json` can be private—review them before sharing or committing.

## Use your NotebookLM exports

Create a source-list JSON export and one or more Q&A JSON exports through your existing, authorized NotebookLM workflow. Then run:

```bash
python3 scripts/build_html_report.py \
  --sources /path/to/sources.json \
  --qa /path/to/analysis.json \
  --title "My research atlas" \
  --output ./output/my-research-atlas.html
```

Repeat `--qa /path/to/another-answer.json` to add more answer sections. The generator accepts local files only.

## Use with AI agents and harnesses

This repository is itself the portable artifact. Point an agent at [SKILL.md](SKILL.md), or use the optional installer to copy the skill into a common local discovery directory:

```bash
./install.sh --agent codex
./install.sh --agent claude
# or choose an exact skill directory for any other harness
./install.sh --target /path/to/skills/notebooklm-html-atlas
```

The installer copies `SKILL.md`, `references/`, and `scripts/`; it never downloads dependencies or contacts a service. If your harness uses another skill directory, use `--target` or give it this cloned repository directly.

## Data boundaries

The generated page keeps the report's answer text and links to original sources. It intentionally does **not** embed source summaries, full source content, or NotebookLM evidence excerpts. The citation links indicate the source NotebookLM associated with a claim; they are not an independent verification.

Before publishing a generated report, check that its title, Q&A text, source titles, and original URLs are safe to share.

## Repository layout

```text
SKILL.md                       Agent instructions and safety boundaries
scripts/build_html_report.py   Offline report generator
tests/                          Regression test
examples/                       Synthetic inputs and generated example
install.sh                      Optional dependency-free skill copier
```

## Publishing this repository

Initialize/commit locally, then choose the GitHub owner and visibility before creating a remote. For example, once you have chosen them:

```bash
gh repo create <owner>/notebooklm-html-atlas --source=. --remote=origin --push
```

Use `--public` or `--private` explicitly according to the audience. Do not push live NotebookLM exports, browser profiles, cookies, or generated reports containing private research.

## License

MIT. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
