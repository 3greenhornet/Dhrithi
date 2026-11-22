"""Chrome / Brave / Edge Bookmarks Ingestion Watcher Daemon (D-096 / §6.6.3 / §19.3).

Provides:
1. Platform locator for Chrome, Edge, and Brave `Bookmarks` JSON files across
   Windows, Linux, and macOS.
2. File system watcher using `watchdog.observers.Observer` and `FileSystemEventHandler`.
3. 2.0-second debounce mechanism to absorb atomic write bursts and prevent duplicate triggers.
4. Automated re-ingestion into `ViduraCorpus` via `ingest_bookmarks_json`
   (idempotent by URL deduplication) and automatic FTS5 index update.
5. `DHRITI_CI_ENVIRONMENT` law compliance (§19.3): runs deterministically with fixture
   data and mocks the background observer in headless CI.
"""

from __future__ import annotations

import glob
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Set

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False
    class FileSystemEventHandler:  # type: ignore
        pass

from .constants import DB_VIDURA_PATH
from .vidura_corpus import ViduraCorpus

logger = logging.getLogger("dhriti.vidura_watcher")


def find_platform_bookmark_paths() -> List[Path]:
    """Discover existing Bookmarks JSON files across Chrome, Edge, and Brave."""
    found: List[Path] = []
    seen: Set[str] = set()

    def add_if_exists(p: Path):
        resolved = str(p.resolve())
        if p.exists() and resolved not in seen:
            seen.add(resolved)
            found.append(p)

    if sys.platform == "win32" or os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            base_dir = Path(local_app_data)
            # Chrome
            chrome_root = base_dir / "Google" / "Chrome" / "User Data"
            if chrome_root.exists():
                add_if_exists(chrome_root / "Default" / "Bookmarks")
                for prof in chrome_root.glob("Profile */Bookmarks"):
                    add_if_exists(prof)

            # Edge
            edge_root = base_dir / "Microsoft" / "Edge" / "User Data"
            if edge_root.exists():
                add_if_exists(edge_root / "Default" / "Bookmarks")
                for prof in edge_root.glob("Profile */Bookmarks"):
                    add_if_exists(prof)

            # Brave
            brave_root = base_dir / "BraveSoftware" / "Brave-Browser" / "User Data"
            if brave_root.exists():
                add_if_exists(brave_root / "Default" / "Bookmarks")
                for prof in brave_root.glob("Profile */Bookmarks"):
                    add_if_exists(prof)

    elif sys.platform == "darwin":
        home = Path.home()
        app_support = home / "Library" / "Application Support"
        # Chrome
        add_if_exists(app_support / "Google" / "Chrome" / "Default" / "Bookmarks")
        # Edge
        add_if_exists(app_support / "Microsoft Edge" / "Default" / "Bookmarks")
        # Brave
        add_if_exists(app_support / "BraveSoftware" / "Brave-Browser" / "Default" / "Bookmarks")

    else:
        # Linux / Unix
        home = Path.home()
        config_dir = home / ".config"
        add_if_exists(config_dir / "google-chrome" / "Default" / "Bookmarks")
        add_if_exists(config_dir / "chromium" / "Default" / "Bookmarks")
        add_if_exists(config_dir / "BraveSoftware" / "Brave-Browser" / "Default" / "Bookmarks")
        add_if_exists(config_dir / "microsoft-edge" / "Default" / "Bookmarks")

    return found


