# Sysmon — process provenance setup (audit item 6)

Status: **placeholder** (narrow config + CSV parser shipped in
`dhriti/adapters/observation/external.py`).

## What it gives Dhriti

Process creation/termination with **ProcessGuid/ParentGuid** lineage —
the "IDE -> browser -> terminal" provenance graph of dossier 4.2,
joinable with browser events from the extension. PIDs alone are not
stable identifiers; GUIDs are.

## Steps (manual, admin)

1. Download Sysmon: https://learn.microsoft.com/sysinternals/downloads/sysmon
2. Install with the shipped narrow profile:
   `sysmon64 -accepteula -i dhriti-sysmon-config.xml`
3. Export events on a cadence (Task Scheduler or manual):
   `wevtutil epl "Microsoft-Windows-Sysmon/Operational" events.evtx`
   Convert to CSV (EvtxECmd / PowerShell) into your export dir.
4. Configure the adapter:

```json
"sysmon": {"enabled": true, "export_dir": "C:/Tools/dhriti-sysmon-out"}
```

5. `dhriti adapter status` → INSTALLED. Parsed files are archived to
   `export_dir/parsed/` so nothing is ingested twice.

## Dossier cautions (D-009, 2.3)

- Sysmon shows process/system telemetry, NOT foreground attention or
  page content. Missing telemetry is `MISSING`, never "inactivity".
- Measure log volume over one workday before widening filters.
- Sysmon Modular research configs are reference only.
