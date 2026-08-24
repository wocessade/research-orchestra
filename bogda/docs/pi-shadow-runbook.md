# Bogda Pi Shadow Operations Runbook

This runbook is for a future, reviewed Raspberry Pi deployment. It is not authorization to run the scripts on a Pi today. Local success does not prove ARM64 compatibility, systemd behavior, SSD mounting, Tailscale exposure, reboot persistence, or 72-hour stability.

Proceed through the gates in order. A hard failure stops the shadow deployment and returns operation to the existing system. Do not print, commit, or paste either Basic Auth value.

## Gate 1 — Local verification

From a reviewed Bogda checkout, verify the bundle and its shell boundary without installing anything:

```powershell
Set-Location bogda
$env:BOGDA_BASH = 'E:\Git\bin\bash.exe'
uv run --python 3.11 pytest -m "not integration" -v
uv run --python 3.11 python -m bogda.ops.bundle check deploy/pi
& $env:BOGDA_BASH -n deploy/pi/install.sh
& $env:BOGDA_BASH -n deploy/pi/rollback.sh
& $env:BOGDA_BASH deploy/pi/install.sh --dry-run
& $env:BOGDA_BASH deploy/pi/rollback.sh --dry-run
```

Record the reviewed commit and confirm that the dry-runs preserve /mnt/nas/.bogda. The dry-run preserves an existing runtime environment file and says that the sentinel example is installed only when that file is absent. Do not treat this gate as evidence for the Pi-specific properties listed above.

On the future Linux/Pi runner, exercise the deferred symlink regression as well:

```sh
cd /path/to/reviewed/bogda
BOGDA_BASH=/bin/bash uv run --python 3.11 pytest tests/ops/test_snapshot.py -k symlink -v
```

## Gate 2 — Manual Pi preflight

On the Pi, collect and retain these read-only facts before any installation. The commands have not been run by this local bundle work.

```sh
uname -m
python3 --version
python3 -c 'import sys; assert sys.version_info >= (3, 11), sys.version'
findmnt -no SOURCE,FSTYPE,UUID --target /mnt/nas
lsblk -o NAME,SERIAL,UUID,PARTUUID,FSTYPE,MOUNTPOINTS
df -B1 --output=source,avail,target /mnt/nas
tailscale status --json
tailscale ip -4
tailscale netcheck
command -v uv
uv --version
systemd-analyze verify \
  deploy/pi/systemd/bogda-prefect-server.service \
  deploy/pi/systemd/bogda-pi-worker.service \
  deploy/pi/systemd/bogda-prefect-snapshot.service \
  deploy/pi/systemd/bogda-prefect-snapshot.timer \
  deploy/pi/systemd/bogda-shadow-health.service \
  deploy/pi/systemd/bogda-shadow-health.timer
rc=$?
printf 'verify_exit=%s\n' "$rc"
```

Expected facts: uname -m is aarch64; Python is 3.11 or newer; /mnt/nas is an approved local SSD partition with FSTYPE ext4; its UUID/PARTUUID and source match the approved SSD and /etc/fstab; and the available-byte value has capacity for the approved 72-hour evidence plus seven snapshots. Record the Tailscale identity, tailnet IPv4 address, and netcheck output; it must show the approved tailnet rather than an unreviewed public exposure. A missing mount, wrong source/identity, non-ext4 filesystem, or inadequate capacity is a hard failure.

uv is a Gate 3 install prerequisite. Record `command -v uv` and `uv --version`. If uv is missing, stop and obtain separate authorization to install it; install.sh must not fetch uv from the network on its own. This Pi already has owner-authorized uv 0.12.5 at /usr/local/bin, so this change does not install uv again.

systemd-analyze verify must still run on all six reviewed unit files. Record the command, the time, and verify_exit. The units are statically checked locally; this command is the Pi gate for actual systemd parsing. Before installation, command resolution may fail only because /opt/bogda/.venv/bin/python does not exist and/or /opt/bogda/.venv/bin/prefect does not exist. Those expected absences may make verify_exit=1 and are not a Gate 2 hard failure. Unknown keys, illegal sections, or any other command errors on Bogda units remain hard failures. Timezone ignoring warnings from already-installed non-bogda units are recorded and are not Bogda failures. Do not treat Gate 2 as the command-resolution acceptance gate. Check available memory as an observation threshold: less than 400 MB available requires investigation, but is not by itself a hard failure.

## Gate 3 — Install without start

Run the installer without any start flag as root:

```sh
cd /path/to/reviewed/bogda
sudo deploy/pi/install.sh --install
systemd-analyze verify \
  /etc/systemd/system/bogda-prefect-server.service \
  /etc/systemd/system/bogda-pi-worker.service \
  /etc/systemd/system/bogda-prefect-snapshot.service \
  /etc/systemd/system/bogda-prefect-snapshot.timer \
  /etc/systemd/system/bogda-shadow-health.service \
  /etc/systemd/system/bogda-shadow-health.timer
rc=$?
printf 'verify_exit=%s\n' "$rc"
stat -c '%a %U %G %n' /etc/bogda/bogda.env
cat /etc/bogda/last-backup
cat "$(cat /etc/bogda/last-backup)/inventory.tsv"
```

