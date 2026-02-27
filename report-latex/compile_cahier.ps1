<#
PowerShell helper to compile the LaTeX source to PDF.
Requires a LaTeX distribution with `pdflatex` on PATH (MiKTeX or TeX Live).
Usage: Open PowerShell in this folder and run: .\compile_cahier.ps1
#>

$tex = "cahier_des_charges_revise.tex"
if (-not (Test-Path $tex)) {
    Write-Error "File $tex not found in current directory. Run this script from report-latex folder."
    exit 1
}

Write-Output "Compiling $tex -> PDF (pdflatex)"
pdflatex -interaction=nonstopmode -halt-on-error $tex | Write-Output
if ($LASTEXITCODE -ne 0) {
    Write-Error "pdflatex failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Output "Compilation finished. Output: cahier_des_charges_revise.pdf"
