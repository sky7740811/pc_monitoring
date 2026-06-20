$p = $PSScriptRoot
$ico = "$p\pc-monitor.ico"
$bat = "$p\PC Monitor.bat"
$desktop = [Environment]::GetFolderPath("Desktop")
$target = "$desktop\PC Monitor.lnk"

if (Test-Path $target) { Remove-Item $target -Force }
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut($target)
$s.TargetPath = $bat
$s.WorkingDirectory = $p
$s.IconLocation = "$ico, 0"
$s.Save()
Write-Host "PC Monitor shortcut created on desktop"
