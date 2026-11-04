<#
  WoolWash-IoT autopilot watchdog  (Windows PowerShell 5.1)

  Restarts Claude Code unattended until every autonomous task in AUTOPILOT.md is done:
    1. waits until the interactive session has been idle for -IdleMinutes (default 20)
    2. runs:  claude -p --dangerously-skip-permissions --resume <session> <PROMPT.txt>
       (falls back to a fresh session if the resume fails)
    3. if Claude reports a usage limit, reads the reset time from the message, sleeps until
       reset + 3 min, and retries; if it cannot read a time it backs off 15 -> 30 -> 60 min
    4. stops when: AUTOPILOT.md says ALL AUTONOMOUS TASKS DONE / no open tasks, a STOP file exists,
       -MaxRuns successful runs were made, or too many unexpected errors occurred

  Start:   double-click start_autopilot.bat     (or: powershell -ExecutionPolicy Bypass -File autopilot.ps1)
  Stop:    create a file named STOP in this folder (or close the window)
  Logs:    autopilot\logs\
#>
param(
    [string]$SessionId = "8f8224fc-7133-498a-8cca-168e40e21a6d",
    [string]$SessionDir = "C:\Users\Nasiba\Desktop",          # folder the session was started in
    [int]$IdleMinutes = 20,
    [int]$MaxRuns = 25,
    [int]$MaxErrors = 6,
    [string]$Model = "",                                       # empty = default model
    [string]$FallbackModel = "",                               # e.g. sonnet
    [switch]$Fresh,                                            # never resume, always new session
    [switch]$NoIdleWait,                                       # start immediately
    [switch]$SelfTest                                          # test the reset-time parser and exit
)

