# Bogda Pi Shadow Operations Runbook

This runbook is for a future, reviewed Raspberry Pi deployment. It is not authorization to run the scripts on a Pi today. Local success does not prove ARM64 compatibility, systemd behavior, SSD mounting, Tailscale exposure, reboot persistence, or 72-hour stability.

Proceed through the gates in order. A hard failure stops the shadow deployment and returns operation to the existing system.

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

Record the reviewed commit and confirm that the dry-runs preserve `/mnt/nas/.bogda`. Do not treat this gate as evidence for the Pi-specific properties listed above.

## Gate 2 — Manual Pi preflight

On the Pi, first confirm the intended checkout, `python3`, `uv`, and the fixed six-unit bundle inventory:

```sh
findmnt -no FSTYPE /mnt/nas
systemd-analyze verify \
  deploy/pi/systemd/bogda-prefect-server.service \
  deploy/pi/systemd/bogda-pi-worker.service \
  deploy/pi/systemd/bogda-prefect-snapshot.service \
  deploy/pi/systemd/bogda-prefect-snapshot.timer \
  deploy/pi/systemd/bogda-shadow-health.service \
  deploy/pi/systemd/bogda-shadow-health.timer
```

`findmnt -no FSTYPE /mnt/nas` must equal `ext4`. A missing SSD mount is a hard failure. Before installing units, retain the output of `systemd-analyze verify` for the reviewed checkout's six unit files; repeat verification against `/etc/systemd/system/bogda-*` after Gate 3. Check available memory as an observation threshold: less than 400 MB available requires investigation, but is not by itself a hard failure.

## Gate 3 — Install without start

Run the installer without `--start` as root:

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
stat -c '%a %U %G %n' /etc/bogda/bogda.env
```

The installer saves the prior managed files in `/etc/bogda/backups/<UTC timestamp>/inventory.tsv` and records that directory in `/etc/bogda/last-backup`. Confirm every one of the six unit paths and `/etc/bogda/bogda.env` has an accurate `present` or `absent` inventory row. An existing `/etc/bogda/bogda.env` is preserved; the sentinel example is installed only when the file is absent. Verify the resulting env-file mode is `640` and its owner/group are `root bogda` before a new installation proceeds. Never paste or print its auth values.

## Gate 4 — Auth and Tailscale exposure check

Replace any sentinel auth values in `/etc/bogda/bogda.env` through an approved secret-handling path. Confirm no `SET_ON_PI_NOT_IN_GIT` value remains. Confirm the API is inaccessible from the public internet and is exposed only through the intended Tailscale/private path; test this from a network that is not on the tailnet as well as from an authorized client. Do not advance if public access succeeds or credentials remain sentinel values.

## Gate 5 — Shadow start

Start only after Gates 1–4 are recorded:

```sh
cd /path/to/reviewed/bogda
sudo deploy/pi/install.sh --install --start
systemctl status \
  bogda-prefect-server.service \
  bogda-pi-worker.service \
  bogda-prefect-snapshot.service \
  bogda-prefect-snapshot.timer \
  bogda-shadow-health.service \
  bogda-shadow-health.timer
```

Confirm that the server, worker, snapshot timer, and health timer are enabled and active as appropriate, and that no unit is repeatedly restarting. This is a shadow operation: it must not replace the established production workflow.

## Gate 6 — 72-hour collection, reboot, snapshot, and restore drill

Collect health summary JSON and system status for at least 72 hours. The health summary JSON must show an OOM delta of zero and no database-integrity failures. OOM is a hard failure; a corrupt database is a hard failure.

During the window, perform a controlled reboot. After it returns, confirm `systemctl status` for all six Bogda units, the queued/history state is present after reboot, and the data remains on the ext4 SSD mount. Create a snapshot, restore it into the approved drill location, and verify the restored snapshot reports integrity `ok`. An unrestorable snapshot is a hard failure.

Record available-memory observations; 400 MB available memory remains an observation threshold, not an automatic acceptance criterion. Do not accept a shadow deployment that has an OOM, missing SSD, corrupt database, or failed restore drill.

## Gate 7 — Decision: accept, return, or rollback

Accept only after every preceding gate is recorded and no hard failure occurred. Otherwise return to the existing production-only operation. When reverting the installed Pi boundary, inspect the planned scope first and then apply it:

```sh
sudo deploy/pi/rollback.sh --dry-run
sudo deploy/pi/rollback.sh --apply
```

Rollback stops/disables only the four startable Bogda units, restores or removes only the six managed unit files and `/etc/bogda/bogda.env` according to the recorded inventory, reloads systemd, and preserves `/mnt/nas/.bogda`. It does not remove program or data directories.

## Deferred work

- Actual Pi deployment and 72-hour acceptance
- Wake Bridge/WoL
- Laptop `dorm-x86`
- Windows Power Agent/game mode
- Task migration
- CPU/GPU worker and higher concurrency
- SLC/pSLC purchase
- 3100 cutover
- CLI error polish
- Streaming logs
- Review, merge, and regression of `bogda-console`
