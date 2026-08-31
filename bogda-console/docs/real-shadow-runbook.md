# Bogda Console real-shadow runbook

This is the bounded acceptance sequence for the console on `3101` against the
Prefect authority. S1 uses `real-readonly`; S2 uses `allowlisted-test` only for
dedicated prefixed test resources and exactly one replica. `mock-all` is a
fixture profile, not real-shadow evidence. Keep `3100` untouched: no cutover,
proxy, SSH, worker, or dorm-machine operation.

Run examples from the checkout root in one PowerShell session. They are
documentation examples and must not be run during this documentation task.
Evidence is sanitized JSON/text under exactly:

```text
.tasks/active/052_bogda-gate7-real-shadow/evidence/
```

Never save raw responses, headers, command lines, or environment dumps.
`PREFECT_API_AUTH_STRING` and `PREFECT_API_KEY` remain in the operator
environment; record availability booleans only, never their values.

The only operational hard stops are unknown `3101` ownership, a non-test
allowlist member, S2 replica count not equal to one, source errors, a failed
authoritative post-read, or a `3100` regression.

## 1. Ownership preflight

Use this one checked launcher helper for every `status`, `start`, and `stop`.
It captures the actual launcher-reported managed profile and refuses a foreign
listener or wrong expected profile before reads.

```powershell
$ErrorActionPreference = "Stop"
$RepoRoot = (Get-Location).Path
$ConsoleRoot = Join-Path $RepoRoot "bogda-console"
$EvidenceRoot = Join-Path $RepoRoot ".tasks\active\052_bogda-gate7-real-shadow\evidence"
$launcher = Join-Path $ConsoleRoot "scripts\local-console.ps1"
$Python = Join-Path $ConsoleRoot ".venv\Scripts\python.exe"
$restoreNames = @(
  "BOGDA_CONSOLE_PROFILE", "BOGDA_CONSOLE_PUBLIC_HOST", "BOGDA_CONSOLE_PUBLIC_PORT",
  "BOGDA_CONSOLE_BFF_PORT", "BOGDA_CONSOLE_REPLICA_COUNT",
  "BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS", "BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS",
  "BOGDA_CONSOLE_ALLOWED_QUEUE_IDS", "BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES"
)
New-Item -ItemType Directory -Force -Path (Join-Path $EvidenceRoot "s1"), (Join-Path $EvidenceRoot "s2") | Out-Null

function Invoke-CheckedLauncher {
  param([ValidateSet("status","start","stop")][string]$Action, [string]$ExpectedProfile)
  $text = (& $launcher $Action 2>&1 | Out-String).Trim()
  $exitCode = $LASTEXITCODE
  if ($Action -eq "status") {
    if ($exitCode -eq 3 -or $text -match "foreign-listener") { throw "HARD STOP: unknown 3101 ownership" }
    if ($exitCode -notin @(0,1,2)) { throw "HARD STOP: launcher status failed" }
    $statusMatch = [regex]::Match($text, '(?m)^status:\s*(?<value>\S+)\s*$')
    if (-not $statusMatch.Success -or $statusMatch.Groups["value"].Value -notin @("healthy","degraded","stopped")) { throw "HARD STOP: launcher ownership status unavailable" }
    $profileMatch = [regex]::Match($text, '(?m)^profile:\s*(?<value>\S+)\s*$')
    $profile = if ($profileMatch.Success) { $profileMatch.Groups["value"].Value } else { $null }
    if ($ExpectedProfile -and ($statusMatch.Groups["value"].Value -ne "healthy" -or $profile -ne $ExpectedProfile)) { throw "HARD STOP: launcher profile mismatch" }
    return [pscustomobject]@{ status = $statusMatch.Groups["value"].Value; profile = $profile }
  }
  if ($exitCode -ne 0) { throw "HARD STOP: launcher $Action failed" }
}

$envSnapshot = [ordered]@{}
foreach ($name in $restoreNames) {
  $item = Get-Item "Env:$name" -ErrorAction SilentlyContinue
  $envSnapshot[$name] = [ordered]@{ set = $null -ne $item; value = if ($null -ne $item) { [string]$item.Value } else { $null } }
}
$preflight = Invoke-CheckedLauncher status
$preflightEvidence = [ordered]@{
  launcherStatus = $preflight.status; launcherManagedProfile = $preflight.profile
  launcherEnv = $envSnapshot
  listener = @(Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 3101 -State Listen -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,OwningProcess)
  prefectApiAuthStringConfigured = [bool]$env:PREFECT_API_AUTH_STRING
  prefectApiKeyConfigured = [bool]$env:PREFECT_API_KEY
}
$preflightEvidence | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $EvidenceRoot "preflight.json") -Encoding utf8
```

