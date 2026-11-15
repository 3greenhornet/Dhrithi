# Day-one checklist

The single ordered list between "a plan" and "a first session" (plan
Part 4, process gaps). Do it once, in order. Each unchecked box is a
known hole — not a surprise later.

## 0. Decide, cold (15 min, no tooling)

- [ ] Write the main belief, its metric, its current state, your
      substitutes and their budget on paper. (These five lines are the
      D-030 contract group; the ritual will ask for them.)
- [ ] Pick the bootcamp length: 30 / 60 / 90 days.
- [ ] Pick the window: default 10:00–21:00, day_close 20:00 (edit
      `dhriti.config.json` `day_window` if needed).
- [ ] Decide the digest recipient (`digest.recipient_label`) — the one
      human who will receive the weekly file. Minimal E4 starts here.

## 1. Core (10 min)

- [ ] `python3 -m dhriti.cli init` (Windows: `py -m dhriti.cli init`)
- [ ] `pip install tzdata` once on Windows.
- [ ] `python3 -m dhriti.cli bootcamp start --days 30`
- [ ] `python3 -m dhriti.cli ritual` — tonight or before 10:00, cold.
      The wizard now asks the main-belief group, the IF–THEN obstacle
      plan, and the emergency policy. Answer in your own words.

## 2. The wall, E1 (10 min)

- [ ] `python3 -m dhriti.cli token show` → paste into
      `extension/config.js` (`bridgeToken`).
- [ ] Chrome → `chrome://extensions` → Developer mode → Load unpacked
      → this repo's `extension/` folder.
- [ ] Verify: badge shows `D` while the window is open, nothing else.
- [ ] Verify suppression (D-024): during the window, open youtube.com —
      no home feed, no Shorts; open an AI chat — no follow-up chips.
      Search still works. If a rule is stale, note it for cold review;
      never fix selectors mid-session.

## 3. Optional E2 (10 min, admin PowerShell)

- [ ] Edit `integrations/windows/hosts-block.ps1` domain list (the
      three worst domains, not thirty).
- [ ] Run as admin → verify with `ping <domain>` resolving to 0.0.0.0.
- [ ] Record the removal command for the honest case you need it.

## 4. Optional observation (15 min)

- [ ] Install ActivityWatch (record the version in
      `docs/VERSION_PINS.md`). Enable the window + web + afk watchers.
- [ ] Run the 10-minute zero-duration check (R-004) before trusting any
      duration data.
- [ ] Skip Sysmon on day one. It belongs to Phase 2, in the disposable
      environment first, never on the daily account untested.

## 5. First session (the actual point)

- [ ] 10:00 — `python3 -m dhriti.cli daemon` (leave it running).
- [ ] `python3 -m dhriti.cli session start --task "reverse the array"`
- [ ] Curiosity fires? `python3 -m dhriti.cli park "why does X"`.
      Back to work.
- [ ] Real dependency? `python3 -m dhriti.cli declare dependency
      --what "test fails on JWT filter"` then
      `dhriti research start ...` (bounded).
- [ ] Proof: `python3 -m dhriti.cli proof command --command "py ..."`
- [ ] `python3 -m dhriti.cli session end --outcome success`

## 6. Evening, cold (10 min)

- [ ] `python3 -m dhriti.cli report` — read the exchange, the
      consumption facts, the breaks. Facts only.
- [ ] `python3 -m dhriti.cli review` — the six questions.
- [ ] `python3 -m dhriti.cli digest` — send the file to the recipient.
      This is the dead-man's switch; it only works if it always goes.
- [ ] `python3 -m dhriti.cli verify` — copy the head hash somewhere
      off-machine.

Known holes you are accepting on day one (honest list): phone and other
devices are outside the wall (answered only in the review); the bridge
token is static until you rotate it (`dhriti token rotate`, cold); E1
is bypassable by a determined owner in seconds — every bypass is
recorded, none is prevented (tamper-evident, not tamper-proof).
