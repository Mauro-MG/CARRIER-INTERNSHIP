param(
    [Parameter(Mandatory=$true)][string]$WorkbookPath,
    [Parameter(Mandatory=$true)][string]$OutputDir
)

$ErrorActionPreference = 'Stop'
$resolvedWorkbook = (Resolve-Path -LiteralPath $WorkbookPath).Path
$resolvedOutput = [System.IO.Path]::GetFullPath($OutputDir)
[System.IO.Directory]::CreateDirectory($resolvedOutput) | Out-Null
$vbaDir = Join-Path $resolvedOutput 'vba'
$pdfDir = Join-Path $resolvedOutput 'sheet_pdfs'
[System.IO.Directory]::CreateDirectory($vbaDir) | Out-Null
[System.IO.Directory]::CreateDirectory($pdfDir) | Out-Null

$excel = $null
$book = $null
$report = [ordered]@{ workbook = $resolvedWorkbook; vbproject = $null; sheets = @() }

try {
    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.EnableEvents = $false
    $excel.AskToUpdateLinks = $false
    $excel.AutomationSecurity = 3
    $book = $excel.Workbooks.Open($resolvedWorkbook, 0, $true)

    try {
        $components = @()
        foreach ($component in $book.VBProject.VBComponents) {
            $extension = switch ([int]$component.Type) {
                1 { '.bas' }
                2 { '.cls' }
                3 { '.frm' }
                100 { '.cls' }
                default { '.txt' }
            }
            $safeName = ($component.Name -replace '[^A-Za-z0-9_.-]', '_')
            $target = Join-Path $vbaDir ($safeName + $extension)
            $component.Export($target)
            $lineCount = $component.CodeModule.CountOfLines
            $components += [ordered]@{ name = $component.Name; type = [int]$component.Type; lines = $lineCount; file = $target }
        }
        $report.vbproject = [ordered]@{ available = $true; components = $components }
    } catch {
        $report.vbproject = [ordered]@{ available = $false; error = $_.Exception.Message }
    }

    foreach ($sheet in $book.Worksheets) {
        $shapeInfo = @()
        foreach ($shape in $sheet.Shapes) {
            $caption = $null
            try { $caption = $shape.TextFrame2.TextRange.Text } catch {}
            if (-not $caption) { try { $caption = $shape.TextFrame.Characters().Text } catch {} }
            $shapeInfo += [ordered]@{
                name = $shape.Name
                type = [int]$shape.Type
                formControlType = $(try { [int]$shape.FormControlType } catch { $null })
                onAction = $(try { $shape.OnAction } catch { $null })
                caption = $caption
                topLeftCell = $(try { $shape.TopLeftCell.Address($false,$false) } catch { $null })
                alternativeText = $(try { $shape.AlternativeText } catch { $null })
            }
        }

        $sheetData = [ordered]@{
            name = $sheet.Name
            codeName = $sheet.CodeName
            visible = [int]$sheet.Visible
            usedRange = $sheet.UsedRange.Address($false,$false)
            shapes = $shapeInfo
            pdf = $null
            pdfError = $null
        }
        try {
            if ([int]$sheet.Visible -ne -1) { $sheet.Visible = -1 }
            $safeSheet = ($sheet.Name -replace '[^A-Za-z0-9_.-]', '_')
            $pdfPath = Join-Path $pdfDir ($safeSheet + '.pdf')
            $sheet.ExportAsFixedFormat(0, $pdfPath, 0, $true, $false)
            $sheetData.pdf = $pdfPath
        } catch {
            $sheetData.pdfError = $_.Exception.Message
        }
        $report.sheets += $sheetData
    }
} finally {
    if ($book) { $book.Close($false) }
    if ($excel) { $excel.Quit() }
    if ($book) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($book) }
    if ($excel) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($excel) }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

$report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $resolvedOutput 'excel_com_report.json') -Encoding utf8
$report | ConvertTo-Json -Depth 10
