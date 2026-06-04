# Export all drawio files to PDF and move them to figures folder
# Automates converting drawio diagrams to PDF with retry logic and timeouts

param(
    [string]$drawioDir = "$(Split-Path -Parent $PSCommandPath)\figures\drawio",
    [string]$figuresDir = "$(Split-Path -Parent $PSCommandPath)\figures",
    [int]$maxRetries = 3,
    [int]$timeoutSeconds = 120
)

if (-not (Test-Path $drawioDir)) {
    Write-Error "DrawIO directory not found: $drawioDir"
    exit 1
}

if (-not (Test-Path $figuresDir)) {
    Write-Error "Figures directory not found: $figuresDir"
    exit 1
}

$drawioExportCmd = Get-Command draw.io-export -ErrorAction SilentlyContinue
$drawioCmd = Get-Command drawio -ErrorAction SilentlyContinue

if (-not $drawioExportCmd -and -not $drawioCmd) {
    Write-Error "Neither 'draw.io-export' nor 'drawio' CLI found. Install: npm install -g draw.io-export"
    exit 1
}

Write-Host "## Starting DrawIO to PDF export..." -ForegroundColor Cyan
Write-Host "Source: $drawioDir"
Write-Host "Destination: $figuresDir" -ForegroundColor Cyan
Write-Host "Using CLI: $(if ($drawioExportCmd) { 'draw.io-export' } else { 'drawio' })" -ForegroundColor Yellow
Write-Host ""

$drawioFiles = Get-ChildItem -Path $drawioDir -Filter "*.drawio"

if ($drawioFiles.Count -eq 0) {
    Write-Warning "No .drawio files found in $drawioDir"
    exit 0
}

Write-Host "Found $($drawioFiles.Count) drawio file(s) to process" -ForegroundColor Yellow
Write-Host ""

$successCount = 0
$failureCount = 0

function Export-DrawioWithRetry {
    param(
        [string]$inputFile,
        [string]$outputFile,
        [int]$maxRetries,
        [int]$timeoutSeconds,
        [bool]$useExportCmd
    )

    for ($attempt = 1; $attempt -le $maxRetries; $attempt++) {
        try {
            Write-Host "  [Attempt $attempt/$maxRetries]" -ForegroundColor Yellow

            if ($useExportCmd) {
                $timeoutMs = $timeoutSeconds * 1000
                & draw.io-export --input $inputFile --output $outputFile --timeout $timeoutMs --quality 100 2>&1 | Out-Null
            }
            else {
                & drawio $inputFile -F pdf -o $outputFile -q 2>&1 | Out-Null
            }

            if (Test-Path $outputFile) {
                $fileSize = (Get-Item $outputFile).Length
                if ($fileSize -gt 1000) {
                    return $true
                }
                else {
                    Write-Host "    ⚠️  PDF too small ($fileSize bytes), retrying..." -ForegroundColor Yellow
                    Remove-Item $outputFile -Force
                }
            }
            else {
                Write-Host "    ⚠️  Output file not created, retrying..." -ForegroundColor Yellow
            }
        }
        catch {
            Write-Host "    ⚠️  Error on attempt $attempt : $_" -ForegroundColor Yellow
        }

        if ($attempt -lt $maxRetries) {
            $waitTime = 2 * $attempt
            Write-Host "    ⏳ Waiting ${waitTime}s before retry..." -ForegroundColor Gray
            Start-Sleep -Seconds $waitTime
        }
    }

    return $false
}

$useExportCmd = $null -ne $drawioExportCmd

foreach ($file in $drawioFiles) {
    $pdfName = $file.BaseName + ".pdf"
    $pdfPath = Join-Path $drawioDir $pdfName

    Write-Host "Exporting: $($file.Name) -> $pdfName" -ForegroundColor Green

    if (Test-Path $pdfPath) {
        Remove-Item $pdfPath -Force
    }

    if (Export-DrawioWithRetry -inputFile $file.FullName -outputFile $pdfPath -maxRetries $maxRetries -timeoutSeconds $timeoutSeconds -useExportCmd $useExportCmd) {
        try {
            Move-Item -Path $pdfPath -Destination (Join-Path $figuresDir $pdfName) -Force
            Write-Host "  [OK] Successfully exported" -ForegroundColor Green
            $successCount++
        }
        catch {
            Write-Host "  [FAIL] Error moving file: $_" -ForegroundColor Red
            $failureCount++
        }
    }
    else {
        Write-Host "  [FAIL] PDF generation failed after $maxRetries attempts" -ForegroundColor Red
        $failureCount++
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Export Complete!" -ForegroundColor Cyan
Write-Host "[OK] Successful: $successCount" -ForegroundColor Green
Write-Host "[FAIL] Failed: $failureCount" -ForegroundColor Red
Write-Host "========================================" -ForegroundColor Cyan

if ($failureCount -gt 0) {
    exit 1
}
else {
    exit 0
}
