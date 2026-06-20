$p = $PSScriptRoot
$ico = "$p\pc-monitor.ico"
$exe = "$p\launcher.exe"
$desktop = [Environment]::GetFolderPath("Desktop")
$target = "$desktop\PC Monitor.lnk"

if (Test-Path $target) { Remove-Item $target -Force }

$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut($target)
$s.TargetPath = $exe
$s.WorkingDirectory = "$p"
$s.IconLocation = "$ico, 0"
$s.Save()
Write-Host "OK: shortcut -> launcher.exe (custom icon)"
