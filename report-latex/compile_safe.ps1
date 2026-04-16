<#
PowerShell helper to compile the sanitized mid-term LaTeX report.
Uses latexmk in go mode so every run rebuilds the PDF even if cached files exist.
Usage: Open PowerShell in this folder and run: .\compile_safe.ps1
#>

$tex = "main_safe.tex"
if (-not (Test-Path $tex)) {
    Write-Error "File $tex not found in current directory. Run this script from report-latex folder."
    exit 1
}

Write-Output "Compiling $tex -> PDF (latexmk -g)"
latexmk -g -pdf $tex | Write-Output
if ($LASTEXITCODE -ne 0) {
    Write-Error "latexmk failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Output "Compilation finished. Output: main_safe.pdf"