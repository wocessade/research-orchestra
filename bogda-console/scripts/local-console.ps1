#Requires -Version 5.1
<#
.SYNOPSIS
  Start, inspect, or stop the local Bogda Console on 127.0.0.1:3101.

.DESCRIPTION
  Daily Windows launcher for the mock-all console. Paths are resolved from this
  script's location. It never binds, proxies, or stops port 3100, and it does
  not install dependencies. plan/probe exist for tests only.
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Action = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$Python = [System.IO.Path]::GetFullPath((Join-Path $Root ".venv\Scripts\python.exe"))
$FrontendDist = [System.IO.Path]::GetFullPath((Join-Path $Root "frontend\dist"))
$BindHost = "127.0.0.1"
$Port = 3101
$ReadyTimeoutSeconds = 15

if ($env:BOGDA_CONSOLE_STATE_DIR) {
    $StateDir = [System.IO.Path]::GetFullPath($env:BOGDA_CONSOLE_STATE_DIR)
} else {
    $StateDir = Join-Path $env:LOCALAPPDATA "BogdaConsole"
}

$StatePath = Join-Path $StateDir "state.json"
$StdoutLog = Join-Path $StateDir "stdout.log"
$StderrLog = Join-Path $StateDir "stderr.log"
$RunnerPath = Join-Path $StateDir "run_bogda_console.py"
$DryRun = $env:BOGDA_CONSOLE_LAUNCHER_DRY_RUN -eq "1"
$ObservationFile = $env:BOGDA_CONSOLE_LAUNCHER_OBSERVATION

$ProfileExplicit = -not [string]::IsNullOrWhiteSpace($env:BOGDA_CONSOLE_PROFILE)
$SelectedProfile = if ($ProfileExplicit) { $env:BOGDA_CONSOLE_PROFILE } else { "mock-all" }
$MockAllowlistDefaults = @{
    BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS  = "deployment-service,deployment-dorm"
    BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS    = "schedule-service,schedule-dorm"
    BOGDA_CONSOLE_ALLOWED_QUEUE_IDS       = "queue-service,queue-cpu,queue-gpu"
    BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES = "pi-service,dorm-x86"
}

if (-not $ProfileExplicit) {
    $ChildEnv = @{
        BOGDA_CONSOLE_PROFILE                 = "mock-all"
        BOGDA_CONSOLE_TEST_MODE               = "0"
        BOGDA_CONSOLE_PUBLIC_HOST             = $BindHost
        BOGDA_CONSOLE_PUBLIC_PORT             = "$Port"
        BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS  = $MockAllowlistDefaults.BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS
        BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS    = $MockAllowlistDefaults.BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS
        BOGDA_CONSOLE_ALLOWED_QUEUE_IDS       = $MockAllowlistDefaults.BOGDA_CONSOLE_ALLOWED_QUEUE_IDS
        BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES = $MockAllowlistDefaults.BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES
    }
} else {
    $ChildEnv = @{
        BOGDA_CONSOLE_PROFILE                 = $SelectedProfile
        BOGDA_CONSOLE_TEST_MODE               = if ($null -ne $env:BOGDA_CONSOLE_TEST_MODE) { $env:BOGDA_CONSOLE_TEST_MODE } else { "0" }
        BOGDA_CONSOLE_PUBLIC_HOST             = $BindHost
        BOGDA_CONSOLE_PUBLIC_PORT             = "$Port"
        BOGDA_CONSOLE_REPLICA_COUNT           = if ($null -ne $env:BOGDA_CONSOLE_REPLICA_COUNT) { $env:BOGDA_CONSOLE_REPLICA_COUNT } else { "1" }
        BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS  = if ($null -ne $env:BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS) { $env:BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS } elseif ($SelectedProfile -eq "mock-all") { $MockAllowlistDefaults.BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS } else { "" }
        BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS    = if ($null -ne $env:BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS) { $env:BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS } elseif ($SelectedProfile -eq "mock-all") { $MockAllowlistDefaults.BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS } else { "" }
        BOGDA_CONSOLE_ALLOWED_QUEUE_IDS       = if ($null -ne $env:BOGDA_CONSOLE_ALLOWED_QUEUE_IDS) { $env:BOGDA_CONSOLE_ALLOWED_QUEUE_IDS } elseif ($SelectedProfile -eq "mock-all") { $MockAllowlistDefaults.BOGDA_CONSOLE_ALLOWED_QUEUE_IDS } else { "" }
        BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES = if ($null -ne $env:BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES) { $env:BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES } elseif ($SelectedProfile -eq "mock-all") { $MockAllowlistDefaults.BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES } else { "" }
    }
    if ($SelectedProfile -ne "mock-all") {
        foreach ($key in @("PREFECT_API_URL", "PREFECT_API_AUTH_STRING", "PREFECT_API_KEY", "DEEPSEEK_API_KEY", "DEEPSEEK_API_BASE")) {
            $value = [Environment]::GetEnvironmentVariable($key)
            if ($null -ne $value) { $ChildEnv[$key] = $value }
        }
    }
}

