# Bogda Console real-shadow runbook

This is the bounded acceptance procedure for comparing the console on `3101`
with the Prefect authority. `real-readonly` is the S1 profile. `allowlisted-test`
is the S2 profile and is permitted only for dedicated test resources with
`BOGDA_CONSOLE_REPLICA_COUNT=1`. `mock-all` remains a local fixture profile and
is not evidence of a real shadow.

Keep the legacy console on `3100` unchanged throughout. This runbook does not
perform a `3100` cutover, use SSH, or operate a worker or a real dorm machine.

Evidence is sanitized JSON/text only, under exactly:

```powershell
.tasks/active/052_bogda-gate7-real-shadow/evidence/
```

Never save raw API responses, request headers, process command lines, or
environment dumps. `PREFECT_API_AUTH_STRING` (or the supported server-side
credential fallback) may be inherited by the launcher, but its value must never
be printed, interpolated into a transcript, or written to evidence.

The only hard-stop boundaries are: unknown `3101` ownership; a non-test
allowlist member; S2 replica count not equal to one; source errors; a failed
authoritative post-read; or a `3100` regression. Record the boundary and do not
continue the affected phase.

## 1. Ownership preflight

Run from the checkout root whose `bogda-console` directory will be exercised. Capture
the profile and launcher ownership before changing any environment variable.
The launcher status is safe to record because it reports status, PID, port, and
profile—not credential values.

```powershell
$ErrorActionPreference = "Stop"
$RepoRoot = (Get-Location).Path
$ConsoleRoot = Join-Path $RepoRoot "bogda-console"
$EvidenceRoot = Join-Path $RepoRoot ".tasks\active\052_bogda-gate7-real-shadow\evidence"
New-Item -ItemType Directory -Force -Path $EvidenceRoot | Out-Null

$launcher = Join-Path $ConsoleRoot "scripts\local-console.ps1"
$statusText = (& $launcher status 2>&1 | Out-String).Trim()
$listener = @(Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 3101 -State Listen -ErrorAction SilentlyContinue |
    Select-Object LocalAddress, LocalPort, OwningProcess)
$preflight = [ordered]@{
    capturedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
    profile = if ($env:BOGDA_CONSOLE_PROFILE) { $env:BOGDA_CONSOLE_PROFILE } else { "mock-all (launcher default)" }
    replicaCount = if ($env:BOGDA_CONSOLE_REPLICA_COUNT) { $env:BOGDA_CONSOLE_REPLICA_COUNT } else { "1 (launcher default)" }
    allowlists = [ordered]@{
        deploymentIds = $env:BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS
        scheduleIds = $env:BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS
        queueIds = $env:BOGDA_CONSOLE_ALLOWED_QUEUE_IDS
        workPoolNames = $env:BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES
    }
    launcherStatus = $statusText
    listener = $listener
    authConfigured = [bool]$env:PREFECT_API_AUTH_STRING
}
$preflight | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $EvidenceRoot "preflight.json") -Encoding utf8
```

If the status is `foreign-listener`, or the launcher cannot prove that its
recorded PID and start time own the `3101` listener, ownership is unknown and
the run stops at this boundary. Do not stop a foreign PID. A launcher-owned
process may be stopped later only through this same launcher's `stop` action.

## 2. 3100 before-check

Check the legacy console once before S1 and save only reachability, status code,
and timestamp. Do not save the response body and do not send a request that
changes state.

```powershell
$legacyBefore = try {
    $response = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:3100/ -TimeoutSec 5
    [ordered]@{ reachable = $true; statusCode = [int]$response.StatusCode }
} catch {
    [ordered]@{ reachable = $false; statusCode = $null; errorType = $_.Exception.GetType().FullName }
}
$legacyBefore | Add-Member -NotePropertyName checkedAtUtc -NotePropertyValue ((Get-Date).ToUniversalTime().ToString("o"))
$legacyBefore | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $EvidenceRoot "3100-before.json") -Encoding utf8
```

Keep the recorded result for the restore comparison. Do not stop, proxy,
overwrite, or reconfigure `3100`.

## 3. S1 start/read/compare

If Phase 1 found a launcher-owned process, stop it with the launcher before
changing its profile. Then set only the S1 profile and loopback ports. Let the
launcher inherit `PREFECT_API_URL` and the already configured
`PREFECT_API_AUTH_STRING`; never echo either credential value. Do not set any
allowlist variable or DeepSeek key for S1.

```powershell
if ($statusText -match "status: (healthy|degraded)" -and $statusText -notmatch "foreign-listener") {
    & $launcher stop
}
$env:BOGDA_CONSOLE_PROFILE = "real-readonly"
$env:BOGDA_CONSOLE_PUBLIC_HOST = "127.0.0.1"
$env:BOGDA_CONSOLE_PUBLIC_PORT = "3101"
$env:BOGDA_CONSOLE_BFF_PORT = "3102"
& $launcher start
& $launcher status
```