Snapshot/restore is limited to these non-secret variables; set/unset presence is retained so later phases restore the operator shell exactly:

| Variable group | S1 change | S2 change | Restore |
| --- | --- | --- | --- |
| Profile and ports | profile `real-readonly`; loopback `3101`/`3102` | profile `allowlisted-test`; same ports | saved value or unset |
| Replica | unchanged | `BOGDA_CONSOLE_REPLICA_COUNT=1` | saved value or unset |
| Four allowlists | unset | exact returned deployment/schedule/queue/pool values | saved value or unset |
| Credentials | unchanged; availability boolean only | unchanged; availability boolean only | leave in operator environment |

## 2. 3100 before-check

Any non-200 result is the same `3100` regression hard stop.

```powershell
$check3100 = {
  param([string]$EvidenceName)
  try { $r = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:3100/ -TimeoutSec 5; $ok = ([int]$r.StatusCode -eq 200) }
  catch { $ok = $false }
  $summary = [ordered]@{ checkedAtUtc = (Get-Date).ToUniversalTime().ToString("o"); http200 = $ok }
  $summary | ConvertTo-Json | Set-Content (Join-Path $EvidenceRoot $EvidenceName) -Encoding utf8
  if (-not $ok) { throw "HARD STOP: 3100 regression" }
}
& $check3100 "3100-before.json"
```

For any S1/S2 source, receipt, or authoritative post-read failure, invoke this
path: it stops only launcher-owned process, restores captured non-secret values
and managed profile, rechecks 3100, and never deletes or natively rolls back.

```powershell
function Invoke-EmergencyRollback {
  $current = Invoke-CheckedLauncher status
  if ($current.status -in @("healthy","degraded")) { Invoke-CheckedLauncher stop }
  foreach ($name in $envSnapshot.Keys) { if ($envSnapshot[$name].set) { Set-Item "Env:$name" $envSnapshot[$name].value } else { Remove-Item "Env:$name" -ErrorAction SilentlyContinue } }
  if ($preflight.status -in @("healthy","degraded")) { Invoke-CheckedLauncher start; Invoke-CheckedLauncher status -ExpectedProfile $preflight.profile }
  & $check3100 "3100-after-emergency-rollback.json"
}
```

Repeat the same `http200`-only check as `3100-after-s1.json` in Phase 4 and as
`3100-after-s2.json` in Phase 6. Never stop, proxy, overwrite, or reconfigure
`3100`.

## 3. S1 start/read/compare

Stop a managed preflight process, then set only the S1 profile and ports. Do not
assign credentials, allowlists, or a DeepSeek key; the operator environment is
inherited by the launcher.

```powershell
if ($preflight.status -in @("healthy","degraded")) { Invoke-CheckedLauncher stop }
$env:BOGDA_CONSOLE_PROFILE = "real-readonly"
$env:BOGDA_CONSOLE_PUBLIC_HOST = "127.0.0.1"
$env:BOGDA_CONSOLE_PUBLIC_PORT = "3101"
$env:BOGDA_CONSOLE_BFF_PORT = "3102"
foreach ($name in @("BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS","BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS","BOGDA_CONSOLE_ALLOWED_QUEUE_IDS","BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES")) { Remove-Item "Env:$name" -ErrorAction SilentlyContinue }
Invoke-CheckedLauncher start
$s1Status = Invoke-CheckedLauncher status -ExpectedProfile "real-readonly"
```

