# Flux UI tablet dashboard versions

`../flux_ui_tablet.yaml` is the **LOCKED baseline** (source of truth) deployed
to `/flux-ui-tablet`.

Normal deploys and browser refreshes load/push that exact file. They do **not**
regenerate layout, gaps, spacings, or sizings from Python builders.

`MANIFEST.json` stores `layout_lock_sha256`. Deploy aborts if the loaded YAML
does not match that fingerprint.

## Files

| File | Purpose |
|------|---------|
| `2026-08-01_baseline.yaml` | Frozen snapshot of the live design captured as the initial baseline |
| `YYYYMMDDTHHMMSSZ_<label>.yaml` | Automatic snapshots taken before the baseline is replaced |
| `MANIFEST.json` | Index of baseline + snapshots + layout lock hash |

## Commands

```bash
# Snapshot current baseline before editing
python3 scripts/deploy_flux_ui.py --snapshot-tablet-yaml --label before-my-change

# Pull live HA tablet into baseline (UNLOCK required — replaces locked layout)
python3 scripts/deploy_flux_ui.py --pull-tablet-yaml --replace-locked-tablet-baseline

# Regenerate from Python builders (UNLOCK required — use only via Cursor agent)
python3 scripts/deploy_flux_ui.py --rebuild-tablet-yaml --replace-locked-tablet-baseline
```

Approved layout changes: ask the Cursor agent. After editing
`flux_ui_tablet.yaml` directly, refresh the lock:

```bash
python3 scripts/deploy_flux_ui.py --relock-tablet-baseline --label my-change
```

`--rebuild-tablet-yaml` / `--pull-tablet-yaml` also refresh the lock when
passed with `--replace-locked-tablet-baseline`.
