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
        self.assertIn('<tspan x="728" y="145">1 portable</tspan><tspan x="728" dy="20">page</tspan>', page)
        self.assertIn('href="#source-', page)
        self.assertIn('href="https://example.test/focus"', page)
        self.assertNotIn('href="javascript:alert(1)"', page)
        self.assertIn("&lt;script&gt;not executable&lt;/script&gt;", page)
        self.assertNotIn("<script>not executable</script>", page)


    def test_embeds_reviewed_svg_and_rejects_unsafe_svg(self) -> None:
        sources = {"sources": [{"id": "s1", "title": "Source", "type": "SourceType.WEB_PAGE", "url": "https://example.test"}]}
        qa = {"question": "Question?", "answer": "Answer.", "references": []}
        safe_svg = (
            '<svg viewBox="0 0 400 120" role="img" aria-labelledby="causal-title causal-desc">'
            '<title id="causal-title">Causal map</title><desc id="causal-desc">A reviewed causal relationship map.</desc>'
            '<defs><marker id="arrow"><path d="M0 0L8 4L0 8Z"/></marker></defs>'
            '<path d="M40 60H340" marker-end="url(#arrow)"/><rect x="20" y="36" width="80" height="40"/>'
            '<rect x="280" y="36" width="80" height="40"/></svg>'
        )
        unsafe_svg = '<svg viewBox="0 0 1 1"><script>alert(1)</script></svg>'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources_path, qa_path, output = root / "sources.json", root / "question.json", root / "report.html"
            diagram, unsafe = root / "diagram.svg", root / "unsafe.svg"
            sources_path.write_text(json.dumps(sources), encoding="utf-8")
            qa_path.write_text(json.dumps(qa), encoding="utf-8")
            diagram.write_text(safe_svg, encoding="utf-8")
            unsafe.write_text(unsafe_svg, encoding="utf-8")
            subprocess.run([
                "python3", str(SCRIPT), "--sources", str(sources_path), "--qa", str(qa_path),
                "--diagram", f"Causal relationships={diagram}", "--title", "Visual test", "--output", str(output),
            ], check=True, capture_output=True, text=True)
            page = output.read_text(encoding="utf-8")
            rejected = subprocess.run([
                "python3", str(SCRIPT), "--sources", str(sources_path), "--diagram", str(unsafe),
                "--title", "Visual test", "--output", str(root / "unsafe.html"),
            ], capture_output=True, text=True)
        self.assertIn('class="diagram-asset"', page)
        self.assertIn('atlas-diagram-1-causal-title', page)
        self.assertIn('url(#atlas-diagram-1-arrow)', page)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("unsafe or external SVG", rejected.stderr)


if __name__ == "__main__":
    unittest.main()
