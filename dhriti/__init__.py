"""Dhriti — local-first commitment-enforcement core.

Dhriti (Sanskrit dhṛ — to hold, to bear, to sustain) is a personal
execution experiment: an externalized will that enforces pre-written
contracts without negotiation.

Design invariants (see docs/ARCHITECTURE.md):
  * Pure standard library. No pip dependencies in the critical path.
  * Deterministic policy only. No model, network or API is required for
    enforcement to function (decision D-014).
  * Tamper-evident, not tamper-proof. Every contract and event is
    hash-chained; nothing is claimed to be unbreakable.
  * The user's own contract is the only voice. No coaching copy.
"""

__version__ = "0.5.0"
__tier__ = "Lite"  # per dossier section 11.1 reference tiers
