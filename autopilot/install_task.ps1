<#
  Registers the autopilot watchdog as a Windows scheduled task "WoolWashAutopilot":
    - starts 1 minute after installation and at every logon
    - runs in your user account, in a visible window, only one instance at a time
  Remove it with uninstall_task.ps1.
#>
$ErrorActionPreference = "Stop"
$Here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$Script = Join-Path $Here "autopilot.ps1"
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
          -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Script`"" -WorkingDirectory $Here
$triggers = @(
    (New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1)),
    (New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME")
)
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) `
            -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName "WoolWashAutopilot" -Action $action -Trigger $triggers -Settings $settings `
    -Principal $principal -Description "Restarts Claude Code for the WoolWash-IoT autonomous task queue" -Force | Out-Null
Write-Host "Scheduled task 'WoolWashAutopilot' installed. It starts in 1 minute and at every logon."
Write-Host "Stop: create the file $Here\STOP   Remove: uninstall_task.ps1"
