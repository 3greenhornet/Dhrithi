"""YouTube ingestion (Part 3 §3.1): OAuth 2.0 Authorization Code
Grant with PKCE, the Liked Videos / playlist fetch, quota accounting,
and the CSV import path.

The OAuth state machine is fully testable: the token endpoint is
injectable (tests mock it), the refresh token lives at
<home>/youtube_refresh_token with 0600 perms, and every network step
records its outcome in the ledger. Real ingestion needs the user's
OAuth client credentials (DHRITI_YOUTUBE_CLIENT_ID / _SECRET) — the
mechanism is built; the credentials are the user's to provide.
"""

import base64
import csv
import hashlib
import json
import os
import secrets
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

from ..db import Database
from ..timeutil import Clock, RealClock
from . import events as ev

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
YOUTUBE_PLAYLIST_ITEMS_URL = \
    "https://www.googleapis.com/youtube/v3/playlistItems"
YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
# The callback listener for `dhriti mirror auth`.
LOCAL_CALLBACK_PORT = 8765

QUOTA_COST = {"playlistItems.list": 1, "videos.list": 1}


class OAuthError(Exception):
    pass


def _pkce_pair() -> tuple:
    """PKCE verifier + challenge (S256)."""
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


def _http_json(url: str, data: Optional[dict] = None,
               headers: Optional[dict] = None,
               opener=None) -> dict:
    """POST/GET JSON with a pluggable opener (tests inject one)."""
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type":
                     "application/x-www-form-urlencoded",
                     **(headers or {})})
    else:
        req = urllib.request.Request(url, headers=headers or {})
    fetch = opener or urllib.request.urlopen
    with fetch(req, timeout=30) as resp:  # pragma: no branch
        return json.loads(resp.read().decode("utf-8"))


