$base = "report-latex/figures/eraser"
$out = Join-Path $base "all_diagrams_code_bundle.md"
$files = Get-ChildItem $base -Filter "*.eraserdiagram" -File | Sort-Object Name

${sb} = New-Object System.Text.StringBuilder
[void]$sb.AppendLine("# All Eraser Diagram Codes")
[void]$sb.AppendLine()
[void]$sb.AppendLine("This file contains the code of all diagrams in this folder.")
[void]$sb.AppendLine()
[void]$sb.AppendLine("## Diagram Index")
[void]$sb.AppendLine()

foreach ($f in $files) {
    [void]$sb.AppendLine("- " + $f.BaseName)
}

[void]$sb.AppendLine()

foreach ($f in $files) {
    [void]$sb.AppendLine("## " + $f.BaseName)
    [void]$sb.AppendLine()
    [void]$sb.AppendLine("Source file: " + $f.Name)
    [void]$sb.AppendLine()

    $contentLines = Get-Content $f.FullName
    foreach ($line in $contentLines) {
        [void]$sb.AppendLine("    " + $line)
    }

    [void]$sb.AppendLine()
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($out, $sb.ToString(), $utf8NoBom)

Write-Output ("Created " + $out + " with " + $files.Count + " diagrams.")