function Write-HostMessage([string]$Text) {
    [Console]::Out.WriteLine($Text)
}

function ConvertTo-CompactJson($Object) {
    return ($Object | ConvertTo-Json -Depth 8 -Compress)
}

function Read-JsonFile([string]$Path) {
    return [System.IO.File]::ReadAllText($Path) | ConvertFrom-Json
}

function Read-Note($Object, [string]$Name, $Default = $null) {
    if ($null -eq $Object) { return $Default }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $Default }
    return $property.Value
}

function ConvertTo-OptionalInt($Value) {
    if ($null -eq $Value -or $Value -eq "") { return $null }
    return [int]$Value
}

function ConvertTo-StartTimeString($Value) {
    if ($null -eq $Value) { return "" }
    if ($Value -is [datetime]) { return $Value.ToString("o") }
    return [string]$Value
}

function New-EnvObject {
    $secretKeys = @("PREFECT_API_AUTH_STRING", "PREFECT_API_KEY", "DEEPSEEK_API_KEY")
    $envObject = New-Object psobject
    foreach ($key in @($ChildEnv.Keys | Sort-Object)) {
        $value = [string]$ChildEnv[$key]
        if ($secretKeys -contains $key -and $value) { $value = "[set]" }
        $envObject | Add-Member -NotePropertyName $key -NotePropertyValue $value
    }
    return $envObject
}

function Get-LiveListenerPid {
    try {
        $rows = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            Where-Object {
                $_.LocalAddress -eq "127.0.0.1" -or
                $_.LocalAddress -eq "0.0.0.0" -or
                $_.LocalAddress -eq "::1" -or
                $_.LocalAddress -eq "::"
            })
        if ($rows.Count -gt 0) {
            return [int]$rows[0].OwningProcess
        }
    } catch {
        return $null
    }
    return $null
}

function Get-LiveCapabilities {
    $uri = "http://${BindHost}:${Port}/api/v1/capabilities"
    try {
        $response = Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec 2
        $payload = $response.Content | ConvertFrom-Json
        return @{
            reachable  = $true
            httpStatus = [int]$response.StatusCode
            profile    = [string](Read-Note (Read-Note $payload "data") "profile")
        }
    } catch {
        $status = $null
        $responseProperty = $_.Exception.PSObject.Properties["Response"]
        if ($null -ne $responseProperty -and $null -ne $responseProperty.Value) {
            $statusCodeProperty = $responseProperty.Value.PSObject.Properties["StatusCode"]
            if ($null -ne $statusCodeProperty) {
                $status = [int]$statusCodeProperty.Value
            }
        }
        return @{
            reachable  = $false
            httpStatus = $status
            profile    = $null
        }
    }
}

function Get-LiveProcessView($PidValue) {
    if ($null -eq $PidValue) {
        return @{ pid = $null; running = $false; startTime = $null }
    }
    $process = Get-Process -Id $PidValue -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        return @{ pid = [int]$PidValue; running = $false; startTime = $null }
    }
    return @{
        pid       = [int]$process.Id
        running   = $true
        startTime = $process.StartTime.ToString("o")
    }
}

