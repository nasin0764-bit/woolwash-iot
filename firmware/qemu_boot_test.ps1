<#
  Boot test of the ready-made firmware in Espressif's ESP32 emulator (QEMU).
  Checks that the image boots, prints the firmware banner and reaches its setup stage.

  Run:  powershell -ExecutionPolicy Bypass -File firmware\qemu_boot_test.ps1

  What it can and cannot show:
    + bootloader, partition table and app image are valid; the app starts; no crash during setup
    - Wi-Fi is NOT emulated by QEMU, so the set-up portal itself cannot be tested here;
      sensors are absent (expect "DS18B20 probes found: 0"). Final proof needs a real board.

  Downloads ~36 MB once from https://github.com/espressif/qemu/releases into %TEMP%\ww_qemu.
#>
param([int]$Seconds = 25)
$ErrorActionPreference = "Stop"
$Here  = Split-Path -Parent $MyInvocation.MyCommand.Path
$Image = Get-ChildItem (Join-Path $Here "bin") -Filter "woolwash_esp32_*.merged.bin" | Select-Object -Last 1
if (-not $Image) { throw "No merged firmware image in firmware\bin" }
$Tag   = "esp-develop-9.2.2-20260417"
$Asset = "qemu-xtensa-softmmu-esp_develop_9.2.2_20260417-x86_64-w64-mingw32.tar.xz"
$Dir   = Join-Path $env:TEMP "ww_qemu"
$Exe   = Join-Path $Dir "qemu\bin\qemu-system-xtensa.exe"

if (-not (Test-Path $Exe)) {
    New-Item -ItemType Directory -Force $Dir | Out-Null
    $Tar = Join-Path $Dir $Asset
    Write-Host "Downloading Espressif QEMU ($Tag) ..."
    Invoke-WebRequest "https://github.com/espressif/qemu/releases/download/$Tag/$Asset" -OutFile $Tar -UseBasicParsing
    if ((Get-Item $Tar).Length -ne 35996720) { throw "Unexpected download size - aborting." }
    tar -xf $Tar -C $Dir
}

$Run = Join-Path $Dir "run"
New-Item -ItemType Directory -Force $Run | Out-Null
Copy-Item $Image.FullName (Join-Path $Run "flash.bin") -Force          # QEMU may write to the flash file
$Log = Join-Path $Run "serial.log"
if (Test-Path $Log) { Remove-Item $Log }
Write-Host "Booting $($Image.Name) for $Seconds s ..."
$p = Start-Process -FilePath $Exe -PassThru -NoNewWindow -WorkingDirectory $Run -ArgumentList @(
    "-nographic", "-machine", "esp32", "-drive", "file=flash.bin,if=mtd,format=raw",
    "-serial", "file:serial.log", "-monitor", "none")
Start-Sleep -Seconds $Seconds
if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force }

$text = if (Test-Path $Log) { Get-Content $Log -Raw } else { "" }
Write-Host "`n----- serial output (first 60 lines) -----"
($text -split "`n" | Select-Object -First 60) -join "`n" | Write-Host
Write-Host "-------------------------------------------`n"
$checks = [ordered]@{
    "ROM bootloader started"       = $text -match "rst:0x1|ets "
    "Firmware banner printed"      = $text -match "WoolWash-IoT FW \d+\.\d+\.\d+"
    "Setup ran (sensor scan)"      = $text -match "DS18B20 probes found"
    "Reached Wi-Fi/portal stage"   = $text -match "SETUP PORTAL|Wi-Fi OK|Wi-Fi failed"
    "No crash (Guru Meditation)"   = $text -notmatch "Guru Meditation|abort\(\)|Backtrace:"
}
$checks.GetEnumerator() | ForEach-Object { "{0,-30} {1}" -f $_.Key, $(if ($_.Value) { "PASS" } else { "FAIL / not reached" }) }
Write-Host "`nNote: 'Reached Wi-Fi/portal stage' may fail in QEMU because Wi-Fi is not emulated; that is not a firmware bug."
Write-Host "Full log: $Log"
