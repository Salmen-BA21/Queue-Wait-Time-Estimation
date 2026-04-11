#!/usr/bin/env python3
"""Analyze LaTeX report chapters for AI-like writing patterns.

This tool does not attempt to prove authorship. It produces confidence-based
suspicion scores using local heuristics and optional external scoring, then
writes non-destructive rewrite suggestions.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request

# Phrases often overused in machine-generated text.
CLICHE_PHRASES = (
    "this chapter aims to",
    "this chapter seeks to",
    "this chapter focuses on",
    "in today's world",
    "it is worth noting that",
    "it should be noted that",
    "plays a crucial role",
    "it can be observed that",
    "it is evident that",
    "in conclusion",
    "to sum up",
    "moreover",
    "furthermore",
)

HEDGE_PHRASES = (
    "it may be considered",
    "it can be argued",
    "it appears that",
    "it seems that",
    "potentially",
    "arguably",
    "generally speaking",
    "in many cases",
)

FILLER_PHRASES = (
    "in order to",
    "as mentioned earlier",
    "at the end of the day",
    "from a practical standpoint",
    "in terms of",
    "a wide range of",
)

GENERIC_WORDS = {
    "system",
    "process",
    "solution",
    "approach",
    "framework",
    "technology",
    "platform",
    "method",
    "implementation",
}

PROJECT_SPECIFIC_TERMS = {
    "datadoit",
    "yolo",
    "bytetrack",
    "fastapi",
    "n8n",
    "telegram",
    "rtsp",
    "onvif",
    "queue",
    "stability",
    "lambda",
    "mu",
    "sprint",
}

REWRITE_REPLACEMENTS = {
    r"\bThis chapter (aims|seeks|focuses) to\b": "This chapter presents",
    r"\bIt should be noted that\b": "Notably,",
    r"\bIt is worth noting that\b": "Notably,",
    r"\bIn today's world\b": "In this project context",
    r"\bplays a crucial role\b": "is important",
    r"\bIn conclusion\b": "Overall",
}


@dataclass
class ParagraphBlock:
    """A paragraph candidate with file-relative line information."""

    text: str
    start_line: int
    end_line: int


@dataclass
class Finding:
    """One flagged paragraph and rewrite suggestion."""

    file: str
    start_line: int
    end_line: int
    level: str
    score: float
    local_score: float
    external_score: float | None
    reasons: list[str]
    excerpt: str
    suggested_rewrite: str


@dataclass
class AnalysisSummary:
    """Top-level run summary."""

    scanned_files: int
    flagged_paragraphs: int
    high_findings: int
    medium_findings: int
    low_findings: int
    findings_path: str
    suggestions_path: str
    external_mode: str


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def split_sentences(text: str) -> list[str]:
    candidates = re.split(r"(?<=[.!?])\s+", normalize_spaces(text))
    return [segment.strip() for segment in candidates if segment.strip()]


def strip_latex_commands(text: str) -> str:
    """Best-effort conversion from LaTeX source to analyzable plain text."""
    no_comments = re.sub(r"%.*", "", text)
    no_env = re.sub(r"\\(?:begin|end)\{[^}]+\}", " ", no_comments)
    no_commands = re.sub(r"\\[a-zA-Z@*]+", " ", no_env)
    no_escaped = re.sub(r"\\.", " ", no_commands)
    cleaned = no_escaped.replace("{", " ").replace("}", " ")
    return normalize_spaces(cleaned)


def extract_paragraphs(tex_text: str) -> list[ParagraphBlock]:
    """Split text into paragraph-like blocks preserving line spans."""
    blocks: list[ParagraphBlock] = []
    buffer: list[str] = []
    start_line: int | None = None

    def flush(end_line: int) -> None:
        nonlocal buffer, start_line
        if not buffer or start_line is None:
            buffer = []
            start_line = None
            return
        text = "\n".join(buffer).strip()
        if text:
            blocks.append(ParagraphBlock(text=text, start_line=start_line, end_line=end_line))
        buffer = []
        start_line = None

    lines = tex_text.splitlines()
    for index, line in enumerate(lines, start=1):
        if line.strip() == "":
            flush(index - 1)
            continue
        if start_line is None:
            start_line = index
        buffer.append(line)

    flush(len(lines))
    return blocks


def is_analyzable_paragraph(block: ParagraphBlock) -> bool:
    lowered = block.text.lower()
    # Skip structural or purely command-heavy regions.
    structural_markers = (
        "\\begin{table}",
        "\\end{table}",
        "\\begin{figure}",
        "\\end{figure}",
        "\\toprule",
        "\\midrule",
        "\\bottomrule",
    )
    if any(marker in lowered for marker in structural_markers):
        return False

    plain_text = strip_latex_commands(block.text)
    word_count = len(re.findall(r"\b\w+\b", plain_text))
    if word_count < 35:
        return False

    letter_count = sum(1 for char in plain_text if char.isalpha())
    if not plain_text:
        return False
    letter_ratio = letter_count / max(1, len(plain_text))
    return letter_ratio >= 0.45


def count_phrase_hits(text_lower: str, phrases: tuple[str, ...]) -> int:
    return sum(text_lower.count(phrase) for phrase in phrases)


def starter_repeat_ratio(sentences: list[str]) -> float:
    if len(sentences) < 3:
        return 0.0
    starters = []
    for sentence in sentences:
        tokens = re.findall(r"\b\w+\b", sentence.lower())
        if len(tokens) >= 2:
            starters.append(" ".join(tokens[:2]))
        elif tokens:
            starters.append(tokens[0])
    if len(starters) < 3:
        return 0.0
    repeated = len(starters) - len(set(starters))
    return max(0.0, repeated / len(starters))


def passive_count(text_lower: str) -> int:
    pattern = r"\b(?:is|are|was|were|be|been|being)\s+\w+(?:ed|en)\b"
    return len(re.findall(pattern, text_lower))


def long_sentence_ratio(sentences: list[str]) -> float:
    if not sentences:
        return 0.0
    long_count = 0
    for sentence in sentences:
        word_count = len(re.findall(r"\b\w+\b", sentence))
        if word_count >= 35:
            long_count += 1
    return long_count / len(sentences)


def compute_local_ai_likelihood(paragraph_text: str) -> tuple[float, list[str], dict[str, float]]:
    plain = strip_latex_commands(paragraph_text)
    lowered = plain.lower()
    words = re.findall(r"\b\w+\b", lowered)
    if not words:
        return 0.0, [], {}

    sentences = split_sentences(plain)
    cliche_hits = count_phrase_hits(lowered, CLICHE_PHRASES)
    hedge_hits = count_phrase_hits(lowered, HEDGE_PHRASES)
    filler_hits = count_phrase_hits(lowered, FILLER_PHRASES)
    repeated_starters = starter_repeat_ratio(sentences)
    passive_hits = passive_count(lowered)
    long_ratio = long_sentence_ratio(sentences)

    generic_hits = sum(1 for token in words if token in GENERIC_WORDS)
    generic_ratio = generic_hits / max(1, len(words))
    specificity_hits = sum(1 for term in PROJECT_SPECIFIC_TERMS if term in lowered)
    numeric_hits = len(re.findall(r"\b\d+(?:\.\d+)?\b", plain))

    score = 0.0
    score += min(0.24, 0.06 * cliche_hits)
    score += min(0.20, 0.05 * hedge_hits)
    score += min(0.16, 0.04 * filler_hits)
    score += min(0.14, repeated_starters * 0.35)
    score += min(0.14, 0.03 * passive_hits)
    score += min(0.08, long_ratio * 0.08)

    if specificity_hits == 0:
        score += 0.12
    if generic_ratio >= 0.11:
        score += min(0.12, generic_ratio * 0.55)
    if numeric_hits == 0 and len(words) >= 80:
        score += 0.08

    score = max(0.0, min(1.0, score))

    reasons: list[str] = []
    if cliche_hits:
        reasons.append(f"Contains {cliche_hits} cliche transition phrase(s).")
    if hedge_hits:
        reasons.append(f"Contains {hedge_hits} hedge phrase(s).")
    if filler_hits:
        reasons.append(f"Contains {filler_hits} filler phrase(s).")
    if repeated_starters >= 0.25:
        reasons.append("Repeats similar sentence starters.")
    if passive_hits >= 3:
        reasons.append("Uses frequent passive constructions.")
    if specificity_hits == 0:
        reasons.append("Lacks project-specific details.")
    if generic_ratio >= 0.11:
        reasons.append("Uses a high ratio of generic terminology.")
    if numeric_hits == 0 and len(words) >= 80:
        reasons.append("No concrete numeric evidence in a long paragraph.")

    metrics = {
        "cliche_hits": float(cliche_hits),
        "hedge_hits": float(hedge_hits),
        "filler_hits": float(filler_hits),
        "repeated_starter_ratio": repeated_starters,
        "passive_hits": float(passive_hits),
        "long_sentence_ratio": long_ratio,
        "generic_ratio": generic_ratio,
        "specificity_hits": float(specificity_hits),
        "numeric_hits": float(numeric_hits),
    }
    return score, reasons, metrics


def parse_external_score(payload: dict[str, Any]) -> float | None:
    candidates: list[Any] = [
        payload.get("score"),
        payload.get("probability"),
        payload.get("ai_score"),
        payload.get("aiProbability"),
    ]

    nested_data = payload.get("data")
    if isinstance(nested_data, dict):
        candidates.extend(
            [
                nested_data.get("score"),
                nested_data.get("probability"),
                nested_data.get("ai_score"),
            ]
        )

    for candidate in candidates:
        if isinstance(candidate, (int, float)):
            value = float(candidate)
            if value > 1.0 and value <= 100.0:
                value = value / 100.0
            if 0.0 <= value <= 1.0:
                return value
    return None


def get_external_ai_score(text: str, timeout_seconds: float) -> tuple[float | None, str | None]:
    api_url = os.getenv("AI_DETECTOR_API_URL")
    api_key = os.getenv("AI_DETECTOR_API_KEY")
    if not api_url or not api_key:
        return None, "external_not_configured"

    payload = json.dumps({"text": text}).encode("utf-8")
    req = request.Request(
        api_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
            parsed = json.loads(body)
    except (TimeoutError, error.URLError, error.HTTPError, json.JSONDecodeError) as exc:
        return None, f"external_error:{exc}"

    if not isinstance(parsed, dict):
        return None, "external_response_not_object"

    score = parse_external_score(parsed)
    if score is None:
        return None, "external_score_missing"
    return score, None


def combine_scores(local_score: float, external_score: float | None) -> float:
    if external_score is None:
        return local_score
    return (0.70 * local_score) + (0.30 * external_score)


def level_from_score(score: float, min_score: float) -> str | None:
    if score < min_score:
        return None
    if score >= 0.75:
        return "HIGH"
    if score >= 0.55:
        return "MEDIUM"
    return "LOW"


def build_rewrite_suggestion(original_text: str, reasons: list[str]) -> str:
    suggestion = original_text
    for pattern, replacement in REWRITE_REPLACEMENTS.items():
        suggestion = re.sub(pattern, replacement, suggestion, flags=re.IGNORECASE)

    suggestion = normalize_spaces(suggestion)

    # Reduce stacked transition adverbs.
    suggestion = re.sub(r"\b(Moreover|Furthermore|Additionally),?\s+", "", suggestion, flags=re.IGNORECASE)

    if "Lacks project-specific details." in reasons:
        suggestion += " [Add one concrete detail: module name, metric value, sprint artifact, or citation.]"
    if "Uses frequent passive constructions." in reasons:
        suggestion += " [Prefer active voice for key actions and ownership.]"

    return suggestion


def relative_to_workspace(path: Path, workspace_root: Path) -> str:
    try:
        return str(path.relative_to(workspace_root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def discover_tex_files(source_path: Path) -> list[Path]:
    if source_path.is_file() and source_path.suffix.lower() == ".tex":
        return [source_path]
    if source_path.is_dir():
        return sorted(source_path.glob("*.tex"))
    return []


def truncate_excerpt(text: str, max_chars: int = 340) -> str:
    compact = normalize_spaces(text)
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3] + "..."


def analyze_file(
    tex_file: Path,
    workspace_root: Path,
    min_score: float,
    external_timeout: float,
) -> tuple[list[Finding], str]:
    content = tex_file.read_text(encoding="utf-8")
    findings: list[Finding] = []
    external_mode = "local-only"

    for block in extract_paragraphs(content):
        if not is_analyzable_paragraph(block):
            continue

        local_score, reasons, _metrics = compute_local_ai_likelihood(block.text)
        if local_score < max(0.20, min_score * 0.45):
            # Skip clearly low-risk blocks without external lookup.
            continue

        external_score, external_note = get_external_ai_score(block.text, external_timeout)
        if external_score is not None:
            external_mode = "hybrid"
        if external_note and external_note.startswith("external_error"):
            external_mode = "hybrid-with-errors"

        combined_score = combine_scores(local_score, external_score)
        level = level_from_score(combined_score, min_score)
        if level is None:
            continue

        finding = Finding(
            file=relative_to_workspace(tex_file, workspace_root),
            start_line=block.start_line,
            end_line=block.end_line,
            level=level,
            score=round(combined_score, 3),
            local_score=round(local_score, 3),
            external_score=round(external_score, 3) if external_score is not None else None,
            reasons=reasons or ["Pattern score exceeded configured threshold."],
            excerpt=truncate_excerpt(block.text),
            suggested_rewrite=build_rewrite_suggestion(block.text, reasons),
        )
        findings.append(finding)

    return findings, external_mode


def write_json_report(path: Path, findings: list[Finding], metadata: dict[str, Any]) -> None:
    payload = {
        "metadata": metadata,
        "findings": [asdict(item) for item in findings],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_suggestions_markdown(path: Path, findings: list[Finding], metadata: dict[str, Any]) -> None:
    lines: list[str] = []
    lines.append("# Report AI Authenticity Suggestions")
    lines.append("")
    lines.append(f"- Generated at: {metadata['generated_at']}")
    lines.append(f"- Source scope: {metadata['source']}")
    lines.append(f"- Scanned files: {metadata['scanned_files']}")
    lines.append(f"- Flagged paragraphs: {metadata['flagged_paragraphs']}")
    lines.append(f"- Detection mode: {metadata['external_mode']}")
    lines.append("")
    lines.append("> Findings indicate AI-like style risk, not definitive authorship proof.")
    lines.append("")

    if not findings:
        lines.append("No paragraphs crossed the configured threshold.")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    for index, finding in enumerate(findings, start=1):
        lines.append(f"## Finding {index}")
        lines.append("")
        lines.append(f"- File: `{finding.file}`")
        lines.append(f"- Lines: {finding.start_line}-{finding.end_line}")
        lines.append(f"- Level: {finding.level}")
        lines.append(f"- Score: {finding.score:.3f} (local {finding.local_score:.3f})")
        if finding.external_score is not None:
            lines.append(f"- External score: {finding.external_score:.3f}")
        lines.append("- Reasons:")
        for reason in finding.reasons:
            lines.append(f"  - {reason}")
        lines.append("")
        lines.append("### Original Excerpt")
        lines.append("")
        lines.append("```text")
        lines.append(finding.excerpt)
        lines.append("```")
        lines.append("")
        lines.append("### Suggested Rewrite")
        lines.append("")
        lines.append("```text")
        lines.append(finding.suggested_rewrite)
        lines.append("```")
        lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_report_analysis(
    source_path: Path,
    output_dir: Path,
    min_score: float,
    external_timeout: float,
) -> AnalysisSummary:
    workspace_root = Path(__file__).resolve().parents[1]
    tex_files = discover_tex_files(source_path)
    if not tex_files:
        raise FileNotFoundError(f"No .tex files found under: {source_path}")

    all_findings: list[Finding] = []
    mode_set: set[str] = {"local-only"}

    for tex_file in tex_files:
        file_findings, file_mode = analyze_file(
            tex_file=tex_file,
            workspace_root=workspace_root,
            min_score=min_score,
            external_timeout=external_timeout,
        )
        mode_set.add(file_mode)
        all_findings.extend(file_findings)

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    findings_path = output_dir / f"ai_authenticity_findings_{timestamp}.json"
    suggestions_path = output_dir / f"ai_authenticity_suggestions_{timestamp}.md"

    if "hybrid-with-errors" in mode_set:
        external_mode = "hybrid-with-errors"
    elif "hybrid" in mode_set:
        external_mode = "hybrid"
    else:
        external_mode = "local-only"

    high_findings = sum(1 for item in all_findings if item.level == "HIGH")
    medium_findings = sum(1 for item in all_findings if item.level == "MEDIUM")
    low_findings = sum(1 for item in all_findings if item.level == "LOW")

    metadata = {
        "generated_at": timestamp,
        "source": relative_to_workspace(source_path, workspace_root),
        "scanned_files": len(tex_files),
        "flagged_paragraphs": len(all_findings),
        "high_findings": high_findings,
        "medium_findings": medium_findings,
        "low_findings": low_findings,
        "min_score": min_score,
        "external_mode": external_mode,
    }

    write_json_report(findings_path, all_findings, metadata)
    write_suggestions_markdown(suggestions_path, all_findings, metadata)

    return AnalysisSummary(
        scanned_files=len(tex_files),
        flagged_paragraphs=len(all_findings),
        high_findings=high_findings,
        medium_findings=medium_findings,
        low_findings=low_findings,
        findings_path=str(findings_path),
        suggestions_path=str(suggestions_path),
        external_mode=external_mode,
    )


def build_argument_parser() -> argparse.ArgumentParser:
    workspace_root = Path(__file__).resolve().parents[1]
    default_source = workspace_root / "report-latex" / "chapters"
    default_output = workspace_root / "report-latex" / "quality-reports"

    parser = argparse.ArgumentParser(
        description=(
            "Analyze report LaTeX chapters for AI-like writing patterns and produce "
            "rewrite suggestions."
        )
    )
    parser.add_argument(
        "source",
        nargs="?",
        default=str(default_source),
        help="Path to a .tex file or directory containing .tex files.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(default_output),
        help="Directory where findings JSON and suggestion Markdown are written.",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.40,
        help="Minimum suspicion score to include (range 0.0-1.0).",
    )
    parser.add_argument(
        "--external-timeout",
        type=float,
        default=8.0,
        help="Timeout in seconds for optional external detector requests.",
    )
    parser.add_argument(
        "--fail-on-high",
        action="store_true",
        help="Exit with code 2 when one or more HIGH findings are present.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    source_path = Path(args.source).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()

    if not (0.0 <= args.min_score <= 1.0):
        parser.error("--min-score must be between 0.0 and 1.0")

    try:
        summary = run_report_analysis(
            source_path=source_path,
            output_dir=output_dir,
            min_score=args.min_score,
            external_timeout=args.external_timeout,
        )
    except FileNotFoundError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - safety net for CLI execution
        print(f"[error] Unexpected failure: {exc}", file=sys.stderr)
        return 1

    print("Report AI authenticity analysis complete.")
    print(f"Scanned files: {summary.scanned_files}")
    print(f"Flagged paragraphs: {summary.flagged_paragraphs}")
    print(
        "Severity counts: "
        f"HIGH={summary.high_findings}, "
        f"MEDIUM={summary.medium_findings}, "
        f"LOW={summary.low_findings}"
    )
    print(f"Detection mode: {summary.external_mode}")
    print(f"Findings JSON: {summary.findings_path}")
    print(f"Suggestions Markdown: {summary.suggestions_path}")

    if args.fail_on_high and summary.high_findings > 0:
        print("[error] High-severity findings present.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
