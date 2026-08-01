# Flux UI tablet dashboard versions

`../flux_ui_tablet.yaml` is the **baseline** (source of truth) deployed to
`/flux-ui-tablet`. Normal deploys load that file; they do **not** regenerate
the tablet from Python builders.

## Files

| File | Purpose |
|------|---------|
| `2026-08-01_baseline.yaml` | Frozen snapshot of the live design captured as the initial baseline |
| `YYYYMMDDTHHMMSSZ_<label>.yaml` | Automatic snapshots taken before the baseline is replaced |
| `MANIFEST.json` | Index of baseline + snapshots |

## Commands

```bash
# Snapshot current baseline before editing
python3 scripts/deploy_flux_ui.py --snapshot-tablet-yaml --label before-my-change

# Pull live HA tablet into baseline (snapshots first)
python3 scripts/deploy_flux_ui.py --pull-tablet-yaml

# Regenerate from Python builders (snapshots first — use sparingly)
python3 scripts/deploy_flux_ui.py --rebuild-tablet-yaml
```

Any intentional replacement of `flux_ui_tablet.yaml` should leave a new file
in this directory so the previous design can be restored.
