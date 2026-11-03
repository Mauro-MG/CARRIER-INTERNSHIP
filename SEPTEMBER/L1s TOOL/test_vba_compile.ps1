param([string]$WorkbookPath)
$ErrorActionPreference='Stop'
$excel=$null; $book=$null
try {
  $excel=New-Object -ComObject Excel.Application
  $excel.Visible=$false
  $excel.DisplayAlerts=$false
  $excel.EnableEvents=$false
  $excel.AutomationSecurity=1
  $book=$excel.Workbooks.Open((Resolve-Path -LiteralPath $WorkbookPath).Path,0,$true)
  $report=[ordered]@{}
  try { $report.Max=$excel.Run("'"+$book.Name+"'!Max",1,2) } catch { $report.MaxError=$_.Exception.Message }
  try { $report.removeNonDigits=$excel.Run("'"+$book.Name+"'!removeNonDigits",'SO 0010') } catch { $report.removeNonDigitsError=$_.Exception.Message }
  $report | ConvertTo-Json
} finally {
  if($book){$book.Close($false)}
  if($excel){$excel.Quit()}
  if($book){[void][Runtime.InteropServices.Marshal]::ReleaseComObject($book)}
  if($excel){[void][Runtime.InteropServices.Marshal]::ReleaseComObject($excel)}
}
