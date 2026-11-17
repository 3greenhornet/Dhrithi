# Dhriti · Google Images vertical exile (D-082)

Blocks the Google Images rabbit-hole entry entirely — the tab chip, the
homepage link, `images.google.com`, `/imghp`, `imgres`, the current `udm=2`
vertical, the legacy `tbm=isch` param, Google Lens, and the thumbnail CDN —
in **one policy layer plus three rings**, so a miss in one ring still cannot
produce a scrollable images grid, and private/incognito windows cannot bypass
anything.

## The exploit this closes

Search something legitimate → click the Images chip → autoplaying media grid
→ every tile leads to a different domain → time gone. The Images vertical is
an entry point to arbitrary domains under the cover of "just searching".

Why keyword/semantic URL blocking (e.g. Cold Turkey's `*comic*`) fails here:
the Batman comic lives on `freebook-read-online.example` (no keyword in the
host), and worse, the whole strip can be consumed inside the Images grid via
thumbnails without ever opening any external site. Blocking the **vertical
itself, regardless of query**, is the only content-blind mechanism that holds
— which is exactly what `udm=2`/`tbm=isch` blocking does.

## Three niche facts (why naive blocks fail)

1. **Google Images is not a separate domain anymore.** It is
   `www.google.com/search?...&udm=2` (current) or `&tbm=isch` (legacy) — the
   same host as your legitimate searches. Hosts-file blocking alone cannot
   separate them; only URL-level rules can. Both params must be covered.
2. **Thumbnails come from `encrypted-tbn0..3.gstatic.com`.** Blocking that CDN
   empties any Images grid that somehow renders — nothing to scroll.
3. **Secure DNS (DoH) silently bypasses the hosts file.** If Chrome's
   "Secure DNS" is on, ring 1 does nothing and the block "mysteriously"
   fails. Keep Secure DNS OFF: `chrome://settings/security` → "Use secure
   DNS" → disabled. (Same for Firefox's DoH setting.)

## Layer 0 + the rings

| Layer | Level | What it kills | Incognito-proof | Where |
|-------|-------|---------------|-----------------|-------|
| 0 | machine policy (above browser toggles) | private/incognito windows disabled; DoH forced off; `images.google.com`, `lens.google.com`, `udm=2`, `tbm=isch`, `/imghp`, `/imgres` in URLBlocklist | yes — policies apply to all windows and cannot be toggled off without deleting registry keys | `windows-policy-layer.cmd` |
| 1 | hosts file (E2) | entry hosts + thumbnail CDN; canary proves liveness | yes — OS-level DNS (with DoH forced off by Layer 0) | `e2_images_block.py` |
| 2 | extension DNR rules (E1) | Images URLs by host + `tbm=isch`/`udm=2` param, any Google TLD listed | yes if "Allow in Incognito" is on (redundant once Layer 0 exists) | `rules/images-block-rules.json` |
| 3 | content script (E1) | if a page still loads: `window.stop()`, DOM wiped, faced wall card + Park button; sweeps Images chips off normal pages; capture-phase click interception | same as ring 2 | `content/images-wall.js` |

**URLBlocklist query matching is token-based and order-insensitive** (verified
against the official filter format): the pattern `google.com/search?udm=2`
matches the param in any position — `?udm=2&q=...`, `?aep=16&sxsrf=...&udm=2&q=...`,
`?q=...&udm=2` — and normal search without the token is untouched. This is
stronger than wildcard substring patterns like `google.*/*&udm=2&*`, which
fail when the param is first or last (no `&` on both sides).

Layer independence: extension removed or disabled → Layer 0 + ring 1 still
kill entries, params, and thumbnails. Hosts wiped (AV cleaner, manual edit) →
Layer 0 still blocks by URL and rings 2+3 still block by URL. Layer 0 is
fail-visible: `policy_health.py` reads the registry and reports OPEN/CLOSED,
and the canary (D-081) catches silent hosts removal. Wire both into
`dhriti health`; the extension's sweep count feeds selector-drift detection
(D-077).

## Install

1. **Machine policy (Layer 0 — do this first, it is the incognito closure)**
   - Run `windows-policy-layer.cmd` from an **elevated** Command Prompt
     (sets IncognitoModeAvailability=1 / InPrivateModeAvailability=1,
     DnsOverHttpsMode=off, and 30 URLBlocklist entries for Chrome, Brave, Edge).
   - Restart the browsers. Verify at `chrome://policy` / `brave://policy` /
     `edge://policy`, then run `python policy_health.py` → all CLOSED, ring 1 armed.
   - Note: if you use another Chromium browser (Vivaldi, Opera), add the same
     keys under its policy path; Firefox is covered separately below.
2. **Extension (ring 2 + 3)**
   - Copy `rules/` and `content/` into your E1 extension folder.
   - Merge `manifest-additions.json` into your `manifest.json`
     (concatenate `permissions`, `host_permissions`, `content_scripts`; add the
     `declarative_net_request` key).
   - Merge `background-images.js` into your existing E1 service worker and set
     the `BRIDGE` origin + token key to your loopback values. If your ledger
     events flow through the native host instead of the bridge, swap
     `bridgePost()` for your `sendNativeMessage` call — payload shape is the same.
   - Reload the unpacked extension.
2. **Hosts ring (ring 1)**
   - From an elevated terminal: `python e2_images_block.py arm`
   - Then `ipconfig /flushdns` and restart the browser.
   - Check: `python e2_images_block.py status` → all `BLOCKED`, canary `OK`.
3. **Browser settings**
   - Secure DNS is already forced off by Layer 0 (the toggle shows "managed").
     If you skip Layer 0, turn it off manually: `chrome://settings/security`.
   - Also flip **Allow in Incognito** for the Dhriti extension
     (`chrome://extensions` → Details) — redundant after Layer 0, harmless now.
   - Add your country TLD to `host_permissions` + `content_scripts.matches` +
     the `URL_FILTERS` list in the background script + the generated policy
     patterns if you search on something other than the listed TLDs.
4. **Firefox (optional coverage)** — create `policies.json` in the Firefox
   install directory:
   `{"policies":{"DNSOverHTTPS":{"Enabled":false,"Fallback":false},"WebsiteFilter":{"Block":["*://images.google.com/*","*://lens.google.com/*"]}}}`
   (WebsiteFilter does not match query params — the udm=2 hole in Firefox is
   closed only partially; policies do apply to Firefox private windows.)

## Test checklist

1. google.com homepage — the "Images" link is gone.
2. Search anything — the Images tab/chip is gone.
3. Navigate to `https://images.google.com` — blocked (policy/DNR error page or wall).
4. `https://www.google.com/imghp` — blocked.
5. `https://www.google.com/search?q=cats&tbm=isch` — blocked.
6. Same URL with `&udm=2` in any param position — blocked (both your captured
   URL shapes, `&udm=2&q=` and `...&udm=2` mid-string, were tested explicitly).
7. Right-click an image → "Search image with Google Lens" → blocked.
8. Force-load a cached Images page → wall card, no scroll, no thumbnails.
9. **New private/incognito window — the menu item is greyed out (Layer 0).**
10. `python policy_health.py` → Layer 0 CLOSED, ring 1 DEAD/DEAD, canary LIVE.
11. Normal search, Gmail, Docs, YouTube still work (no over-blocking —
    `googleusercontent`, fonts, Maps tiles are untouched; `udm=14`, `tbm=vid`,
    `tbm=nws` verticals are untouched).

## Rollback

`python e2_images_block.py disarm` + disable or remove the extension ruleset +
the REVERT block at the bottom of `windows-policy-layer.cmd` (deletes the
policy keys). Backups of the hosts file are written next to it on every change.

## Ledger integration (paste-ready)

- **D-082 — vertical exile**: Google Images vertical is a blocked entry
  class. Enforcement at one policy layer plus three rings: machine policy
  (incognito disabled, DoH forced off, URLBlocklist token-matched params +
  entry hosts), DNS (entry hosts + thumbnail CDN, canary-controlled), URL
  (DNR static rules on tbm=isch/udm=2/imghp/imgres/lens), content (stop +
  wipe + faced wall card with park action). Rationale: the Images vertical is
  a domain-hopping media grid reachable through legitimate search, consumed
  often inside private windows and readable without ever opening an external
  domain; killing the entry + emptying the room satisfies L-4 (pure
  URL-pattern enforcement — no content classification, so not even the L-9
  valve is needed) while the wall card keeps the record faced, not softened.
- **Cold Turkey stays belt-and-suspenders, never primary**: Dhriti's existing
  Cold Turkey probe (`_probe_cold_turkey`, `delegate_domains`) keeps reporting
  it, and the `google.*/*&udm=2&*` wildcard may be added — but its matcher is
  boundary-fragile (fails when the param is first/last) and untestable from
  here, so Layer 0 + ring 1 + ring 2 are the load-bearing layers.
- **P-17 — Image Vertical Dive**: emitted as `vertical_block` /
  `vertical_wall` / `chip_suppressed` events; kill-chain stage = navigate
  (ring 1/2) or read (ring 3). Content-blind: hostname + pattern flag only,
  query text never logged.
- Optional: feed repeated `vertical_block` events into the break-glass
  escalation ladder if you want attempted dives to carry a toll.