$ErrorActionPreference = "Continue"
$Here      = Split-Path -Parent $MyInvocation.MyCommand.Path
$TaskFile  = Join-Path $Here "AUTOPILOT.md"
$PromptFile= Join-Path $Here "PROMPT.txt"
$StopFile  = Join-Path $Here "STOP"
$StateFile = Join-Path $Here "state.json"
$LogDir    = Join-Path $Here "logs"
New-Item -ItemType Directory -Force $LogDir | Out-Null
$LogFile   = Join-Path $LogDir ("autopilot_{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))
$ProjDir   = Join-Path $env:USERPROFILE (".claude\projects\" + ($SessionDir -replace '[:\\/]', '-'))

function Log([string]$msg) {
    $line = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    Write-Host $line
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

function Get-OpenTaskCount {
    if (-not (Test-Path $TaskFile)) { return 0 }
    $t = Get-Content $TaskFile -Raw -Encoding UTF8
    if ($t -match '(?m)^\s*ALL AUTONOMOUS TASKS DONE\s*$') { return 0 }   # must be on its own line
    $open = ($t -split "`n") | Where-Object { $_ -match '^\s*- \[ \]' -and $_ -notmatch '\[HUMAN\]' }
    return @($open).Count
}

function Get-TranscriptAgeMinutes([string]$id) {
    $f = Join-Path $ProjDir "$id.jsonl"
    if (-not (Test-Path $f)) { return 99999 }
    return ((Get-Date) - (Get-Item $f).LastWriteTime).TotalMinutes
}

function Get-ResetTime([string]$text) {
    # 1) epoch seconds, e.g. "Claude AI usage limit reached|1793812800"
    if ($text -match '\|(\d{10})\b') {
        return ([DateTimeOffset]::FromUnixTimeSeconds([int64]$Matches[1])).LocalDateTime
    }
    # 2) ISO timestamp
    if ($text -match '(?i)reset\w*\D{0,20}(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?(Z|[+-]\d{2}:?\d{2})?)') {
        try { return ([DateTimeOffset]::Parse($Matches[1])).LocalDateTime } catch {}
    }
    # 3) clock time, e.g. "resets 3pm", "resets at 11:30 PM", "reset at 15:00"
    if ($text -match '(?i)resets?\s*(?:at\s*)?(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)?') {
        $h = [int]$Matches[1]; $m = 0
        if ($Matches[2]) { $m = [int]$Matches[2] }
        if ($Matches[3]) {
            $ampm = $Matches[3].ToLower().Replace(".", "")
            if ($ampm -eq "pm" -and $h -lt 12) { $h += 12 }
            if ($ampm -eq "am" -and $h -eq 12) { $h = 0 }
        }
        if ($h -le 23 -and $m -le 59) {
            $t = (Get-Date).Date.AddHours($h).AddMinutes($m)
            if ($t -le (Get-Date)) { $t = $t.AddDays(1) }
            return $t
        }
    }
    # 4) relative, e.g. "try again in 2 hours", "in 45 minutes"
    if ($text -match '(?i)in\s+(\d+)\s*(h|hr|hrs|hour|hours)\b') { return (Get-Date).AddHours([int]$Matches[1]) }
    if ($text -match '(?i)in\s+(\d+)\s*(m|min|mins|minute|minutes)\b') { return (Get-Date).AddMinutes([int]$Matches[1]) }
    return $null
}

function Save-State($obj) { $obj | ConvertTo-Json | Set-Content -Path $StateFile -Encoding UTF8 }

if ($SelfTest) {
    $cases = @(
        "Claude AI usage limit reached|1793812800",
        "You've hit your limit - resets 3pm (Asia/Tashkent)",
        "5-hour limit reached. Your limit will reset at 11:30 PM",
        "Usage limit reached, resets at 15:00",
        "Rate limited. Please try again in 2 hours",
        "limit reached, try again in 45 minutes",
        "usage limit reached (no time given)"
    )
    foreach ($c in $cases) {
        $r = Get-ResetTime $c
        $s = if ($r) { $r.ToString("yyyy-MM-dd HH:mm") } else { "<none -> backoff>" }
        Write-Host ("{0,-62} -> {1}" -f $c, $s)
    }
    Write-Host ("Open autonomous tasks: {0}" -f (Get-OpenTaskCount))
    Write-Host ("Transcript age of {0}: {1:N1} min" -f $SessionId, (Get-TranscriptAgeMinutes $SessionId))
    exit 0
}

# ------------------------------------------------------------------ start
$claude = (Get-Command claude -ErrorAction SilentlyContinue).Source
if (-not $claude) { $claude = Join-Path $env:USERPROFILE ".local\bin\claude.exe" }
if (-not (Test-Path $claude)) { Write-Host "claude CLI not found"; exit 1 }
if (Test-Path $StateFile) {
    try { $st = Get-Content $StateFile -Raw | ConvertFrom-Json; if ($st.session_id) { $SessionId = $st.session_id } } catch {}
}
Log "Autopilot started. claude=$claude session=$SessionId fresh=$Fresh open_tasks=$(Get-OpenTaskCount)"

$runs = 0; $errors = 0; $backoff = 15
if (-not $NoIdleWait) {
    while ((Get-TranscriptAgeMinutes $SessionId) -lt $IdleMinutes) {
        if (Test-Path $StopFile) { Log "STOP file found - exiting."; exit 0 }
        Log ("Interactive session active (transcript {0:N0} min old) - waiting..." -f (Get-TranscriptAgeMinutes $SessionId))
        Start-Sleep -Seconds 300
    }
}

while ($true) {
    if (Test-Path $StopFile) { Log "STOP file found - exiting."; break }
    $open = Get-OpenTaskCount
    if ($open -eq 0) { Log "No open autonomous tasks - done."; break }
    if ($runs -ge $MaxRuns) { Log "MaxRuns ($MaxRuns) reached - exiting."; break }
    if ($errors -ge $MaxErrors) { Log "Too many errors ($errors) - exiting. Check the logs."; break }

    $prompt = (Get-Content $PromptFile -Raw -Encoding UTF8).Trim()
    $cliArgs = @("-p", "--dangerously-skip-permissions", "--output-format", "json")
    if ($Model) { $cliArgs += @("--model", $Model) }
    if ($FallbackModel) { $cliArgs += @("--fallback-model", $FallbackModel) }
    $resuming = (-not $Fresh) -and $SessionId
    if ($resuming) { $cliArgs += @("--resume", $SessionId) }
    $cliArgs += $prompt

    $runLog = Join-Path $LogDir ("run_{0}.json" -f (Get-Date -Format "yyyyMMdd_HHmmss"))
    Log "Run $($runs + 1): open tasks=$open resume=$resuming"
    Push-Location $SessionDir
    $out = & $claude @cliArgs 2>&1 | Out-String
    $code = $LASTEXITCODE
    Pop-Location
    Set-Content -Path $runLog -Value $out -Encoding UTF8

    $json = $null
    try { $json = ($out.Substring($out.IndexOf("{"))) | ConvertFrom-Json } catch {}
    $resultText = if ($json -and $json.result) { [string]$json.result } else { $out }
    $isError = ($code -ne 0) -or ($json -and $json.is_error)

    # ---- usage / rate limit (only for failed or very short runs, so a normal summary mentioning "reset" is ignored)
    $looksLimited = $resultText -match '(?i)usage limit|limit reached|rate.?limit|out of (extra )?usage|hit your limit|quota exceeded|limit will reset|resets?\s+(at\s+)?\d'
    if ($looksLimited -and ($isError -or $resultText.Length -lt 400)) {
        $reset = Get-ResetTime $resultText
        if ($reset) {
            $wake = $reset.AddMinutes(3)
            Log ("Usage limit. Reset at {0:yyyy-MM-dd HH:mm}; sleeping until {1:HH:mm}." -f $reset, $wake)
            Save-State @{ session_id = $SessionId; status = "waiting_for_reset"; wake = $wake.ToString("o") }
            while ((Get-Date) -lt $wake) {
                if (Test-Path $StopFile) { break }
                Start-Sleep -Seconds ([Math]::Min(600, [Math]::Max(5, ($wake - (Get-Date)).TotalSeconds)))
            }
        } else {
            Log "Usage limit, reset time not readable - backing off $backoff min. Message: $($resultText.Substring(0, [Math]::Min(200, $resultText.Length)))"
            Start-Sleep -Seconds ($backoff * 60)
            $backoff = [Math]::Min(60, $backoff * 2)
        }
        continue
    }
    # ---- server overloaded / network
    if ($isError -and $resultText -match '(?i)overloaded|\b529\b|\b503\b|ECONNRESET|ETIMEDOUT|network error') {
        Log "Service busy or network issue - retry in 5 min."
        Start-Sleep -Seconds 300; continue
    }
    # ---- resume failure -> fresh session
    if ($isError -and $resuming -and $resultText -match '(?i)no conversation|not found|could not (find|resume)|invalid session') {
        Log "Resume failed - switching to fresh sessions."
        $Fresh = $true; continue
    }
    if ($isError) {
        $errors++
        Log "Run failed (exit $code), error $errors/$MaxErrors. See $runLog"
        Start-Sleep -Seconds 120; continue
    }

    # ---- success
    $runs++; $errors = 0; $backoff = 15
    if ($json -and $json.session_id) { $SessionId = [string]$json.session_id }
    Save-State @{ session_id = $SessionId; status = "ok"; last_run = (Get-Date).ToString("o"); runs = $runs }
    Log "Run $runs finished. Session $SessionId. Open tasks now: $(Get-OpenTaskCount)"
    Start-Sleep -Seconds 30
}
Log "Autopilot finished."
