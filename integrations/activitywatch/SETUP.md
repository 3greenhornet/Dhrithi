# ActivityWatch — observation adapter setup

Status: **placeholder until installed** (the REST client is fully
implemented in `dhriti/adapters/observation/activitywatch.py`).

## Install (manual step)

1. Download from https://github.com/ActivityWatch/activitywatch/releases
   (or activitywatch.net). Windows: unzip, run
   `activitywatch.exe`.
2. Install the browser extension (Aw Watcher) for URL/title events,
   and point it at your local server (default 127.0.0.1:5600).
3. Verify: open http://127.0.0.1:5600 — you should see the web UI.

## Enable in Dhriti

Edit `~/.dhriti/dhriti.config.json`:

```json
"adapters": {
  "activitywatch": {
    "enabled": true,
    "url": "http://127.0.0.1:5600"
  }
}
```

Then:

```
dhriti adapter status   # probe must say INSTALLED
```

The daemon now pulls window/afk/browser events every tick into the
normalized ledger. Nothing leaves your machine.

## Dossier notes (D-009)

- Do not run redundant trackers: if ActivityWatch covers windows + web,
  you do not also need another observer for those sources.
- Compare with a minimal native observer before adding anything
  heavier (audit item 5).
- Watch CPU/RAM over a workday; record it in your audit notes.
