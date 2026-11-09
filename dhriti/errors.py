"""Dhriti exception hierarchy.

Every failure is explicit and honest: the system never pretends a
capability exists when it does not (dossier 3.4 arming gate), and never
claims a penalty was imposed when it merely detected a violation
(dossier 2.7 tamper-evident stance).
"""


class DhritiError(Exception):
    """Base class for all Dhriti errors."""


class ConfigError(DhritiError):
    """Configuration is missing or invalid."""


class StateError(DhritiError):
    """An illegal lifecycle transition was attempted (state machine guard)."""


class ContractError(DhritiError):
    """Contract missing, not sealed, or an edit on a sealed contract."""


class BreakGlassError(DhritiError):
    """Break-glass preconditions failed (cooldown, reason too short...)."""


class EvidenceError(DhritiError):
    """Evidence submission or verification problem."""


class AdapterError(DhritiError):
    """Adapter probe/arming failure."""


class DisabledFeature(DhritiError):
    """A deliberately disabled, placeholder feature was invoked.

    Raised instead of silently faking behaviour for anything that needs
    manual download / integration (external tools, API keys, model
    downloads). The message points at the setup guide.
    """


class LedgerError(DhritiError):
    """Ledger integrity or write failure."""


class BridgeError(DhritiError):
    """Local bridge (extension API) failure."""