Read the S1 projection from `3101` and save a deliberately reduced summary for
`capabilities`, `overview`, `runs`, `deployments`, and `infrastructure`:

```powershell
$paths = @("capabilities", "overview", "runs", "deployments", "infrastructure")
$responses = [ordered]@{}
foreach ($path in $paths) {
    $responses[$path] = Invoke-RestMethod "http://127.0.0.1:3101/api/v1/$path" -TimeoutSec 10
}
# Construct an explicit summary containing only IDs, counts, pool/queue/worker
# names, state.type, state.name, RunResult identifiers, profile, and can* fields.
# Write that summary—not $responses—to s1-projection.json.
```

Make the matching direct, read-only Prefect authority query with the same
server-side environment credentials. Compare deployment IDs, run IDs, pool,
queue, worker, `state.type`, `state.name`, and RunResult identifiers. Every
projection capability beginning with `can` must be `false` for S1. Record
counts, compared identifiers, discrepancies, source freshness, and any source
error under `evidence/s1/` without writing raw payloads or headers.

## 4. Restore

Stop S1 only after the launcher status proves that the process is launcher-owned:

```powershell
& $launcher status
& $launcher stop
```

Restore the profile, port variables, and non-secret allowlist environment state
captured in `preflight.json`. If the preflight had no managed `3101` process,
leave `3101` stopped; otherwise start the captured profile and verify its
reported profile. Keep dedicated acceptance records identifiable for S2 and do
not delete Prefect records.

Repeat the Phase 2 read and write `3100-after-s1.json` with the same sanitized
fields. A changed legacy status or an otherwise observable `3100` regression is
a hard stop. Record the S1 comparison and restore result under `evidence/s1/`.

## 5. S2 dedicated-resource setup

Use the Prefect authority to create only a dedicated, inert test flow, process
work pool, queue, deployment, and inactive interval schedule. Each name must
begin with `bogda-s2-acceptance-20260901-`; use the returned IDs and non-secret
names as the only S2 resource inputs. The pool concurrency limit is one and no
worker is attached. Record only returned IDs, names, and the inactive schedule
state in sanitized JSON under `evidence/s2/`.

Before starting the console, compare every proposed allowlist member with the
fresh test-resource inventory. A production resource, `pi-service`,
`dorm-x86`, an existing deployment, a resource name without the required
prefix, or an ID not returned for that prefixed resource is a non-test
allowlist member and is a hard stop.

Start exactly one loopback S2 replica with the four exact resource scopes:

```powershell
$env:BOGDA_CONSOLE_PROFILE = "allowlisted-test"
$env:BOGDA_CONSOLE_REPLICA_COUNT = "1"
$env:BOGDA_CONSOLE_PUBLIC_HOST = "127.0.0.1"
$env:BOGDA_CONSOLE_PUBLIC_PORT = "3101"
$env:BOGDA_CONSOLE_BFF_PORT = "3102"
$env:BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS = $testDeploymentId
$env:BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS = $testScheduleId
$env:BOGDA_CONSOLE_ALLOWED_QUEUE_IDS = $testQueueId
$env:BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES = $testWorkPoolName
& $launcher start
```

Confirm `/api/v1/capabilities` reports `allowlisted-test`, one replica, and
only the dedicated IDs/names. A replica count other than
`BOGDA_CONSOLE_REPLICA_COUNT=1` is a hard stop. No production allowlist member
may be used.

## 6. S2 command matrix/restore

Run each applicable command once through `3101`, capturing a sanitized receipt
and an authoritative post-read after each successful command:

| Resource | One command sequence | Required post-read |
| --- | --- | --- |
| Dedicated deployment | submit one run, then cancel that run | Prefect run ID and final state |
| Dedicated schedule | pause, then resume | schedule paused flag after each action |
| Dedicated queue | pause, then resume | queue paused flag after each action |
| Test RunResult Artifact | seed a test-only result, then submit one scientific review | latest artifact ID and review state |
| Checkpoint fixture | decide the documented test-only checkpoint, or record `inapplicable` with the exact missing runtime precondition | checkpoint decision or applicability record |

The command matrix must use only the dedicated S2 resources. A negative-path
check may submit one non-allowlisted, production-safe resource command only when
authorization rejects it before mutation; record the expected
`403 RESOURCE_NOT_ALLOWLISTED` and a no-mutation post-read. Do not retry a
command. A source error or a failed authoritative post-read is a hard stop.

After the matrix, record whether the dedicated schedule and queue are resumed
or paused, cancel any remaining dedicated run, and capture the final
non-secret resource states. Stop only the launcher-owned S2 process, restore
the captured preflight profile, and write `3100-after-s2.json` using the same
Phase 2 fields. Leave all dedicated S2 records identifiable; never delete
Prefect acceptance records. A `3100` regression is a hard stop. Store the
matrix receipts, post-reads, negative-path result, rollback state, and final
3100 check under `evidence/s2/`.
