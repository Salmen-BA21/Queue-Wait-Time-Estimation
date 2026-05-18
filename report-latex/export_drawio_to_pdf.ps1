# Export all drawio files to PDF and move them to figures folder
# This script automates the process of converting drawio diagrams to PDF format

param(
    [string]$drawioDir = "$(Split-Path -Parent $PSCommandPath)\figures\drawio",
    [string]$figuresDir = "$(Split-Path -Parent $PSCommandPath)\figures"
)

# Verify directories exist
if (-not (Test-Path $drawioDir)) {
    Write-Error "DrawIO directory not found: $drawioDir"
    exit 1
}

if (-not (Test-Path $figuresDir)) {
    Write-Error "Figures directory not found: $figuresDir"
    exit 1
}

# Check if drawio CLI is available
$drawioCmd = Get-Command drawio -ErrorAction SilentlyContinue
if (-not $drawioCmd) {
    Write-Error "drawio CLI not found. Please install it or add it to PATH"
    exit 1
}

Write-Host "## Starting DrawIO to PDF export..." -ForegroundColor Cyan
Write-Host "Source: $drawioDir"
Write-Host "Destination: $figuresDir" -ForegroundColor Cyan
Write-Host ""

# Get all drawio files
$drawioFiles = Get-ChildItem -Path $drawioDir -Filter "*.drawio"

if ($drawioFiles.Count -eq 0) {
    Write-Warning "No .drawio files found in $drawioDir"
    exit 0
}

Write-Host "Found $($drawioFiles.Count) drawio file(s) to process" -ForegroundColor Yellow
Write-Host ""

$successCount = 0
$failureCount = 0

# Process each file
foreach ($file in $drawioFiles) {
    $pdfName = $file.BaseName + ".pdf"
    $pdfPath = Join-Path $drawioDir $pdfName
    
    Write-Host "Exporting: $($file.Name) -> $pdfName" -ForegroundColor Green
    
    try {
        # Export to PDF
        & drawio $file.FullName -F pdf -o $pdfPath -q
        
        if (Test-Path $pdfPath) {
            # Move to figures folder with force (replace if exists)
            Move-Item -Path $pdfPath -Destination (Join-Path $figuresDir $pdfName) -Force
            Write-Host "  [OK] Success" -ForegroundColor Green
            $successCount++
        } else {
            Write-Host "  [FAIL] PDF generation failed" -ForegroundColor Red
            $failureCount++
        }
    }
    catch {
        Write-Host "  [FAIL] Error: $_" -ForegroundColor Red
        $failureCount++
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Export Complete!" -ForegroundColor Cyan
Write-Host "[OK] Successful: $successCount" -ForegroundColor Green
Write-Host "[FAIL] Failed: $failureCount" -ForegroundColor Red
Write-Host "========================================" -ForegroundColor Cyan
