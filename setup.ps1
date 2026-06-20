$p = "$PSScriptRoot"
$ico = "$p\pc-monitor.ico"
$target = "$env:USERPROFILE\Desktop\PC Monitor.lnk"
$bat = "$p\PC Monitor.bat"

$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut($target)
$lnk.TargetPath = $bat
$lnk.Arguments = ""
$lnk.WorkingDirectory = "$p"
if (Test-Path $ico) { $lnk.IconLocation = "$ico, 0" }
$lnk.Save()
Write-Host "OK: Desktop shortcut -> PC Monitor.bat"