The installer rejects a symlinked managed unit target, environment target, or last-backup pointer before it changes the host. It saves the prior managed files in /etc/bogda/backups/<UTC timestamp>/inventory.tsv and records that directory in /etc/bogda/last-backup. Confirm every one of the six unit paths and /etc/bogda/bogda.env has an accurate present or absent inventory row. An existing runtime environment file is preserved; the sentinel example is installed only when the file is absent. Verify the resulting env-file mode is 640 and its owner/group are root bogda before a new installation proceeds.

After --install and before any --start* flag, re-run systemd-analyze verify on the installed unit paths and record verify_exit. This run must exit 0. The output must not report /opt/bogda/.venv/bin/python or /opt/bogda/.venv/bin/prefect as not executable. If either command is still missing, or verify_exit is not 0, stop. Do not enter Gate 4 and do not run --start-server or --start-services. Command resolution is accepted here, not at Gate 2. Timezone ignoring warnings from already-installed non-bogda units are still recorded and are not Bogda failures.

## Gate 4 — Configure auth, check static exposure, then start only the server

Use an approved secret-handling path to replace sentinel values in /etc/bogda/bogda.env. Its runtime contract is exactly four assignments: the fixed PREFECT_HOME, fixed PREFECT_API_URL, one nonempty PREFECT_SERVER_API_AUTH_STRING, and one matching nonempty PREFECT_API_AUTH_STRING; no duplicate, extra, or malformed entries are allowed. Do not echo the file or either credential.

Before starting a listener, retain the static Tailscale, ACL, and firewall facts:

```sh
tailscale status --json
tailscale serve status
sudo nft list ruleset
sudo iptables -S
```

Confirm the static policy has no approved public inbound path to TCP 4200 and restricts the intended API path to the reviewed tailnet/private boundary. If the platform does not use nftables or iptables, record its deployed firewall tool and equivalent read-only rule dump before continuing.

Preserve the rollback pointer, start only the authenticated server, and confirm its local service state:

```sh
before_backup="$(sudo cat /etc/bogda/last-backup)"
sudo deploy/pi/install.sh --start-server
test "$before_backup" = "$(sudo cat /etc/bogda/last-backup)"
systemctl is-active bogda-prefect-server.service
```

The start-only command validates the runtime environment before it starts the server and never creates a new backup or reinstalls files. On an authorized tailnet client, set PI_TAILNET_IP to the recorded Pi Tailscale IPv4 address and run the authenticated live test without exposing the credential:

```sh
read -r -s -p 'Prefect Basic Auth user:password: ' AUTH_PAIR; printf '\n'
curl --fail --silent --show-error --user "$AUTH_PAIR" "http://$PI_TAILNET_IP:4200/api/health"
unset AUTH_PAIR
```

The authenticated health request must succeed, but `/api/health` may be intentionally anonymous and therefore does not prove that API authentication is enforced. Verify authentication separately against a protected endpoint such as `POST /api/flows/count`: the authenticated request must return 200 and the same request without credentials must return 401 or 403.

From a client that is not on the tailnet, run the reachability-negative test; any HTTP response is a hard failure, while transport failure with no response is expected:

```sh
http_code="$(curl --connect-timeout 5 --max-time 10 --silent --show-error \
  --output /dev/null --write-out '%{http_code}' \
  "http://$PI_TAILNET_IP:4200/api/health")"
curl_status=$?
if [ "$http_code" != "000" ]; then
  echo "unexpected non-tailnet API HTTP response: $http_code" >&2
  exit 1
fi
if [ "$curl_status" -eq 0 ]; then
  echo 'unexpected non-tailnet API reachability without an HTTP response' >&2
  exit 1
fi
echo 'non-tailnet API transport is unreachable as expected'
```

Do not add `--fail` to this negative test: an HTTP 401/403 is still proof that the API is reachable and must fail the gate. Curl's `000` code plus a nonzero transport status is the expected no-response case.

## Gate 5 — Rotate trial evidence, then start worker and timers

Each 72-hour trial uses a fresh health JSONL file. Archive any prior file before starting the worker or timers so summarize is unbounded but cannot mix trials:

```sh
trial_id="$(date -u +%Y%m%dT%H%M%SZ)"
health_root=/mnt/nas/.bogda/manifests/health
sudo install -d -o bogda -g bogda -m 0750 "$health_root/archive"
if sudo test -e "$health_root/samples.jsonl"; then
  sudo mv "$health_root/samples.jsonl" "$health_root/archive/samples-$trial_id.jsonl"
fi
sudo touch "$health_root/samples.jsonl"
sudo chown bogda:bogda "$health_root/samples.jsonl"
sudo chmod 0640 "$health_root/samples.jsonl"
```

