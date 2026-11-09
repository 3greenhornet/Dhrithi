"""Lifecycle state machines (dossier section 3.4).

Generic, explicit transition tables. Anything not listed is illegal and
raises StateError. This is the single source of truth for what may
happen; day/session/bootcamp services call assert_transition().
"""

from .errors import StateError
from .models import BootcampState, DayState, SessionState

SESSION_TRANSITIONS = {
    SessionState.DRAFT: {SessionState.SEALED},
    SessionState.SEALED: {SessionState.ARMING},
    SessionState.ARMING: {SessionState.ACTIVE, SessionState.ARMING_FAILED},
    SessionState.ARMING_FAILED: {SessionState.SEALED, SessionState.DRAFT},
    SessionState.ACTIVE: {
        SessionState.SUCCESS,
        SessionState.INCOMPLETE,
        SessionState.BREAK_GLASS,
        SessionState.INTERRUPTED,
    },
    # Recovery path (dossier 3.4): an INTERRUPTED session is reviewed on the
    # next boot; it closes out honestly as INCOMPLETE, SUCCESS (proof was
    # already accepted before the interruption) or BREAK_GLASS.
    SessionState.INTERRUPTED: {
        SessionState.INCOMPLETE,
        SessionState.SUCCESS,
        SessionState.BREAK_GLASS,
    },
    SessionState.SUCCESS: set(),
    SessionState.INCOMPLETE: set(),
    SessionState.BREAK_GLASS: set(),
}

DAY_TRANSITIONS = {
    DayState.PLANNED: {DayState.OPEN, DayState.NO_CONTRACT, DayState.RECOVERED},
    DayState.NO_CONTRACT: {DayState.OPEN, DayState.CLOSED_INCOMPLETE, DayState.RECOVERED},
    DayState.OPEN: {
        DayState.RELEASED_EARLY,
        DayState.CLOSED_COMPLETE,
        DayState.CLOSED_INCOMPLETE,
        DayState.RECOVERED,
    },
    DayState.RELEASED_EARLY: set(),
    DayState.CLOSED_COMPLETE: set(),
    DayState.CLOSED_INCOMPLETE: set(),
    DayState.RECOVERED: set(),
}

BOOTCAMP_TRANSITIONS = {
    BootcampState.PLANNED: {BootcampState.ACTIVE},
    BootcampState.ACTIVE: {BootcampState.TAPERED, BootcampState.GRADUATED,
                           BootcampState.ABANDONED},
    BootcampState.TAPERED: {BootcampState.GRADUATED, BootcampState.ABANDONED,
                            BootcampState.TAPERED},
    BootcampState.GRADUATED: set(),
    BootcampState.ABANDONED: set(),
}

_TABLES = {
    "session": (SessionState, SESSION_TRANSITIONS),
    "day": (DayState, DAY_TRANSITIONS),
    "bootcamp": (BootcampState, BOOTCAMP_TRANSITIONS),
}


def can_transition(kind: str, current, target) -> bool:
    enum_cls, table = _TABLES[kind]
    return target in table.get(current, set())


def assert_transition(kind: str, current, target) -> None:
    if not can_transition(kind, current, target):
        raise StateError(
            f"illegal {kind} transition {current.value} -> {target.value}"
        )
