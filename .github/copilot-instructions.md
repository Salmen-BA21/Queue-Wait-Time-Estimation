# Copilot Workspace Instructions

## LaTeX Context (report-latex/)
When working in the `report-latex/` folder or any `.tex`, `.bib`, or `.sty` file:
- Always output valid LaTeX syntax, never plain text or Markdown.
- Respect existing `\\usepackage{}` declarations and do not add duplicates.
- Preserve the document's `\\label{}` and `\\ref{}` naming conventions.
- Ensure all `\\cite{}` keys match entries in the project's `.bib` file.
- Prefer safe, standard LaTeX that preserves compilation stability.
