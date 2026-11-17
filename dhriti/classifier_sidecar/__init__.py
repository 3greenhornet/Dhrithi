"""Dhriti Guard Kit -- optional AI classifier sidecar package.

L-9 / L-6 gating: this whole package is OFF by default. It is a SENSOR,
not a decider (D-014 spirit): its verdicts may only ESCALATE to park or
collapse; the deterministic core (dhriti/chat_guard.py) owns every denial.

Run standalone (never imported by the core):
    python -m dhriti.classifier_sidecar.server --port 8765 --token-file ...
"""
