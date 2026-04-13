# PFE Report (LaTeX)

This folder contains a ready-to-edit LaTeX report template for your PFE.

## Structure

- `main.tex`: master document
- `preamble.tex`: packages and formatting
- `titlepage.tex`: title page
- `chapters/`: chapter files
- `references.bib`: bibliography
- `figures/`: place your images here

## Build on Windows (PowerShell)

If you have TeX Live / MiKTeX installed:

```powershell
cd report-latex
latexmk -g -pdf main.tex
```

Or use the local wrapper, which always forces a rebuild:

```powershell
cd report-latex
.\compile_main.ps1
```

If you want the incremental latexmk flow instead:

```powershell
cd report-latex
latexmk -pdf main.tex
```

## Next edits you should do first

1. Update `titlepage.tex` with supervisors and institution formatting.
2. Replace chapter placeholder text with your actual content.
3. Add figures in `figures/` and cite them in chapters.
4. Add references and cite with `\cite{...}`.

## Recent changes in this template

- Added front-matter chapters: `chapters/dedications.tex` and `chapters/acknowledgements.tex`.
- Updated master flow to the new 10-chapter report structure from `chapters/01_context_project.tex` to `chapters/10_general_conclusion.tex`.
- Removed legacy chapter files from the previous report organization.

## Overleaf / Online compilation

You can also upload the entire `report-latex` folder to Overleaf and compile there (it will handle TeX Live / biber for you). For local zipping on Windows use File Explorer or PowerShell's `Compress-Archive` to create an uploadable archive.

If you want, I can also provide an Overleaf-ready ZIP or a small script to run the full build locally and report errors.
