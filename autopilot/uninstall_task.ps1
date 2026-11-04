# Removes the WoolWashAutopilot scheduled task and stops a running watchdog.
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
New-Item -ItemType File -Force (Join-Path $Here "STOP") | Out-Null
Stop-ScheduledTask -TaskName "WoolWashAutopilot" -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "WoolWashAutopilot" -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "WoolWashAutopilot removed. Delete the STOP file before starting the autopilot again."