function Get-SavedState {
    if (-not (Test-Path -LiteralPath $StatePath)) { return $null }
    try {
        $data = Read-JsonFile $StatePath
        $pidValue = ConvertTo-OptionalInt (Read-Note $data "pid")
        if ($null -eq $pidValue) { return $null }
        return @{
            pid       = $pidValue
            startTime = ConvertTo-StartTimeString (Read-Note $data "startTime")
        }
    } catch {
        return $null
    }
}

function Get-LiveSnapshot {
    $state = Get-SavedState
    $listenerPid = Get-LiveListenerPid
    $processPid = $null
    if ($null -ne $state) { $processPid = $state.pid }
    elseif ($null -ne $listenerPid) { $processPid = $listenerPid }
    return @{
        state        = $state
        process      = (Get-LiveProcessView $processPid)
        listener     = @{ port = $Port; pid = $listenerPid }
        capabilities = (Get-LiveCapabilities)
    }
}

function Get-Snapshot {
    if (-not $ObservationFile) {
        return Get-LiveSnapshot
    }
    $raw = Read-JsonFile $ObservationFile
    $stateRaw = Read-Note $raw "state"
    $state = $null
    if ($null -ne $stateRaw) {
        $state = @{
            pid       = (ConvertTo-OptionalInt (Read-Note $stateRaw "pid"))
            startTime = ConvertTo-StartTimeString (Read-Note $stateRaw "startTime")
        }
    }
    $processRaw = Read-Note $raw "process"
    $listenerRaw = Read-Note $raw "listener"
    $capRaw = Read-Note $raw "capabilities"
    return @{
        state        = $state
        process      = @{
            pid       = (ConvertTo-OptionalInt (Read-Note $processRaw "pid"))
            running   = [bool](Read-Note $processRaw "running" $false)
            startTime = ConvertTo-StartTimeString (Read-Note $processRaw "startTime")
        }
        listener     = @{
            port = $Port
            pid  = (ConvertTo-OptionalInt (Read-Note $listenerRaw "pid"))
        }
        capabilities = @{
            reachable  = [bool](Read-Note $capRaw "reachable" $false)
            httpStatus = (ConvertTo-OptionalInt (Read-Note $capRaw "httpStatus"))
            profile    = (Read-Note $capRaw "profile")
        }
    }
}

function Test-ManagedMatch($Snapshot) {
    $state = $Snapshot.state
    $process = $Snapshot.process
    if ($null -eq $state -or $null -eq $state.pid) { return $false }
    if (-not $process.running) { return $false }
    if ([int]$process.pid -ne [int]$state.pid) { return $false }
    return ((ConvertTo-StartTimeString $process.startTime) -eq (ConvertTo-StartTimeString $state.startTime))
}

function Test-HealthyCapabilities($Snapshot) {
    $cap = $Snapshot.capabilities
    return ($cap.reachable -and $cap.httpStatus -eq 200 -and [string]$cap.profile -eq $SelectedProfile)
}

function Test-LaunchReady($Snapshot) {
    return ($null -ne $Snapshot.listener.pid) -and (Test-HealthyCapabilities $Snapshot)
}

function Get-StatusName($Snapshot) {
    $managed = Test-ManagedMatch $Snapshot
    $listenerPid = $Snapshot.listener.pid
    if ($managed) {
        $listenerOk = ($null -ne $listenerPid) -and ([int]$listenerPid -eq [int]$Snapshot.state.pid)
        if ($listenerOk -and (Test-HealthyCapabilities $Snapshot)) {
            return "healthy"
        }
        return "degraded"
    }
    if ($null -ne $listenerPid) {
        return "foreign-listener"
    }
    return "stopped"
}

function Resolve-StartDecision($Snapshot) {
    switch (Get-StatusName $Snapshot) {
        "healthy" { return "already-running" }
        "foreign-listener" { return "refuse-foreign" }
        "degraded" { return "refuse-degraded" }
        default { return "launch" }
    }
}

