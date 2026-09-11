# Optional NotebookLM connector

Use `scripts/export_notebooklm_atlas.py` only after the user identifies a notebook and question. It is a convenience wrapper around an already-installed `notebooklm` CLI; it is not an SDK dependency.

The connector runs only these remote-reading actions after a local `auth check`:

- `notebooklm source list --notebook <id> --json`
- `notebooklm ask --notebook <id> --json <question>`

It does not call `source fulltext`, and it must never add `--new` to `ask`: current notebooklm-py versions define that option as deleting the notebook's server-side conversation before asking. Require `--yes` because a normal `ask` adds a conversation turn.

The connector writes `sources.json`, `analysis.json`, `manifest.json`, and `index.html` into the chosen output directory. Treat that directory as private data until reviewed. Use a new output directory by default; `--overwrite` is an explicit opt-in.
