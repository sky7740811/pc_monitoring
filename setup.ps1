$p = "$PSScriptRoot"
$ico = "$p\pc-monitor.ico"
$target = "$env:USERPROFILE\Desktop\PC Monitor.lnk"

$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut($target)
$lnk.TargetPath = "powershell.exe"
$lnk.Arguments = "-ExecutionPolicy Bypass -Command Start-Process cmd.exe -ArgumentList '/c `"$p\PC Monitor.bat`"' -Verb RunAs -WindowStyle Hidden"
$lnk.WorkingDirectory = "$p"
if (Test-Path $ico) { $lnk.IconLocation = "$ico, 0" }
$lnk.Save()
Write-Host "OK: $target"