function Resolve-StopDecision($Snapshot) {
    $state = $Snapshot.state
    $listenerPid = $Snapshot.listener.pid
    if ($null -eq $state -or $null -eq $state.pid) {
        if ($null -ne $listenerPid) { return "refuse-foreign" }
        return "already-stopped"
    }
    $process = $Snapshot.process
    $pidMatch = $process.running -and ($null -ne $process.pid) -and ([int]$process.pid -eq [int]$state.pid)
    if (-not $pidMatch) {
        if ($null -ne $listenerPid -and ([int]$listenerPid -ne [int]$state.pid)) {
            return "refuse-foreign"
        }
        return "already-stopped"
    }
    if ([string]$process.startTime -ne [string]$state.startTime) {
        return "refuse-mismatch"
    }
    return "stop"
}

function Show-MissingPrereqs([string[]]$Missing) {
    foreach ($item in $Missing) {
        if ($item -eq ".venv") {
            Write-HostMessage "Missing .venv"
            Write-HostMessage "Fix from bogda-console directory:"
            Write-HostMessage "  py -3.11 -m venv .venv"
            Write-HostMessage "  .venv\Scripts\python.exe -m pip install -e ."
        }
        if ($item -eq "frontend/dist") {
            Write-HostMessage "Missing frontend\dist"
            Write-HostMessage "Fix from bogda-console directory:"
            Write-HostMessage "  npm ci"
            Write-HostMessage "  npm run build"
        }
    }
}

function New-PlanObject {
    $plan = New-Object psobject
    $plan | Add-Member -NotePropertyName root -NotePropertyValue $Root
    $plan | Add-Member -NotePropertyName python -NotePropertyValue $Python
    $plan | Add-Member -NotePropertyName frontendDist -NotePropertyValue $FrontendDist
    $plan | Add-Member -NotePropertyName host -NotePropertyValue $BindHost
    $plan | Add-Member -NotePropertyName port -NotePropertyValue $Port
    $plan | Add-Member -NotePropertyName env -NotePropertyValue (New-EnvObject)
    $plan | Add-Member -NotePropertyName command -NotePropertyValue @($Python, "-m", "bogda_console")
    return $plan
}

function New-ProbeObject($Snapshot) {
    $probe = New-Object psobject
    $probe | Add-Member -NotePropertyName status -NotePropertyValue (Get-StatusName $Snapshot)
    $probe | Add-Member -NotePropertyName pid -NotePropertyValue (Read-HashtableValue $Snapshot.state "pid")
    $probe | Add-Member -NotePropertyName listenerPid -NotePropertyValue $Snapshot.listener.pid
    $probe | Add-Member -NotePropertyName listenerPort -NotePropertyValue $Port
    $probe | Add-Member -NotePropertyName port -NotePropertyValue $Port
    $probe | Add-Member -NotePropertyName startDecision -NotePropertyValue (Resolve-StartDecision $Snapshot)
    $probe | Add-Member -NotePropertyName stopDecision -NotePropertyValue (Resolve-StopDecision $Snapshot)
    $probe | Add-Member -NotePropertyName profile -NotePropertyValue $Snapshot.capabilities.profile
    $launchReady = Test-LaunchReady $Snapshot
    $probe | Add-Member -NotePropertyName launchReady -NotePropertyValue $launchReady
    $probe | Add-Member -NotePropertyName launchPid -NotePropertyValue $(if ($launchReady) { $Snapshot.listener.pid } else { $null })
    return $probe
}

function Read-HashtableValue($Map, [string]$Name) {
    if ($null -eq $Map) { return $null }
    if ($Map -is [hashtable]) { return $Map[$Name] }
    return (Read-Note $Map $Name)
}

function Get-StatusExitCode([string]$Status) {
    switch ($Status) {
        "healthy" { return 0 }
        "degraded" { return 1 }
        "stopped" { return 2 }
        "foreign-listener" { return 3 }
        default { return 1 }
    }
}

function Clear-AttemptFiles {
    foreach ($path in @($StatePath, $StdoutLog, $StderrLog, $RunnerPath)) {
        if (Test-Path -LiteralPath $path) {
            Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
        }
    }
}

