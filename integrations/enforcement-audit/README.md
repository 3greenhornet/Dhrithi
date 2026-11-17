# Enforcement backend audit — mapping to your Manual Audit Queue

Your `DHRITI_MANUAL_AUDIT_QUEUE.md` (preserved at
`source-material/`) drives everything in this folder. The decision
register is explicit (D-005/D-006): **no external enforcement backend
is adopted from its README.** Each candidate gets a controlled
experiment, and the result template below.

## Current adapter status (v1 defaults)

| Tool | Adapter | Default | Gate |
|---|---|---|---|
| Focuser | `focuser` | disabled | audit item 1: source audit + Defender report + Windows trial |
| FocusMe | `focusme` | disabled | audit item 2: CLI reality vs marketing |
| Cold Turkey | `cold_turkey` | disabled | audit item 2: locked blocks, Micromanager |
| Plucky | `plucky` | disabled | audit item 3: delay semantics in disposable config |
| Safe Exam Browser | — | — (not an adapter; E3 pattern) | audit item 4: kiosk work environment |

## Enabling one after its audit passes

```json
"adapters": {
  "focusme": {
    "enabled": true,
    "executable": "C:\\Program Files\\FocusMe\\FocusMe.exe",
    "arm_cmd": ["C:\\Program Files\\FocusMe\\focusme-cli.exe", "plan", "start", "deepwork"],
    "disarm_cmd": ["C:\\Program Files\\FocusMe\\focusme-cli.exe", "plan", "stop"]
  }
}
```

Then `dhriti adapter status` → INSTALLED, and (only if you choose)
add `"focusme"` to `enforcement.required_adapters`. If a required
adapter fails to arm, sessions fail arming honestly — never silently.

## What the adapter does NOT claim

- It cannot verify the external tool actually blocked anything; it
  records that the command ran with exit 0. The bypass tests in the
  audit queue are how you know what the tool really does.
- "Bypass observed but logged" is the honest ceiling of every local
  tool (dossier 2.7).
