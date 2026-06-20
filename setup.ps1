$p = $PSScriptRoot
$ico = "$p\pc-monitor.ico"
$desktop = [Environment]::GetFolderPath("Desktop")
$target = "$desktop\PC Monitor.lnk"

# Remove old shortcut
if (Test-Path $target) { Remove-Item $target -Force }

$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut($target)
$s.TargetPath = "pythonw.exe"
$s.Arguments = """$p\run.py"""
$s.WorkingDirectory = "$p"
$s.IconLocation = "$ico, 0"
$s.Save()
Write-Host "OK: Shortcut -> pythonw run.py"