function Save-State([int]$ProcessId, [string]$StartTime) {
    New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
    $payload = New-Object psobject
    $payload | Add-Member -NotePropertyName pid -NotePropertyValue $ProcessId
    $payload | Add-Member -NotePropertyName startTime -NotePropertyValue $StartTime
    $payload | Add-Member -NotePropertyName host -NotePropertyValue $BindHost
    $payload | Add-Member -NotePropertyName port -NotePropertyValue $Port
    [System.IO.File]::WriteAllText($StatePath, (ConvertTo-CompactJson $payload))
}

function Write-Runner {
    New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
    $code = @"
import runpy
import sys

sys.stdout = open(r"$($StdoutLog.Replace('\', '\\'))", "a", encoding="utf-8", buffering=1)
sys.stderr = open(r"$($StderrLog.Replace('\', '\\'))", "a", encoding="utf-8", buffering=1)
runpy.run_module("bogda_console", run_name="__main__")
"@
    [System.IO.File]::WriteAllText($RunnerPath, $code)
}

function Start-ConsoleProcess {
    Write-Runner
    foreach ($path in @($StdoutLog, $StderrLog)) {
        if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }
        New-Item -ItemType File -Force -Path $path | Out-Null
    }

    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $Python
    $startInfo.Arguments = '"{0}"' -f $RunnerPath
    $startInfo.WorkingDirectory = $Root
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    foreach ($key in $ChildEnv.Keys) {
        $startInfo.EnvironmentVariables[$key] = [string]$ChildEnv[$key]
    }

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    [void]$process.Start()
    return $process
}

function Get-LogTail([string]$Path, [int]$Lines = 40) {
    if (-not (Test-Path -LiteralPath $Path)) { return "" }
    $content = Get-Content -LiteralPath $Path -Tail $Lines -ErrorAction SilentlyContinue
    if ($null -eq $content) { return "" }
    return ($content -join [Environment]::NewLine)
}

function Wait-UntilHealthy($Process) {
    $deadline = (Get-Date).AddSeconds($ReadyTimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if ($Process.HasExited) { return $null }
        $snapshot = Get-LiveSnapshot
        if (Test-LaunchReady $snapshot) { return $snapshot }
        Start-Sleep -Milliseconds 500
    }
    $snapshot = Get-LiveSnapshot
    if (Test-LaunchReady $snapshot) { return $snapshot }
    return $null
}

function Invoke-Plan {
    Write-HostMessage (ConvertTo-CompactJson (New-PlanObject))
    return 0
}

function Invoke-Probe {
    $snapshot = Get-Snapshot
    $probe = New-ProbeObject $snapshot
    Write-HostMessage (ConvertTo-CompactJson $probe)
    return (Get-StatusExitCode $probe.status)
}

function Invoke-Status {
    $snapshot = Get-Snapshot
    $status = Get-StatusName $snapshot
    Write-HostMessage "status: $status"
    $managedPid = Read-HashtableValue $snapshot.state "pid"
    if ($null -ne $managedPid) {
        Write-HostMessage "pid: $managedPid"
    }
    if ($null -ne $snapshot.listener.pid) {
        Write-HostMessage "listener: ${BindHost}:${Port} pid $($snapshot.listener.pid)"
    } else {
        Write-HostMessage "listener: none on ${BindHost}:${Port}"
    }
    $profile = $snapshot.capabilities.profile
    if ($profile) {
        Write-HostMessage "profile: $profile"
    }
    return (Get-StatusExitCode $status)
}

