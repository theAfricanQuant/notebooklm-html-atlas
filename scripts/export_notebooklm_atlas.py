#!/usr/bin/env python3
"""Optional bridge from an authorized NotebookLM CLI session to an HTML Atlas.

The bridge is intentionally separate from the report renderer.  It invokes an
already-installed `notebooklm` command, writes its JSON responses to a local
folder, and builds a static report from those files.  It never installs a
package, opens a browser, exports source full text, or starts a fresh
conversation.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "scripts" / "build_html_report.py"


def command_base(args: argparse.Namespace) -> list[str]:
    command = [args.notebooklm_command]
    if args.profile:
        command.extend(["--profile", args.profile])
    return command


def run(command: list[str], *, expect_json: bool = False) -> str | dict:
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as error:
        raise RuntimeError(
            f"NotebookLM command not found: {command[0]!r}. Install and authenticate notebooklm-py separately, or pass --notebooklm-command."
        ) from error
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"NotebookLM command failed with exit code {error.returncode}: {' '.join(command[1:3])}") from error
    if not expect_json:
        return completed.stdout
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("NotebookLM did not return valid JSON. Ensure the installed CLI supports --json.") from error


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export an authorized NotebookLM notebook's source list and one answer, then build a local HTML Atlas."
    )
    parser.add_argument("--notebook", required=True, help="NotebookLM notebook ID or unique prefix.")
    parser.add_argument("--question", required=True, help="Question to send to the selected notebook.")
    parser.add_argument("--output-dir", required=True, help="New or empty directory for private JSON exports and index.html.")
    parser.add_argument("--title", default="NotebookLM Research Atlas", help="Title shown in the generated report.")
    parser.add_argument("--source", action="append", default=[], help="Optional source ID to limit the question to; repeat as needed.")
    parser.add_argument("--profile", help="Optional notebooklm-py profile name.")
    parser.add_argument("--notebooklm-command", default="notebooklm", help="Path or command name for an already-installed NotebookLM CLI.")
    parser.add_argument("--overwrite", action="store_true", help="Allow replacement of connector output files in --output-dir.")
    parser.add_argument("--yes", action="store_true", help="Confirm that the connector may send this question to NotebookLM.")
    args = parser.parse_args()

    if not args.yes:
        parser.error("--yes is required because this sends a question to NotebookLM and adds a normal conversation turn. The connector never uses --new.")
    output_dir = Path(args.output_dir).expanduser().resolve()
    targets = [output_dir / name for name in ("sources.json", "analysis.json", "manifest.json", "index.html")]
    if any(target.exists() for target in targets) and not args.overwrite:
        parser.error("connector output already exists; choose a new --output-dir or pass --overwrite")
    output_dir.mkdir(parents=True, exist_ok=True)

    base = command_base(args)
    # This local check validates stored credentials but deliberately does not make a token/network test.
    run(base + ["auth", "check"])
    sources = run(base + ["source", "list", "--notebook", args.notebook, "--json"], expect_json=True)
    ask_command = base + ["ask", "--notebook", args.notebook, "--json"]
    for source_id in args.source:
        ask_command.extend(["--source", source_id])
    ask_command.append(args.question)
    answer = run(ask_command, expect_json=True)

    sources_path = output_dir / "sources.json"
    answer_path = output_dir / "analysis.json"
    write_json(sources_path, sources)
    write_json(answer_path, answer)
    manifest = {
        "connector": "notebooklm-html-atlas",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "notebook_id": args.notebook,
        "question": args.question,
        "source_filter": args.source,
        "files": {"sources": sources_path.name, "analysis": answer_path.name, "report": "index.html"},
        "data_boundary": "This folder may contain private NotebookLM exports. Do not commit it unless reviewed.",
    }
    write_json(output_dir / "manifest.json", manifest)

    subprocess.run(
        [sys.executable, str(RENDERER), "--sources", str(sources_path), "--qa", str(answer_path), "--title", args.title, "--output", str(output_dir / "index.html")],
        check=True,
    )
    print(f"CREATED: {output_dir / 'index.html'}")
    print("NOTE: sources.json and analysis.json may be private; review them before sharing or committing.")


if __name__ == "__main__":
    main()