Read `/api/v1/capabilities`, `/overview`, `/runs?limit=100`,
`/deployments?limit=100`, and `/infrastructure` from `3101`; save selected IDs,
counts, pool/queue/worker names, `state.type`, `state.name`, RunResult artifact
IDs, profile, and `can*` booleans only. A non-200 or malformed response is a
source error.

```powershell
$S1Evidence = Join-Path $EvidenceRoot "s1"
$projection = [ordered]@{
  capabilities = Invoke-RestMethod "http://127.0.0.1:3101/api/v1/capabilities"
  overview = Invoke-RestMethod "http://127.0.0.1:3101/api/v1/overview"
  runs = Invoke-RestMethod "http://127.0.0.1:3101/api/v1/runs?limit=100"
  deployments = Invoke-RestMethod "http://127.0.0.1:3101/api/v1/deployments?limit=100"
  infrastructure = Invoke-RestMethod "http://127.0.0.1:3101/api/v1/infrastructure"
}
$selected = @(
  @($projection.runs.data.items | % { @{ kind="run"; id=$_.runId } })
  @($projection.deployments.data.items | % { @{ kind="deployment"; id=$_.deploymentId } })
  @($projection.infrastructure.data.pools | % { @{ kind="pool"; id=$_.name } })
  @($projection.infrastructure.data.pools | % { $_.queues } | % { @{ kind="queue"; id=$_.queueId } })
)
if ($selected.Count -eq 0) { throw "HARD STOP: Prefect source error" }
$selected | ConvertTo-Json | Set-Content (Join-Path $S1Evidence "projection-selected.json") -Encoding utf8
```

Minimal direct authority example (the same selector is rerun for each
authoritative post-read):

