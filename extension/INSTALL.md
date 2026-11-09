# Dhriti Wall — Install (one manual step)

A Manifest V3 Chrome/Edge/Brave extension. The boring wall: it blocks
what the daemon says to block and shows your own contract line. Nothing
else. No popup, no options page, no counts, no reasons.

## 1. Start the daemon first

```
python -m dhriti.cli daemon
```

The daemon listens on `http://127.0.0.1:7311` and creates a token file
at `~/.dhriti/bridge_token` (or `$DHRITI_HOME/bridge_token`).

## 2. Paste the bridge token

Open `extension/config.js` and replace `PASTE_BRIDGE_TOKEN_HERE` with
the contents of the token file. Keep the quotes.

## 3. Load the extension

Chrome/Edge/Brave → `chrome://extensions` → enable **Developer mode** →
**Load unpacked** → select this `extension/` folder.

Done. The badge shows `D` while the wall is up (state, not judgement)
and nothing while dormant.

## How it behaves

| Situation | Behaviour |
|---|---|
| Day OPEN, daemon alive | blocks blocked_domains; redirects to the wall page |
| Day OPEN, daemon dead | keeps enforcing from cache **until the policy TTL expires** |
| Policy TTL expired | stops enforcing (a dead daemon can never lock you out forever) |
| No day OPEN | dormant — nothing is blocked |
| Extension removed | the daemon records the absence (tamper-evident, not tamper-proof) |

## What it does NOT do

- No reason strings on the wall page (Wall Principle).
- No break-glass button here — the toll lives in the CLI
  (`dhriti break-glass`), not in the browser.
- No content inspection, no keylogging, no history scraping beyond
  navigation events posted to your own local daemon.

## Lineage

This replaces the earlier "Intent Lock" prototype (PDF section 4): same
default-deny idea, now contract-driven, day-window aware, fail-safe,
and silent. `declarativeNetRequest` is actually used this time.
