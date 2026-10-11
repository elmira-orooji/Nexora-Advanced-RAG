param(
    [string]$Source = "$PSScriptRoot\..\requirements\Nexora-SRS.docx",
    [string]$Output = "$PSScriptRoot\..\..\.local\srs-rebuild\Nexora-SRS.pdf"
)
$ErrorActionPreference = 'Stop'
$sourcePath = (Resolve-Path -LiteralPath $Source).Path
$outputPath = [IO.Path]::GetFullPath($Output)
New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($outputPath)) -Force | Out-Null
$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $document = $word.Documents.Open($sourcePath, $false, $false)
    # Replace oversized literal dot strings with compact leaders before pagination.
    foreach ($paragraph in $document.Paragraphs) {
        $text = $paragraph.Range.Text.Trim()
        if ($text -match '^\s*(فصل\s+[۰-۹0-9]+.*?)\s*\.{5,}\s*([۰-۹0-9]+)$') {
            $title = [regex]::Replace($Matches[1].Trim(), '\s+', ' ')
            $title = $title.Replace('OCR', 'استخراج متن').Replace('Connector', 'اتصال منابع')
            $number = $Matches[2]
            $range = $paragraph.Range.Duplicate
            $range.End = $range.End - 1
            $range.Text = $title + '  ' + ('.' * 60) + '  ' + $number
            $paragraph.Format.ReadingOrder = 0
            $paragraph.Format.Alignment = 0
        }
    }
    $document.Repaginate()
    $chapterPages = @{}
    $faDigits = '۰۱۲۳۴۵۶۷۸۹'
    foreach ($paragraph in $document.Paragraphs) {
        $text = $paragraph.Range.Text.Trim()
        if ($text -match '^فصل\s+([۰-۹0-9]+)$') {
            $chapterPages[$Matches[1]] = [int]$paragraph.Range.Information(3)
        }
    }
    # The template has a manually styled contents page; update its page numbers.
    foreach ($paragraph in $document.Paragraphs) {
        $text = $paragraph.Range.Text.Trim()
        if ($text -match '^\s*فصل\s+([۰-۹0-9]+).*\.{5,}\s*[۰-۹0-9]+$') {
            $chapter = $Matches[1]
            if ($chapterPages.ContainsKey($chapter)) {
                $number = $chapterPages[$chapter].ToString()
                for ($digit = 0; $digit -lt 10; $digit++) {
                    $number = $number.Replace([string]$digit, [string]$faDigits[$digit])
                }
                $range = $paragraph.Range.Duplicate
                $range.End = $range.End - 1
                $range.Text = [regex]::Replace($text, '[۰-۹0-9]+$', $number)
            }
        }
    }
    $document.Fields.Update() | Out-Null
    $document.Repaginate()
    $document.Save()
    $document.ExportAsFixedFormat($outputPath, 17)
    Write-Output "Exported: $outputPath"
    Write-Output "Pages: $($document.ComputeStatistics(2))"
} finally {
    if ($document) { $document.Close(0); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($document) }
    if ($word) { $word.Quit(); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($word) }
}