```powershell
$authorityScript = @'
import asyncio, json, os, sys
from uuid import UUID
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.filters import ArtifactFilter, ArtifactFilterFlowRunId, ArtifactFilterKey, ArtifactFilterType
from prefect.client.schemas.sorting import ArtifactSort
async def main():
    kind, ident = sys.argv[1], sys.argv[2]
    auth, key = os.getenv("PREFECT_API_AUTH_STRING"), os.getenv("PREFECT_API_KEY")
    client = PrefectClient(os.environ["PREFECT_API_URL"], auth_string=auth) if auth else PrefectClient(os.environ["PREFECT_API_URL"], api_key=key)
    async with client:
        if kind == "run":
            x = await client.read_flow_run(UUID(ident))
            artifacts = await client.read_artifacts(artifact_filter=ArtifactFilter(key=ArtifactFilterKey(any_=[f"bogda-run-{x.id}"]), type=ArtifactFilterType(any_=["bogda.run-result"]), flow_run_id=ArtifactFilterFlowRunId(any_=[x.id])), sort=ArtifactSort.CREATED_DESC, limit=1)
            artifact_ids = [str(a.id) for a in artifacts]
            print(json.dumps({"runId":str(x.id), "deploymentId":str(x.deployment_id) if x.deployment_id else None, "stateType":str(x.state.type) if x.state else None, "stateName":x.state.name if x.state else None, "artifactIds":artifact_ids}, sort_keys=True))
        elif kind == "deployment":
            x = await client.read_deployment(UUID(ident)); ss = await client.read_deployment_schedules(x.id)
            print(json.dumps({"deploymentId":str(x.id), "schedules":[{"scheduleId":str(s.id), "active":s.active} for s in ss]}, sort_keys=True))
        elif kind == "queue":
            x = await client.read_work_queue(UUID(ident)); print(json.dumps({"queueId":str(x.id), "isPaused":x.is_paused}, sort_keys=True))
        elif kind == "pool":
            x = await client.read_work_pool(ident); ws = await client.read_workers_for_work_pool(x.name, limit=100)
            print(json.dumps({"name":x.name, "concurrencyLimit":x.concurrency_limit, "workerCount":len(ws)}, sort_keys=True))
asyncio.run(main())
'@
$authorityRecords = foreach ($item in $selected) {
  $authority = & $Python -c $authorityScript $item.kind $item.id 2>$null
  if ($LASTEXITCODE -ne 0 -or -not $authority) { throw "HARD STOP: Prefect source error" }
  ($authority -join "`n") | ConvertFrom-Json
}
$authorityRecords | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $S1Evidence "authority-post-read.json") -Encoding utf8
```

Compare projection and authority by ID, not list order, for deployment/run/
pool/queue/worker, state type/name, and RunResult IDs. Every S1 `can*` value is
false. A mismatch is a failed authoritative post-read.

## 4. Restore

Set `$continueWithS2 = $true` when Phase 5 follows immediately; use `$false`
only when ending after S1. Stop S1 through the helper in both cases. With S2
next, leave `3101` stopped and do not restore/restart the preflight profile yet.

```powershell
$continueWithS2 = $true
Invoke-CheckedLauncher stop
if (-not $continueWithS2) {
  foreach ($name in $envSnapshot.Keys) { if ($envSnapshot[$name].set) { Set-Item "Env:$name" $envSnapshot[$name].value } else { Remove-Item "Env:$name" -ErrorAction SilentlyContinue } }
  if ($preflight.status -in @("healthy","degraded")) { Invoke-CheckedLauncher start; Invoke-CheckedLauncher status -ExpectedProfile $preflight.profile }
}
& $check3100 "3100-after-s1.json"
```

When S1 ends here, restore the actual preflight managed profile, or leave `3101`
stopped if none existed; record comparison and restore under `evidence/s1/`.

## 5. S2 dedicated-resource setup

Use existing Prefect client methods in this compact, non-reusable recipe. Create
a flow, process pool, queue, deployment, and inactive interval schedule whose
names start with `bogda-s2-acceptance-20260901-`; set concurrency to 1 with no
worker. Return only these non-secret values:
`flowId/flowName`, `poolId/poolName`, `queueId/queueName`,
`deploymentId/deploymentName`, `scheduleId/scheduleSlug`, `scheduleActive`,
`concurrencyLimit`, and `workerCount`.

```python
# Existing PrefectClient, with PREFECT_API_URL and either credential inherited.
prefix = "bogda-s2-acceptance-20260901-<unique-suffix>"
flow_name = prefix + "flow"
flow_id = await client.create_flow_from_name(flow_name)
pool = await client.create_work_pool(WorkPoolCreate(name=prefix + "pool", type="prefect-process", concurrency_limit=1, is_paused=False))
queue = await client.create_work_queue(name=prefix + "queue", work_pool_name=pool.name, is_paused=True, concurrency_limit=1)
schedule_slug = prefix + "schedule"
schedule = DeploymentScheduleCreate(schedule=IntervalSchedule(interval=timedelta(days=3650)), active=False, slug=schedule_slug)
deployment_name = prefix + "deployment"
deployment_id = await client.create_deployment(flow_id=flow_id, name=deployment_name, work_pool_name=pool.name, work_queue_name=queue.name, schedules=[schedule], paused=True)
schedule_id = (await client.read_deployment_schedules(deployment_id))[0].id
print({"prefix": prefix, "flowId": flow_id, "flowName": flow_name, "poolId": pool.id, "poolName": pool.name, "queueId": queue.id, "queueName": queue.name, "deploymentId": deployment_id, "deploymentName": deployment_name, "scheduleId": schedule_id, "scheduleSlug": schedule_slug, "scheduleActive": False, "concurrencyLimit": 1, "workerCount": 0})
```

Do not print the client or environment. Bind the one sanitized recipe line, then
validate that its names and IDs are the resources being allowlisted:

```powershell
$recipeOutput = <one sanitized JSON line emitted by the recipe above>
$s2 = $recipeOutput | ConvertFrom-Json; $prefix = [string]$s2.prefix
foreach ($field in "flowName","poolName","queueName","deploymentName","scheduleSlug") { if (-not ([string]$s2.$field).StartsWith($prefix, [StringComparison]::Ordinal)) { throw "HARD STOP: non-test allowlist member" } }
if (@("flowId","poolId","queueId","deploymentId","scheduleId" | % { [string]::IsNullOrWhiteSpace([string]$s2.$_) }) -contains $true) { throw "HARD STOP: non-test allowlist member" }
if ($s2.scheduleActive -or $s2.concurrencyLimit -ne 1 -or $s2.workerCount -ne 0) { throw "HARD STOP: non-test allowlist member" }
$env:BOGDA_CONSOLE_PROFILE = "allowlisted-test"
$env:BOGDA_CONSOLE_REPLICA_COUNT = "1"
$env:BOGDA_CONSOLE_PUBLIC_HOST = "127.0.0.1"; $env:BOGDA_CONSOLE_PUBLIC_PORT = "3101"; $env:BOGDA_CONSOLE_BFF_PORT = "3102"
$env:BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS = $s2.deploymentId
$env:BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS = $s2.scheduleId
$env:BOGDA_CONSOLE_ALLOWED_QUEUE_IDS = $s2.queueId
$env:BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES = $s2.poolName
Invoke-CheckedLauncher start
Invoke-CheckedLauncher status -ExpectedProfile "allowlisted-test"
```

Record resource JSON under `evidence/s2/`; a replica count other than
`BOGDA_CONSOLE_REPLICA_COUNT=1` is a hard stop.

## 6. S2 command matrix/restore

Execute each row once through `3101`, capture `data.command` and
`data.resourceId`, then rerun the authority selector. A non-2xx command, missing
receipt, source error, or failed authoritative post-read is a hard stop.

| Action | 3101 endpoint and exact input | Authoritative post-read |
| --- | --- | --- |
| Submit | `POST /deployments/{deploymentId}/runs`, `{parameters:{}, idempotency_key:<unique>}` | returned `runId`, deployment ID, state type/name |
| Cancel | `POST /runs/{runId}/cancel`, `{expected_command_version:<fresh>}` | same run ID and terminal/cancelling state |
| Schedule pause/resume | `POST /deployments/{deploymentId}/schedules/{scheduleId}/{pause\|resume}`, fresh `expected_command_version` | deployment schedule ID and `active=false/true` |
| Queue pause/resume | `POST /work-queues/{queueId}/{pause\|resume}`, fresh `expected_command_version` | queue ID and `isPaused=true/false` |
| Scientific review | `POST /runs/{runId}/reviews`, `{base_artifact_id:<latest>, scientific_status:"inconclusive", review_summary:<test text>}` | latest RunResult artifact ID and run ID |
| Checkpoint | `POST /runs/{runId}/checkpoints`, `{expected_command_version:<fresh>, verdict:"approved", rationale:<test text>}` | run ID/deployment ID; or `inapplicable` with exact missing precondition |

Minimal receipt shape:

```powershell
$receipt = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:3101/api/v1/deployments/$deploymentId/runs" -ContentType "application/json" -Body (@{ parameters = @{}; idempotency_key = $idempotency } | ConvertTo-Json)
if ($null -eq $receipt.data.command -or $null -eq $receipt.data.resourceId) { throw "HARD STOP: failed authoritative post-read" }
$receipt.data | Select-Object command,resourceId | ConvertTo-Json | Set-Content (Join-Path $S2Evidence "receipt.json") -Encoding utf8
```

After submit, seed the RunResult Artifact with `key="bogda-run-$runId"`,
`type="bogda.run-result"`, and `flow_run_id=$runId`; seed the checkpoint fixture
with `key="bogda-decision-scientific_review-$runId"`,
`type="bogda.research-decision"`, `flow_run_id=$runId`, and `command_version`.
Record identifiers only; if the checkpoint is absent for this run, record
`inapplicable` and its exact missing precondition.

```python
# Existing PrefectClient; emit identifiers only, never artifact data.
artifact = await client.create_artifact(ArtifactCreate(key=f"bogda-run-{run_id}", type="bogda.run-result", data=test_result, flow_run_id=UUID(run_id)))
checkpoint = await client.create_artifact(ArtifactCreate(key=f"bogda-decision-scientific_review-{run_id}", type="bogda.research-decision", data={"kind":"scientific_review", "command_version":f"s2-checkpoint-{run_id}"}, flow_run_id=UUID(run_id)))
print({"runId": run_id, "artifactId": artifact.id, "checkpointArtifactId": checkpoint.id})
```

Before ending S2, record actual schedule/queue state, pool concurrency 1, worker
count 0, and all receipt/post-read IDs; cancel remaining nonterminal runs in the
prefixed deployment through the same path. Do not delete acceptance records.

```powershell
$deploymentId = [string]$s2.deploymentId; $poolName = [string]$s2.poolName
$remaining = (Invoke-RestMethod "http://127.0.0.1:3101/api/v1/runs?deploymentId=$deploymentId&limit=100").data.items
foreach ($run in @($remaining | Where-Object { -not $_.state.terminal })) {
  $cancel = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:3101/api/v1/runs/$($run.runId)/cancel" -ContentType "application/json" -Body (@{ expected_command_version = $run.commandVersion } | ConvertTo-Json)
  if ($null -eq $cancel.data.command -or $null -eq $cancel.data.resourceId) { throw "HARD STOP: failed authoritative post-read" }
  $cancelPost = Invoke-RestMethod "http://127.0.0.1:3101/api/v1/runs/$($run.runId)"
  $authority = & $Python -c $authorityScript "run" $run.runId 2>$null
  if ($LASTEXITCODE -ne 0 -or -not $authority) { throw "HARD STOP: Prefect source error" }
  $authorityPost = ($authority -join "`n") | ConvertFrom-Json
  if ((-not [bool]$cancelPost.data.run.state.terminal -and $cancelPost.data.run.state.name -ne "Cancelled") -or -not ($authorityPost.stateType -match "CANCELLED$" -or $authorityPost.stateName -match "Cancelled$")) { throw "HARD STOP: failed authoritative post-read" }
}
$finalDeployment = (Invoke-RestMethod "http://127.0.0.1:3101/api/v1/deployments/$deploymentId").data
$finalInfrastructure = (Invoke-RestMethod "http://127.0.0.1:3101/api/v1/infrastructure").data
$scheduleState = @($finalDeployment.schedules | Where-Object scheduleId -eq $s2.scheduleId)[0].active
$queueState = @(@($finalInfrastructure.pools | Where-Object name -eq $poolName)[0].queues | Where-Object queueId -eq $s2.queueId)[0].isPaused
$finalPool = @($finalInfrastructure.pools | Where-Object name -eq $poolName)[0]
$final = @{ deploymentId = $deploymentId; runId = $runId; scheduleActive = $scheduleState; queuePaused = $queueState; poolName = $poolName; concurrencyLimit = $finalPool.concurrencyLimit; workerCount = @($finalPool.workers).Count }
$final | ConvertTo-Json | Set-Content (Join-Path $S2Evidence "final-state.json") -Encoding utf8
Invoke-CheckedLauncher stop
foreach ($name in $envSnapshot.Keys) { if ($envSnapshot[$name].set) { Set-Item "Env:$name" $envSnapshot[$name].value } else { Remove-Item "Env:$name" -ErrorAction SilentlyContinue } }
if ($preflight.status -in @("healthy","degraded")) { Invoke-CheckedLauncher start; Invoke-CheckedLauncher status -ExpectedProfile $preflight.profile }
& $check3100 "3100-after-s2.json"
```

The final report records final states, sanitized evidence paths, rollback state,
checkpoint limitation, and identifiable dedicated S2 records.
