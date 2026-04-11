"""Unit tests for report AI authenticity checker."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def load_checker_module():
    root = Path(__file__).resolve().parent
    module_path = root / "scripts" / "report_ai_authenticity_check.py"
    spec = importlib.util.spec_from_file_location("report_ai_authenticity_check", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load report_ai_authenticity_check module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


checker = load_checker_module()


class TestLocalScoring(unittest.TestCase):
    """Validate heuristic scoring behavior."""

    def test_generic_paragraph_scores_higher(self) -> None:
        generic = (
            "This chapter aims to present a general approach that plays a crucial role in "
            "today's world. It should be noted that this system can be considered an "
            "effective solution in many cases. Furthermore, the process is generally "
            "important in terms of implementation and framework alignment."
        )

        score, reasons, _metrics = checker.compute_local_ai_likelihood(generic)
        self.assertGreaterEqual(score, 0.50)
        self.assertTrue(reasons)

    def test_specific_paragraph_scores_lower(self) -> None:
        specific = (
            "In Sprint 6, the backend sent queue payloads to n8n with a 10-second cooldown "
            "and critical escalation through Telegram. The QueueAnalyzer module produced "
            "lambda and mu estimates, while ThresholdDetector handled queue instability alerts "
            "for wait time under noisy RTSP feeds at 24 FPS."
        )

        score, _reasons, _metrics = checker.compute_local_ai_likelihood(specific)
        self.assertLess(score, 0.45)

    def test_score_combination_uses_external_weight(self) -> None:
        self.assertAlmostEqual(checker.combine_scores(0.60, 0.20), 0.48, places=2)
        self.assertAlmostEqual(checker.combine_scores(0.42, None), 0.42, places=5)


class TestExternalFallback(unittest.TestCase):
    """Ensure external checks remain optional and non-blocking."""

    def test_external_score_not_configured(self) -> None:
        with patch.dict(os.environ, {"AI_DETECTOR_API_URL": "", "AI_DETECTOR_API_KEY": ""}, clear=False):
            score, note = checker.get_external_ai_score("sample text", timeout_seconds=1.0)
        self.assertIsNone(score)
        self.assertEqual(note, "external_not_configured")


class TestReportGeneration(unittest.TestCase):
    """Validate end-to-end report output generation."""

    def test_run_report_analysis_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_dir = temp_path / "chapters"
            source_dir.mkdir(parents=True, exist_ok=True)

            tex_content = """
            This chapter aims to provide a general approach that plays a crucial role in today's world.
            It should be noted that this system can be considered effective in many cases.
            Furthermore, the implementation process is generally speaking important in terms of
            framework alignment, solution quality, and technology consistency across a wide range
            of operational contexts where no specific metric is explicitly highlighted.

            In Sprint 5, the frontend consumed WebSocket feed status events and rendered KPI updates.
            """
            (source_dir / "sample.tex").write_text(tex_content, encoding="utf-8")

            output_dir = temp_path / "quality-reports"
            with patch.dict(os.environ, {"AI_DETECTOR_API_URL": "", "AI_DETECTOR_API_KEY": ""}, clear=False):
                summary = checker.run_report_analysis(
                    source_path=source_dir,
                    output_dir=output_dir,
                    min_score=0.35,
                    external_timeout=1.0,
                )

            self.assertEqual(summary.scanned_files, 1)
            self.assertGreaterEqual(summary.flagged_paragraphs, 1)
            self.assertEqual(summary.external_mode, "local-only")

            findings_path = Path(summary.findings_path)
            suggestions_path = Path(summary.suggestions_path)
            self.assertTrue(findings_path.exists())
            self.assertTrue(suggestions_path.exists())

            findings_payload = json.loads(findings_path.read_text(encoding="utf-8"))
            self.assertIn("metadata", findings_payload)
            self.assertIn("findings", findings_payload)
            self.assertGreaterEqual(len(findings_payload["findings"]), 1)

            suggestions_content = suggestions_path.read_text(encoding="utf-8")
            self.assertIn("Suggested Rewrite", suggestions_content)
            self.assertIn("Finding 1", suggestions_content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