class BookmarkChangeHandler(FileSystemEventHandler):
    """Debounced file modification handler for browser Bookmarks files."""

    def __init__(
        self,
        target_paths: List[Path],
        on_change_callback: Callable[[Path], None],
        debounce_seconds: float = 2.0
    ):
        super().__init__()
        self.target_paths = {p.resolve(): p for p in target_paths}
        self.target_names = {p.name.lower() for p in target_paths}
        self.on_change_callback = on_change_callback
        self.debounce_seconds = debounce_seconds
        self._last_event_times: Dict[str, float] = {}
        self._timers: Dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def _handle_path(self, path_str: str):
        path = Path(path_str).resolve()
        # Check if modified file is one of our targets (or Bookmarks)
        if path.name.lower() != "bookmarks" and path not in self.target_paths:
            return

        with self._lock:
            # Cancel any pending timer for this path
            key = str(path)
            if key in self._timers:
                self._timers[key].cancel()

            # Schedule debounced callback
            def debounced_trigger():
                logger.info(f"Triggering ingestion for {path}")
                try:
                    self.on_change_callback(path)
                except Exception as ex:
                    logger.error(f"Error ingesting bookmarks from {path}: {ex}")

            timer = threading.Timer(self.debounce_seconds, debounced_trigger)
            self._timers[key] = timer
            timer.daemon = True
            timer.start()

    def on_modified(self, event):
        if not event.is_directory:
            self._handle_path(event.src_path)

    def on_created(self, event):
        if not event.is_directory:
            self._handle_path(event.src_path)


class BookmarksWatcher:
    """Manages browser Bookmarks monitoring and automatic Vidura ingestion."""

    def __init__(
        self,
        corpus: ViduraCorpus,
        bookmark_paths: Optional[List[Path]] = None,
        debounce_seconds: float = 2.0,
        on_ingest_callback: Optional[Callable[[Path, int], None]] = None
    ):
        self.corpus = corpus
        self.debounce_seconds = debounce_seconds
        self.on_ingest_callback = on_ingest_callback
        self.bookmark_paths = bookmark_paths if bookmark_paths is not None else find_platform_bookmark_paths()
        self.is_ci = os.environ.get("DHRITI_CI_ENVIRONMENT", "").lower() in ("true", "1")
        self._observer: Optional[Any] = None
        self._running = False

    def ingest_path(self, path: Path) -> int:
        """Ingest a single bookmarks file into the ViduraCorpus."""
        if not path.exists():
            return 0
        try:
            count = self.corpus.ingest_bookmarks_json(path)
            if self.on_ingest_callback:
                self.on_ingest_callback(path, count)
            return count
        except Exception as exc:
            logger.error(f"Failed to ingest bookmarks from {path}: {exc}")
            return 0

    def ingest_all_now(self) -> Dict[str, int]:
        """Perform immediate one-shot ingestion of all registered Bookmarks paths."""
        results = {}
        for p in self.bookmark_paths:
            results[str(p)] = self.ingest_path(p)
        return results

    def start(self, blocking: bool = False):
        """Start monitoring Bookmarks files for modifications."""
        if self.is_ci:
            logger.info("DHRITI_CI_ENVIRONMENT active: running deterministic one-shot ingestion without Observer.")
            self.ingest_all_now()
            return

        if not HAS_WATCHDOG:
            logger.warning("watchdog package not installed; falling back to one-shot ingestion.")
            self.ingest_all_now()
            return

        if not self.bookmark_paths:
            logger.info("No browser Bookmarks files found to monitor.")
            return

        self.ingest_all_now()

        self._observer = Observer()
        handler = BookmarkChangeHandler(
            target_paths=self.bookmark_paths,
            on_change_callback=lambda p: self.ingest_path(p),
            debounce_seconds=self.debounce_seconds
        )

        # Watch unique parent directories
        watched_dirs = set(p.parent.resolve() for p in self.bookmark_paths if p.parent.exists())
        for d in watched_dirs:
            self._observer.schedule(handler, str(d), recursive=False)
            logger.info(f"Watching bookmark directory: {d}")

        self._observer.start()
        self._running = True

        if blocking:
            try:
                while self._running:
                    time.sleep(1.0)
            except KeyboardInterrupt:
                self.stop()

    def stop(self):
        """Stop the background watcher."""
        self._running = False
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            logger.info("Bookmarks watcher stopped.")
