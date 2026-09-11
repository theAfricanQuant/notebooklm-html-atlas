# Agent entry point

Read [SKILL.md](SKILL.md) before changing or running this repository. The base generator is intentionally offline and needs only Python 3.10+. The optional `scripts/export_notebooklm_atlas.py` bridge may invoke an already-authorized NotebookLM CLI only when the user explicitly requests it and supplies a notebook/question; it must never use `ask --new`. Keep source cards link-only and do not add private NotebookLM exports to version control.

For user-requested research visuals, invoke the installed `diagram-design` skill and follow `references/diagram-design-handoff.md`; embed only its reviewed static SVG output through `--diagram`.
