"""Local backup with manifest (operator toolkit #3, Phase 1).

Copies the database, config, profiles and a ledger export into a
timestamped directory, verifies the hash chain before and after, and
writes a manifest with sha256 of every file. The backup is the "undo"
path for migrations (backup-before-migration) and the honest local copy
of an otherwise un-witnessed record.

No network, no cloud, no credentials — by design (non-goal: local-first).
"""

import hashlib
import json
import shutil
from datetime import timedelta
from pathlib import Path
from typing import Optional

from . import __version__
from .db import Database
from .ledger import Ledger
from .timeutil import Clock, RealClock, to_iso


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


class BackupService:
    def __init__(self, home: Path, db: Database, ledger: Ledger,
                 clock: Optional[Clock] = None):
        self.home = Path(home)
        self.db = db
        self.ledger = ledger
        self.clock = clock or RealClock()

    def create(self, dest: Optional[Path] = None) -> dict:
        """Create a timestamped backup directory; return the manifest."""
        dest_root = Path(dest) if dest else self.home / "backups"
        stamp = self.clock.now_utc().strftime("%Y%m%dT%H%M%SZ")
        out_dir = dest_root / stamp
        out_dir.mkdir(parents=True, exist_ok=True)

        chain_before = self.ledger.verify_chain()
        files: list = []

        # 1. the database (checkpoint sidecars first so the copy is whole)
        db_src = Path(self.db.path)
        self.db.conn.commit() if getattr(self.db, "conn", None) else None
        db_dst = out_dir / db_src.name
        shutil.copy2(db_src, db_dst)
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(db_src) + suffix)
            if sidecar.exists():
                shutil.copy2(sidecar, out_dir / sidecar.name)
        files.append(db_dst.name)

        # 2. ledger export
        export = out_dir / "ledger_export.json"
        self.ledger.export(str(export), fmt="json")
        files.append(export.name)

        # 3. config + profiles + bridge token presence flag (not content)
        config_src = self.home / "dhriti.config.json"
        if config_src.exists():
            shutil.copy2(config_src, out_dir / config_src.name)
            files.append(config_src.name)
        profiles_src = self.home / "profiles"
        if profiles_src.is_dir():
            shutil.copytree(profiles_src, out_dir / "profiles",
                            dirs_exist_ok=True)
            files.append("profiles/")

        manifest = {
            "backup_time": to_iso(self.clock.now_utc()),
            "dhriti_version": __version__,
            "schema_version": self.db.get_meta("schema_version"),
            "chain_head": self.ledger.head()["row_hash"],
            "chain_verified_before": chain_before["ok"],
            "chain_events": chain_before["checked"],
            "files": [],
            "dest": str(out_dir),
        }

        # verify the backup's own chain by opening the copy; do this
        # BEFORE hashing so a WAL replay during the check cannot change
        # the file under the recorded hash.
        try:
            db_check = Database(db_dst, journal_mode="delete")
            ledger_check = Ledger(db_check, self.clock)
            after = ledger_check.verify_chain()
            manifest["chain_verified_after"] = after["ok"]
            db_check.close()
        except Exception as exc:  # never fake a verification
            manifest["chain_verified_after"] = False
            manifest["chain_check_error"] = str(exc)[:200]

        manifest["files"] = [
            {"name": f, "sha256": _sha256_file(out_dir / f)}
            for f in files if (out_dir / f).is_file()]

        (out_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest

    def verify(self, backup_dir: Path) -> dict:
        """Verify a backup directory against its manifest."""
        backup_dir = Path(backup_dir)
        manifest_path = backup_dir / "manifest.json"
        if not manifest_path.exists():
            return {"ok": False, "reason": "no manifest.json"}
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        problems = []
        for entry in manifest.get("files", []):
            path = backup_dir / entry["name"]
            if not path.is_file():
                problems.append(f"missing: {entry['name']}")
            elif _sha256_file(path) != entry["sha256"]:
                problems.append(f"hash mismatch: {entry['name']}")
        return {"ok": not problems, "problems": problems,
                "manifest": manifest}
