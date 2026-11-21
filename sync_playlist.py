"""Dhriti Vidura YouTube Playlist / Watch Later Synchronizer.

Extracts your YouTube Watch Later or Liked playlist using yt-dlp,
saves the raw JSON dump to `watch_later.json`, and automatically ingests
every video into the Vidura local corpus (`vidura.sqlite3`).

Usage:
  python sync_playlist.py
  python sync_playlist.py --browser chrome
  python sync_playlist.py --url "https://www.youtube.com/playlist?list=LL"
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Fix Windows console encoding for terminal outputs
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def get_ytdlp_cmd(browser: str = "brave", playlist_url: str = "https://www.youtube.com/playlist?list=WL", no_cookies: bool = False) -> list[str]:
    """Build the yt-dlp command line arguments."""
    base = [sys.executable, "-m", "yt_dlp"]

    if no_cookies:
        print("[+] Running without cookies (public playlist mode)...")
        cookie_args = []
    else:
        # Check for local Netscape cookies file first (zero lock contention)
        candidate_cookies = [
            Path("www.youtube.com_cookies.txt"),
            Path("cookies.txt"),
            Path("youtube.com_cookies.txt")
        ]
        found_cookie_file = None
        for cand in candidate_cookies:
            if cand.exists():
                found_cookie_file = cand
                break
        if not found_cookie_file:
            for cand in Path(".").glob("*cookie*.txt"):
                found_cookie_file = cand
                break

        if found_cookie_file:
            print(f"[+] Found cookie file '{found_cookie_file.name}'. Using it directly (zero browser lock contention)...")
            cookie_args = ["--cookies", str(found_cookie_file.resolve())]
        else:
            print(f"[+] Attempting to extract session cookies from {browser.capitalize()} browser...")
            cookie_args = ["--cookies-from-browser", browser]

    return base + cookie_args + [
        "--flat-playlist",
        "-J",
        "--no-warnings",
        playlist_url
    ]


def sync_playlist():
    parser = argparse.ArgumentParser(description="Dhriti Vidura YouTube Sync Engine")
    parser.add_argument("--browser", default="brave", choices=["brave", "chrome", "edge", "firefox"], help="Browser to extract cookies from (default: brave)")
    parser.add_argument("--url", default="https://www.youtube.com/playlist?list=WL", help="YouTube playlist URL (default: Watch Later)")
    parser.add_argument("--output", default="watch_later.json", help="Output JSON path (default: watch_later.json)")
    parser.add_argument("--no-cookies", action="store_true", help="Fetch without cookies (for public playlists)")
    args = parser.parse_args()

    output_path = Path(args.output)
    print("=" * 60)
    print("  DHRITI VIDURA - YOUTUBE PLAYLIST SYNC")
    print(f"  Target:     {args.url}")
    print(f"  Browser:    {args.browser if not args.no_cookies else 'none (public)'}")
    print(f"  Output:     {output_path.resolve()}")
    print("=" * 60)

    cmd = get_ytdlp_cmd(browser=args.browser, playlist_url=args.url, no_cookies=args.no_cookies)

    try:
        print("\n[*] Fetching playlist metadata via yt-dlp...")
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            err = result.stderr.strip()
            print("\n[-] yt-dlp encountered an error:")
            print(err)

            if "Could not copy Chrome cookie database" in err or "used by another process" in err or "WinError 32" in err:
                print("\n" + "!" * 60)
                print(f"[!] BROWSER COOKIE DATABASE IS LOCKED BY {args.browser.upper()}!")
                print("!" * 60)
                print(f"Why this happens: When {args.browser.capitalize()} is open, Windows enforces an exclusive")
                print("kernel file-lock on its cookie database for security.\n")
                print("YOU HAVE TWO SIMPLE WAYS TO SOLVE THIS:")
                print(f"  Method 1 (Easiest - 10 Seconds):")
                print(f"    1. Completely close all {args.browser.capitalize()} windows.")
                print(f"    2. Run 'python sync_playlist.py' again in this terminal.")
                print(f"    3. Reopen {args.browser.capitalize()}.\n")
                print(f"  Method 2 (No browser restart needed):")
                print(f"    1. Install the extension 'Get cookies.txt LOCALLY' in {args.browser.capitalize()}.")
                print(f"    2. On youtube.com, click export and save 'cookies.txt' into this repo folder.")
                print(f"    3. Run 'python sync_playlist.py'. It will use 'cookies.txt' instantly.\n")
            elif "Private video" in err or "Sign in" in err:
                print("\n[!] YouTube requires authentication to view this playlist.")
                print("Make sure you are logged into YouTube in your chosen browser.")
            return False

        # Parse json to verify it's valid
        playlist_data = json.loads(result.stdout)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(playlist_data, f, indent=2, ensure_ascii=False)

        entries = playlist_data.get("entries", [])
        print(f"\n[+] Successfully saved {len(entries)} videos to {output_path.name}!")

        # Automatic ingestion into Vidura SQLite database
        try:
            from dhriti.constants import DB_VIDURA_PATH
            from dhriti.vidura_corpus import ViduraCorpus

            corpus = ViduraCorpus(DB_VIDURA_PATH)
            ingested_count = corpus.ingest_youtube_playlist_json(playlist_data, source="youtube_watch_later")
            print(f"[+] Automatically ingested {ingested_count} videos into Vidura Corpus ({DB_VIDURA_PATH.name})")
            print(f"[+] Total Vidura Corpus items now: {corpus.stats()['total_items']}")
        except Exception as ingest_err:
            print(f"[!] Note: JSON saved, but Vidura corpus auto-ingest had a notice: {ingest_err}")

        return True

    except Exception as e:
        print(f"\n[-] Unexpected error during sync: {e}")
        return False


if __name__ == "__main__":
    success = sync_playlist()
    if not success:
        sys.exit(1)