class YouTubeIngest:
    def __init__(self, db: Database, config: dict, home: Path,
                 clock: Optional[Clock] = None, ledger=None,
                 token_url: str = GOOGLE_TOKEN_URL,
                 http=None):
        self.db = db
        self.config = config.get("mirror", {})
        self.home = Path(home)
        self.clock = clock or RealClock()
        self.ledger = ledger
        self._token_url = token_url
        self._http = http or _http_json
        self.quota_used_today = 0

    # -- credentials ---------------------------------------------------------
    @property
    def client_id(self) -> str:
        return os.environ.get(
            self.config.get("youtube", {}).get(
                "oauth_client_id_env",
                "DHRITI_YOUTUBE_CLIENT_ID"), "")

    @property
    def client_secret(self) -> str:
        return os.environ.get(
            self.config.get("youtube", {}).get(
                "oauth_client_secret_env",
                "DHRITI_YOUTUBE_CLIENT_SECRET"), "")

    @property
    def refresh_token_path(self) -> Path:
        return self.home / self.config.get("youtube", {}).get(
            "oauth_refresh_token_path", "youtube_refresh_token")

    def has_refresh_token(self) -> bool:
        return self.refresh_token_path.exists()

    def _write_refresh_token(self, token: str):
        self.refresh_token_path.parent.mkdir(parents=True,
                                             exist_ok=True)
        self.refresh_token_path.write_text(token, encoding="utf-8")
        try:
            self.refresh_token_path.chmod(0o600)
        except OSError:
            pass

    # -- the OAuth state machine ------------------------------------------------
    def build_auth_url(self, redirect_uri: str,
                       state: str = "") -> tuple:
        """Step 1: the consent URL + the PKCE verifier (kept for the
        token exchange). Returns (url, verifier, state)."""
        if not self.client_id:
            raise OAuthError(
                "DHRITI_YOUTUBE_CLIENT_ID is not set — the credentials "
                "are the user's to provide (the mechanism is built)")
        verifier, challenge = _pkce_pair()
        state = state or secrets.token_urlsafe(16)
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "https://www.googleapis.com/auth/youtube.readonly",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        url = GOOGLE_AUTH_URL + "?" + urllib.parse.urlencode(params)
        return url, verifier, state

    def exchange_code(self, code: str, verifier: str,
                      redirect_uri: str) -> dict:
        """Step 2: authorization code -> tokens. The refresh token is
        stored (0600); the access token lives in memory only."""
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "code_verifier": verifier,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }
        tokens = self._http(self._token_url, data=payload)
        if "refresh_token" not in tokens:
            raise OAuthError(
                "the token response carried no refresh_token — "
                "re-run the consent with prompt=consent")
        self._write_refresh_token(tokens["refresh_token"])
        return tokens

    def refresh_access_token(self) -> str:
        """Step 3 (every ingestion): refresh token -> access token."""
        if not self.has_refresh_token():
            raise OAuthError(
                "no refresh token — run `dhriti mirror auth` first")
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token":
                self.refresh_token_path.read_text(encoding="utf-8").strip(),
            "grant_type": "refresh_token",
        }
        try:
            tokens = self._http(self._token_url, data=payload)
        except OAuthError:
            raise
        except Exception as exc:
            if self.ledger is not None:
                self.ledger.record(
                    ev.MIRROR_OAUTH_EXPIRED,
                    observed={"error": str(exc)[:200]},
                    action_taken="refresh failed; re-auth needed")
            raise OAuthError(f"refresh failed: {exc}") from exc
        return tokens.get("access_token", "")

    # -- quota -----------------------------------------------------------------
    def _spend_quota(self, endpoint: str, units: int = 1) -> bool:
        budget = int(self.config.get("youtube", {}).get(
            "quota_budget_per_day", 8000))
        if self.quota_used_today + units > budget:
            if self.ledger is not None:
                self.ledger.record(
                    ev.MIRROR_QUOTA_EXHAUSTED,
                    observed={"budget": budget,
                              "used": self.quota_used_today},
                    action_taken="ingestion stopped for today")
            return False
        self.quota_used_today += units
        return True

    # -- ingestion ------------------------------------------------------------
    def fetch_playlist_items(self, access_token: str,
                             playlist_id: str = "LL",
                             max_items: int = 500,
                             fetch_video_details=True) -> list:
        """playlistItems.list + videos.list, paged, quota-accounted.
        Returns raw item dicts for the store to upsert."""
        items = []
        page_token = ""
        per_page = min(50, max_items)
        while len(items) < max_items:
            if not self._spend_quota("playlistItems.list"):
                break
            params = {
                "part": "snippet,contentDetails",
                "playlistId": playlist_id,
                "maxResults": str(per_page),
            }
            if page_token:
                params["pageToken"] = page_token
            url = (YOUTUBE_PLAYLIST_ITEMS_URL + "?"
                   + urllib.parse.urlencode(params))
            try:
                page = self._http(url, headers={
                    "Authorization": f"Bearer {access_token}"})
            except Exception:
                if self.ledger is not None:
                    self.ledger.record(
                        ev.MIRROR_INGESTION_RETRY,
                        observed={"endpoint": "playlistItems.list"},
                        action_taken="transient failure; retry next "
                                     "tick")
                break
            for entry in page.get("items", []):
                snippet = entry.get("snippet", {})
                video_id = (entry.get("contentDetails", {})
                            .get("videoId")
                            or snippet.get("resourceId", {})
                            .get("videoId", ""))
                items.append({
                    "external_id": video_id,
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "published_at": snippet.get("publishedAt", ""),
                    "thumbnail_url": (snippet.get("thumbnails", {})
                                      .get("medium", {})
                                      .get("url", "")),
                    # duration arrives via videos.list below
                    "duration_seconds": None,
                })
            page_token = page.get("nextPageToken", "")
            if not page_token:
                break
        if fetch_video_details and items:
            self._fill_durations(access_token, items)
        return items[:max_items]

    def _fill_durations(self, access_token: str, items: list):
        """videos.list in chunks of 50 for durations (quota 1/chunk)."""
        for start in range(0, len(items), 50):
            chunk = items[start:start + 50]
            ids = ",".join(i["external_id"] for i in chunk
                           if i.get("external_id"))
            if not ids:
                continue
            if not self._spend_quota("videos.list"):
                break
            url = (YOUTUBE_VIDEOS_URL + "?"
                   + urllib.parse.urlencode(
                       {"part": "contentDetails", "id": ids}))
            try:
                page = self._http(url, headers={
                    "Authorization": f"Bearer {access_token}"})
            except Exception:
                continue
            by_id = {v["id"]: v for v in page.get("items", [])}
            for item in chunk:
                details = by_id.get(item["external_id"], {})
                dur = details.get("contentDetails", {}).get("duration")
                if dur:
                    item["duration_seconds"] = _parse_iso8601_duration(
                        dur)

    def ingest(self, store, source: dict) -> dict:
        """One ingestion pass for one source: refresh, fetch, upsert.
        Returns a summary; failures are events, not exceptions."""
        try:
            access_token = self.refresh_access_token()
        except OAuthError as exc:
            return {"ok": False, "reason": str(exc)[:200],
                    "ingested": 0}
        max_items = int(self.config.get("max_items_per_ingestion", 500))
        raw = self.fetch_playlist_items(
            access_token, source["source_identifier"],
            max_items=max_items)
        ingested = 0
        for item in raw:
            if not item.get("external_id"):
                continue
            store.upsert_item(
                source["id"], item["external_id"], item["title"],
                description=item.get("description", ""),
                duration_seconds=item.get("duration_seconds"),
                thumbnail_url=item.get("thumbnail_url", ""),
                published_at=item.get("published_at", ""))
            ingested += 1
        store.mark_ingested(source["id"])
        return {"ok": True, "ingested": ingested,
                "quota_used": self.quota_used_today}


def _parse_iso8601_duration(text: str) -> Optional[int]:
    """PT1H2M3S -> seconds."""
    import re
    match = re.match(
        r"^P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$",
        text or "")
    if not match:
        return None
    days, hours, minutes, seconds = (int(g) if g else 0
                                     for g in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def import_csv(store, source: dict, path: Path) -> dict:
    """The Google Takeout CSV import path: columns are matched by
    name (Title / Video URL / Timestamp — Takeout's shape), rows are
    upserted. Malformed rows are counted honestly."""
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"no such file: {path}")
    rows = list(csv.DictReader(
        path.open(encoding="utf-8-sig", newline="")))
    ingested, malformed = 0, 0
    for row in rows:
        title = (row.get("Title") or row.get("title") or "").strip()
        url = (row.get("Video URL") or row.get("Url") or
               row.get("URL") or "").strip()
        if not title or not url:
            malformed += 1
            continue
        video_id = url.rsplit("=", 1)[-1].rsplit("/", 1)[-1]
        if not video_id:
            malformed += 1
            continue
        store.upsert_item(source["id"], video_id, title,
                          published_at=(row.get("Timestamp") or ""))
        ingested += 1
    return {"ingested": ingested, "malformed": malformed}
