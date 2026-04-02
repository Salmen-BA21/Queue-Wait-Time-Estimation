---
name: report-ai-authenticity
description: "Use when checking whether report-latex chapters look AI-generated, scoring AI-like writing risk, and generating humanized English academic rewrite suggestions for flagged sections. Trigger phrases: verify report authenticity, check if chapter is AI generated, humanize report text, rewrite AI-like paragraph."
argument-hint: "Describe the chapter scope and whether you want flagging only or rewrite suggestions."
user-invocable: true
---

# Report AI Authenticity Validation

Use this skill to assess whether report prose contains AI-like writing patterns and to generate non-destructive rewrite suggestions that improve academic human voice.

## Scope

- Target directory: `report-latex/chapters/`
- Target files: `.tex` chapter sources
- Language target: English academic style
- Output mode: findings report + separate rewrite suggestions file

## Core Principle

This skill produces **risk signals**, not definitive proof of AI authorship. Results should be interpreted as writing-quality indicators for revision.

## Tooling Contract

Run the checker script first:

```bash
python scripts/report_ai_authenticity_check.py report-latex/chapters --output-dir report-latex/quality-reports --min-score 0.40
```

Optional CI gate for critical findings:

```bash
python scripts/report_ai_authenticity_check.py report-latex/chapters --fail-on-high
```

## Detection Model

### Local Heuristic Layer (always on)

- cliche transition detection
- hedge/filler phrase density
- repeated sentence-starter detection
- passive voice overuse detection
- low specificity detection
- low evidence signal in long paragraphs

### External Layer (optional)

If both environment variables are set, the checker adds external scoring:

- `AI_DETECTOR_API_URL`
- `AI_DETECTOR_API_KEY`

If not configured, analysis remains local-only and does not fail.

## Rewrite Policy

For each flagged paragraph, produce a rewrite that:

- keeps technical meaning intact
- keeps LaTeX-safe content and structure
- reduces generic/cliche phrasing
- reduces unnecessary hedging/passive phrasing
- asks for concrete evidence where specificity is missing

Do **not** auto-edit chapter files by default. Suggestions must be emitted in the generated markdown output.

## Generated Artifacts

- JSON findings: `report-latex/quality-reports/ai_authenticity_findings_<timestamp>.json`
- Markdown suggestions: `report-latex/quality-reports/ai_authenticity_suggestions_<timestamp>.md`

## Standard Workflow

1. Run checker on all report chapters.
2. Review HIGH and MEDIUM findings first.
3. Apply suggested rewrites selectively to chapter source files.
4. Re-run checker to confirm score reduction.
5. Rebuild LaTeX report to ensure compile stability.

## Verification Checklist

- findings and suggestions files generated
- no chapter files auto-modified by checker
- rewritten text remains technically accurate
- LaTeX report compiles successfully after accepted edits

## Example Prompts

- verify report authenticity for chapter 02 and suggest rewrites
- check if these sections are AI generated and humanize them
- run full report AI-like writing scan and list high-risk paragraphs
