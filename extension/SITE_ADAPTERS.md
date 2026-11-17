# Site adapters — the plugin slot

The guard's per-site knowledge lives in ONE object in
`extension/chatguard_content.js` (`ADAPTERS`). Adding a site = adding an
object. No other file changes. This is the same discipline as the core's
adapter registry (`manifest()` capability declarations + arming gate).

## Field contract

| Field | Meaning | Missing it means |
|---|---|---|
| `input` | selector for the prompt textarea / contenteditable | guard cannot hold anything (probe fails: `input`) |
| `sendBtn` | selector for the send control | Enter-gate still works; button path blind |
| `transcript` | selector for the conversation container | leak detection + collapse-seal blind |
| `userMsg` | selector for user messages | transcript-diff truth unavailable (event hooks only) |
| `assistantMsg` | selector for assistant messages | collapse-seal + length governor unavailable |
| `chips` | selector for follow-up suggestion chips | bait stays visible (D-032 gap) |
| `stopBtn` | selector for the streaming stop control | stream abort via UI unavailable |

`generic` is the fallback: Enter-count + transcript heuristics only. It is
honest about what it cannot see — the probe reports `blind` and the digest
flags it (never silent).

## Probe + canary

- `probe()` runs at load: reports which of input/send/transcript were
  found. Missing items are recorded by the bridge as
  `guard_adapter_blind` (fail-visible, D-077).
- A hidden `.dhriti-canary` marker is injected into the transcript. If it
  disappears mid-session (site re-render, redesign), the extension reports
  `guard_dom_canary_missing` — staleness is an event, not a discovery.

## Maintenance expectation

All four sites redesign often (Gemini's open shadow roots are the worst —
`pierce()` handles open roots only). Budget one repair evening a month;
the complexity budget field in the contract should count these hours.

## Known gap: leak paths

The send button is NOT the only send path. The transcript-diff
(`diffTranscript`) is the source of truth: any user message whose hash is
not in the approved set triggers a `guard_leak` and the following response
is collapse-sealed. Edit-resend, regenerate, and follow-up chips are all
covered by the diff — the chips are additionally hidden outright.
