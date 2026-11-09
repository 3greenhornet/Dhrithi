# Refinement guide — when your refined material arrives

You said more refined material is coming, and that the current
documents are conversation-shaped raw material with contradictions,
updates and vagueness that need tightening. This file is the docking
procedure so refinements land without a rebuild.

## What is derived from what

| Refined input will touch | Files derived from it | Update order |
|---|---|---|
| Philosophy / patterns / framing | `README.md` (Why), this project's doc tone | 1 |
| Enforcement model (windows, rules) | `docs/RESOLUTIONS.md` → `dhriti/day_window.py` → `tests/test_day_window.py` | 2 |
| Contract/ritual fields | `docs/SCHEMAS.md` → `dhriti/contract.py` (`REQUIRED_DAILY_FIELDS`, `validate_payload`) → `tests/test_contracts.py` | 3 |
| Evidence rules | `dhriti/evidence.py` → `tests/test_evidence.py` | 4 |
| Break-glass costs | `dhriti/constants.py` defaults → `break_glass.py` → tests | 5 |
| Taper/graduation thresholds | `constants.py` (`taper`) → `bootcamp.py` → `tests/test_bootcamp_taper.py` | 6 |
| Adapter decisions (post-audit) | `dhriti.config.json` adapter blocks + `integrations/*/SETUP.md` | 7 |
| Event schema changes | `docs/SCHEMAS.md` → `dhriti/db.py` (new schema version + migration) — the hash chain makes old rows immutable, so schema changes must be additive | 8 |

## The rule

1. **RESOLUTIONS.md first.** If the refined material contradicts a
   resolution, edit the row there and say why (that file is the
   decision log).
2. Then the module, then the test, then
   `python -m unittest discover -s tests` green.
3. Never edit `source-material/` — add the refined file next to the
   originals and update `docs/TRACEABILITY.md` with new rows.

## Open items waiting for your material (from the decision register)

- D-003: verbatim chat export → `source-material/`.
- D-006: Focuser audit result → enable or drop the adapter slot.
- D-018 refinements: if you choose different day-window semantics,
   R1 is the single place to record the veto.
- Vision-proof provider choice (if you enable the experiment).
- Anything the dossier marked UNVERIFIED that your material verifies.
