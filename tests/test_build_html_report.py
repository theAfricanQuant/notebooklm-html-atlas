"""End-to-end tests for the platform-neutral report generator CLI."""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
SCRIPT = REPOSITORY / "scripts/build_html_report.py"


class BuildHtmlReportTests(unittest.TestCase):
    def test_cli_creates_citation_linked_safe_report(self) -> None:
        """Users receive a portable page where cited claims link to real sources."""
        sources = {
            "notebook_id": "notebook-1",
            "sources": [
                {
                    "id": "video-1",
                    "title": "Focus & deliberate practice",
                    "type": "SourceType.YOUTUBE",
                    "url": "https://example.test/focus",
                    "created_at": "2026-09-11T12:00:00Z",
                },
                {
                    "id": "pdf-2",
                    "title": "<script>not executable</script>",
                    "type": "SourceType.PDF",
                    "url": "javascript:alert(1)",
                },
            ],
        }
        qa = {
            "question": "What supports deep focus?",
            "answer": "Protect uninterrupted time [1] and review the evidence [2].",
            "references": [
                {"source_id": "video-1", "cited_text": "Long, uninterrupted periods support sustained focus."},
                {"source_id": "pdf-2", "cited_text": "Deliberate practice needs feedback and recovery."},
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources_path, qa_path, output = root / "sources.json", root / "question.json", root / "report.html"
            sources_path.write_text(json.dumps(sources), encoding="utf-8")
            qa_path.write_text(json.dumps(qa), encoding="utf-8")

            completed = subprocess.run(
                ["python3", str(SCRIPT), "--sources", str(sources_path), "--qa", str(qa_path), "--title", "Focus test", "--output", str(output)],
                capture_output=True,
                text=True,
                check=True,
            )
            page = output.read_text(encoding="utf-8")

        self.assertIn("CREATED:", completed.stdout)
        self.assertTrue(page.startswith("<!doctype html>"))
        self.assertNotIn("Long, uninterrupted periods support sustained focus.", page)
        self.assertNotIn("Deliberate practice needs feedback and recovery.", page)
        self.assertNotIn("Evidence excerpt", page)
        self.assertIn("Open source", page)
        self.assertIn('href="#source-', page)
        self.assertIn('href="https://example.test/focus"', page)
        self.assertNotIn('href="javascript:alert(1)"', page)
        self.assertIn("&lt;script&gt;not executable&lt;/script&gt;", page)
        self.assertNotIn("<script>not executable</script>", page)


if __name__ == "__main__":
    unittest.main()
