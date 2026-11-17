"""The saved-content mirror (v0.7.0 Part 3 §3.1).

The mirror is the inversion of the feed: you saved these things;
the system hands ONE back per day, after the earned evening, with
recall before reveal — and nothing is optimized, recommended, or
paced. The pile is the record (L-7); the schedule is honest.

Off by default (L-6). Enabling is a cold-state act.
"""

from .events import *  # noqa: F401,F403
from .store import MirrorStore  # noqa: F401
from .surface import SurfaceService  # noqa: F401
from .ingest import YouTubeIngest, import_csv, OAuthError  # noqa: F401
from .classify_rule import classify  # noqa: F401
from .adapter import ViduraMirrorAdapter  # noqa: F401