function Invoke-Start {
    $missing = @()
    if (-not (Test-Path -LiteralPath $Python)) { $missing += ".venv" }
    if (-not (Test-Path -LiteralPath $FrontendDist)) { $missing += "frontend/dist" }
    if ($missing.Count -gt 0) {
        Show-MissingPrereqs $missing
        return 1
    }

    $snapshot = Get-Snapshot
    switch (Resolve-StartDecision $snapshot) {
        "already-running" {
            Write-HostMessage "already running"
            Write-HostMessage "pid: $($snapshot.state.pid)"
            Write-HostMessage "http://${BindHost}:${Port}/"
            return 0
        }
        "refuse-foreign" {
            Write-HostMessage "foreign-listener"
            Write-HostMessage "${BindHost}:${Port} is used by PID $($snapshot.listener.pid), which is not managed by this launcher. Not stopping that process."
            return 3
        }
        "refuse-degraded" {
            Write-HostMessage "degraded managed process is still running (PID $($snapshot.state.pid)); not starting another copy and not stopping it."
            return 1
        }
    }

    if ($DryRun) {
        Write-HostMessage "would start $Python -m bogda_console on ${BindHost}:${Port}"
        return 0
    }

    New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
    try {
        $process = Start-ConsoleProcess
        Save-State -ProcessId $process.Id -StartTime $process.StartTime.ToString("o")
        $readySnapshot = Wait-UntilHealthy $process
        if ($null -eq $readySnapshot) {
            Write-HostMessage "start failed: ${BindHost}:${Port} did not become healthy within ${ReadyTimeoutSeconds}s"
            $tail = Get-LogTail $StderrLog
            if ($tail) {
                Write-HostMessage "stderr tail:"
                Write-HostMessage $tail
            }
            if (-not $process.HasExited) {
                try { $process.Kill() } catch { }
            }
            Clear-AttemptFiles
            return 1
        }
        $listenerProcess = Get-LiveProcessView $readySnapshot.listener.pid
        if (-not $listenerProcess.running) {
            throw "listener PID $($readySnapshot.listener.pid) exited before it could be recorded"
        }
        Save-State -ProcessId $listenerProcess.pid -StartTime $listenerProcess.startTime
        Write-HostMessage "started pid $($listenerProcess.pid) on http://${BindHost}:${Port}/"
        return 0
    } catch {
        Write-HostMessage "start failed: $($_.Exception.Message)"
        $tail = Get-LogTail $StderrLog
        if ($tail) {
            Write-HostMessage "stderr tail:"
            Write-HostMessage $tail
        }
        Clear-AttemptFiles
        return 1
    }
}

function Invoke-Stop {
    $snapshot = Get-Snapshot
    switch (Resolve-StopDecision $snapshot) {
        "already-stopped" {
            Write-HostMessage "already stopped"
            if (-not $DryRun -and -not $ObservationFile) {
                Clear-AttemptFiles
            }
            return 0
        }
        "refuse-foreign" {
            Write-HostMessage "foreign-listener"
            Write-HostMessage "${BindHost}:${Port} is used by PID $($snapshot.listener.pid). Not stopping that process."
            return 3
        }
        "refuse-mismatch" {
            Write-HostMessage "stale pid/start time: recorded PID $($snapshot.state.pid) start time $($snapshot.state.startTime) does not match running process start time $($snapshot.process.startTime). Not stopping PID $($snapshot.state.pid)."
            return 1
        }
    }

    $targetPid = [int]$snapshot.state.pid
    if ($DryRun) {
        Write-HostMessage "would stop pid $targetPid"
        return 0
    }

    $running = Get-Process -Id $targetPid -ErrorAction SilentlyContinue
    if ($null -eq $running) {
        Write-HostMessage "recorded PID $targetPid is not running; not killing anything"
        Clear-AttemptFiles
        return 0
    }
    if ($running.StartTime.ToString("o") -ne [string]$snapshot.state.startTime) {
        Write-HostMessage "stale pid/start time: recorded start time does not match running process. Not stopping PID $targetPid."
        return 1
    }
    Stop-Process -Id $targetPid -ErrorAction Stop
    Clear-AttemptFiles
    Write-HostMessage "stopped pid $targetPid"
    return 0
}

switch ($Action.Trim().ToLowerInvariant()) {
    "start" { exit (Invoke-Start) }
    "status" { exit (Invoke-Status) }
    "stop" { exit (Invoke-Stop) }
    "plan" { exit (Invoke-Plan) }
    "probe" { exit (Invoke-Probe) }
    default {
        Write-HostMessage "Usage: .\scripts\local-console.ps1 start|status|stop"
        exit 2
    }
}
