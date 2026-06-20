$p = $PSScriptRoot
$ico = "$p\pc-monitor.ico"
$desktop = [Environment]::GetFolderPath("Desktop")
$target = "$desktop\PC Monitor.lnk"
$bat = "$p\PC Monitor.bat"

if (Test-Path $target) { Remove-Item $target -Force }

$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut($target)
$s.TargetPath = "powershell.exe"
$s.Arguments = "-WindowStyle Hidden -Command Start-Process '$bat' -Verb RunAs"
$s.WorkingDirectory = "$p"
$s.IconLocation = "$ico, 0"
$s.Save()
Write-Host "OK: raccourci -> PowerShell -> PC Monitor.bat (admin)"
