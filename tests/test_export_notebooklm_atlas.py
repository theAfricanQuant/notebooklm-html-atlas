"""Tests for the optional notebooklm-py bridge without contacting NotebookLM."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
CONNECTOR = REPOSITORY / "scripts/export_notebooklm_atlas.py"


class NotebookLMConnectorTests(unittest.TestCase):
    def test_exports_json_and_never_uses_destructive_new_conversation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / "fake-notebooklm"
            calls = root / "calls.txt"
            fake.write_text(textwrap.dedent("""\
                #!/usr/bin/env python3
                import json, os, sys
                with open(os.environ['FAKE_CALLS'], 'a', encoding='utf-8') as handle:
                    handle.write(json.dumps(sys.argv[1:]) + '\\n')
                if sys.argv[-2:] == ['auth', 'check']:
                    raise SystemExit(0)
                if 'source' in sys.argv and 'list' in sys.argv:
                    print(json.dumps({'sources': [{'id': 's1', 'title': 'A source', 'type': 'SourceType.WEB_PAGE', 'url': 'https://example.test'}]}))
                    raise SystemExit(0)
                if 'ask' in sys.argv:
                    print(json.dumps({'question': 'Question?', 'answer': 'Answer [1].', 'references': [{'source_id': 's1', 'cited_text': 'private excerpt'}]}))
                    raise SystemExit(0)
                raise SystemExit(9)
            """), encoding="utf-8")
            fake.chmod(0o755)
            output = root / "private-export"
            environment = {**os.environ, "FAKE_CALLS": str(calls)}
            completed = subprocess.run(
                ["python3", str(CONNECTOR), "--notebooklm-command", str(fake), "--notebook", "abc", "--question", "Question?", "--output-dir", str(output), "--title", "Test atlas", "--yes"],
                capture_output=True, text=True, check=True, env=environment,
            )
            recorded = calls.read_text(encoding="utf-8")
            report = (output / "index.html").read_text(encoding="utf-8")
            self.assertIn("CREATED:", completed.stdout)
            self.assertTrue((output / "sources.json").is_file())
            self.assertTrue((output / "analysis.json").is_file())
            self.assertTrue((output / "manifest.json").is_file())
            self.assertIn("Open source", report)
            self.assertNotIn("private excerpt", report)
            self.assertNotIn("--new", recorded)
            self.assertIn('"ask"', recorded)

    def test_requires_explicit_confirmation(self) -> None:
        completed = subprocess.run(
            ["python3", str(CONNECTOR), "--notebook", "abc", "--question", "Question?", "--output-dir", "/tmp/unused-atlas-test"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("--yes is required", completed.stderr)


if __name__ == "__main__":
    unittest.main()