Then start only the worker and timers. The pre-existing server must already be active.

```sh
before_backup="$(sudo cat /etc/bogda/last-backup)"
sudo deploy/pi/install.sh --start-services
test "$before_backup" = "$(sudo cat /etc/bogda/last-backup)"
systemctl status \
  bogda-prefect-server.service \
  bogda-pi-worker.service \
  bogda-prefect-snapshot.service \
  bogda-prefect-snapshot.timer \
  bogda-shadow-health.service \
  bogda-shadow-health.timer
```

Confirm the worker and both timers are enabled and active as appropriate, no unit is repeatedly restarting, and no new backup pointer was created. This is a shadow operation: it must not replace the established production workflow.

## Gate 6 — 72-hour collection, reboot, snapshot, and restore drill

Collect the active trial for at least 72 hours. Produce the exact health summary and retain its JSON output with the trial record:

```sh
/opt/bogda/.venv/bin/python -m bogda.ops.health summarize \
  --input /mnt/nas/.bogda/manifests/health/samples.jsonl
```

Evaluate every summary field against this acceptance table. A documented controlled reboot may increment oom_kill_counter_reset_count; it never excuses a positive OOM delta or an unavailable OOM evidence span.

| Summary field | Acceptance check |
|---|---|
| started_at, ended_at | Span covers the recorded 72-hour trial window. |
| sample_count | Consistent with the five-minute cadence and recorded downtime. |
| missing_intervals | Zero, or every gap has a recorded and approved explanation. |
| api_failure_count | Zero; any failure is investigated before acceptance. |
| api_latency_p95_ms | Common API operations remain approximately one second or less; investigate a value above 1000 ms. |
| min_mem_available_bytes | Record the minimum; 400 MB is an observation threshold, not an automatic failure. |
| swap_growth_bytes | No sustained or unexplained swap growth/thrashing. |
| oom_kill_delta | Exactly 0; any positive value is a hard failure. |
| oom_kill_counter_reset_count | Matches only the documented controlled reboot; unexpected resets are investigated. |
| oom_kill_unavailable_span_count | Exactly 0; unavailable OOM evidence blocks acceptance. |
| database_integrity_failure_count | Exactly 0; any failure is a hard failure. |
| min_disk_free_bytes | Remains above the capacity approved in Gate 2; a missing SSD mount is a hard failure. |

During the window, perform one controlled reboot. After it returns, confirm all six Bogda unit states, the approved ext4 mount identity, and the queued/history state:

```sh
systemctl status \
  bogda-prefect-server.service \
  bogda-pi-worker.service \
  bogda-prefect-snapshot.service \
  bogda-prefect-snapshot.timer \
  bogda-shadow-health.service \
  bogda-shadow-health.timer
findmnt -no SOURCE,FSTYPE,UUID --target /mnt/nas
```

Record the inspected Prefect queue and history result from the authenticated tailnet client. They must still be present after reboot.

Create and verify a snapshot without touching the live database. The first command prints the snapshot report; retain it, then derive the snapshot path from latest.json and use its adjacent manifest for verification:

```sh
/opt/bogda/.venv/bin/python -m bogda.ops.snapshot create \
  --source /mnt/nas/.bogda/prefect/prefect.db \
  --destination /mnt/nas/.bogda/snapshots \
  --keep 7
snapshot_path="$(python3 -c 'import json; print(json.load(open("/mnt/nas/.bogda/snapshots/latest.json", encoding="utf-8"))["snapshot"])')"
snapshot_manifest="${snapshot_path%.db}.json"
/opt/bogda/.venv/bin/python -m bogda.ops.snapshot verify \
  --snapshot "$snapshot_path" \
  --manifest "$snapshot_manifest" \
  --restore-dir /mnt/nas/.bogda/restore-drill
```

The verification report must show integrity_check equal to ok. An unrestorable snapshot, corrupt database, missing SSD, or any OOM is a hard failure.

## Gate 7 — Decision: accept, return, or rollback

Accept only after every preceding gate is recorded and no hard failure occurred. Otherwise return to the existing production-only operation. When reverting the installed Pi boundary, inspect the planned scope first and then apply it:

```sh
sudo deploy/pi/rollback.sh --dry-run
sudo deploy/pi/rollback.sh --apply
```

Rollback stops/disables only the four startable Bogda units, restores or removes only the six managed unit files and /etc/bogda/bogda.env according to the original recorded inventory, reloads systemd, and preserves /mnt/nas/.bogda. It does not remove program or data directories.

## Deferred work

- Actual Pi deployment and 72-hour acceptance
- Wake Bridge/WoL
- Laptop dorm-x86
- Windows Power Agent/game mode
- Task migration
- CPU/GPU worker and higher concurrency
- SLC/pSLC purchase
- 3100 cutover
- CLI error polish
- Streaming logs
- Review, merge, and regression of bogda-console
