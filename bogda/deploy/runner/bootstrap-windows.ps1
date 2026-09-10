#Requires -RunAsAdministrator
<#
.SYNOPSIS
  Host-side prep for the stand-in research runner.

  Research worker, Prefect, dsh, and attempt dirs stay in WSL2.
  This script does not install Prefect, does not join pi-service,
  and does not enable Wake Bridge / WoL.
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "runner host bootstrap (Windows side only)"
Write-Host "research processes belong in WSL2 Ubuntu, not native PowerShell"

$featureNames = @(
    "Microsoft-Windows-Subsystem-Linux",
    "VirtualMachinePlatform"
)
foreach ($name in $featureNames) {
    $feature = Get-WindowsOptionalFeature -Online -FeatureName $name
    if ($feature.State -ne "Enabled") {
        Write-Host "enabling $name (reboot may be required)"
        Enable-WindowsOptionalFeature -Online -FeatureName $name -All -NoRestart | Out-Null
    }
    else {
        Write-Host "$name already enabled"
    }
}

wsl --set-default-version 2
$distros = @(wsl --list --quiet 2>$null)
if (-not ($distros | Where-Object { $_ -match "Ubuntu" })) {
    Write-Host "installing Ubuntu WSL distro"
    wsl --install --distribution Ubuntu --no-launch
}
else {
    Write-Host "Ubuntu distro already present"
}

# Plugged-in stay-awake. Manual power, not Wake Bridge.
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /change disk-timeout-ac 0
Write-Host "AC sleep/hibernate/disk timeouts set to 0 (stay awake while plugged in)"

$tailscale = Get-Command tailscale -ErrorAction SilentlyContinue
if (-not $tailscale) {
    Write-Host "install Tailscale next: https://tailscale.com/download/windows"
    Write-Host "join the existing tailnet, then confirm rk3528 is listed before mounting NAS"
}
else {
    Write-Host "Tailscale CLI present. Run: tailscale status"
}

Write-Host ""
Write-Host "next:"
Write-Host "  1. Reboot if WSL features were just enabled."
Write-Host "  2. Open Ubuntu once and create the default UNIX user."
Write-Host "  3. In Ubuntu: clone the private repo, then bash bogda/deploy/runner/bootstrap-wsl.sh"
Write-Host "  4. Do not start a Prefect worker from Windows cmd/PowerShell."
