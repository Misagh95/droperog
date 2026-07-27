# Run this PowerShell as Admin to schedule DroperOG every 4 hours
param([int]$Hours=4)
$taskName = "DroperOG"
$scriptPath = Join-Path $PSScriptRoot "run.bat"
schtasks /Delete /TN $taskName /F 2>$null
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$scriptPath`""
$trigger = New-ScheduledTaskTrigger -Daily -At "00:00" -RepetitionInterval (New-TimeSpan -Hours $Hours) -RepetitionDuration ([TimeSpan]::MaxValue)
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Force
Write-Host "DroperOG scheduled: every $Hours hours"
