# Eraser Diagram Sources

This folder stores `.eraserdiagram` source files for report figures.

## New database relationship diagrams

- `database_core_erd.eraserdiagram`: core operational data (establishments, caisses, sessions, feed configs, alerts).
- `database_auth_erd.eraserdiagram`: authentication and audit data (users, refresh sessions, audit log).

## Export workflow

1. Open a `.eraserdiagram` file in VS Code with Eraser extension.
2. Verify layout in preview.
3. Export to PDF/SVG.
4. Save exported figure into `report-latex/figures/` and reference it in LaTeX chapters.
