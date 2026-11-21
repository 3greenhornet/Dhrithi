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


def sync_single_playlist(url: str, output_path: Path, source_name: str, browser: str, no_cookies: bool) -> bool:
    """Fetch one playlist and ingest into Vidura."""
    print("=" * 60)
    print(f"  DHRITI VIDURA - SYNCING: {source_name.upper()}")
    print(f"  Target:     {url}")
    print(f"  Browser:    {browser if not no_cookies else 'none (public)'}")
    print(f"  Output:     {output_path.resolve()}")
    print("=" * 60)

    cmd = get_ytdlp_cmd(browser=browser, playlist_url=url, no_cookies=no_cookies)

    try:
        print(f"\n[*] Fetching metadata via yt-dlp (this may take a moment for large playlists)...")
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            err = result.stderr.strip()
            print("\n[-] yt-dlp encountered an error:")
            print(err)

            if "Could not copy Chrome cookie database" in err or "used by another process" in err or "WinError 32" in err:
                print("\n" + "!" * 60)
                print(f"[!] BROWSER COOKIE DATABASE IS LOCKED BY {browser.upper()}!")
                print("!" * 60)
                print(f"Why this happens: When {browser.capitalize()} is open, Windows enforces an exclusive")
                print("kernel file-lock on its cookie database for security.\n")
                print("YOU HAVE TWO SIMPLE WAYS TO SOLVE THIS:")
                print(f"  Method 1 (Easiest - 10 Seconds):")
                print(f"    1. Completely close all {browser.capitalize()} windows.")
                print(f"    2. Run 'python sync_playlist.py' again in this terminal.")
                print(f"    3. Reopen {browser.capitalize()}.\n")
                print(f"  Method 2 (No browser restart needed):")
                print(f"    1. Install the extension 'Get cookies.txt LOCALLY' in {browser.capitalize()}.")
                print(f"    2. On youtube.com, click export and save 'cookies.txt' into this repo folder.")
                print(f"    3. Run 'python sync_playlist.py'. It will use 'cookies.txt' instantly.\n")
            elif "Private video" in err or "Sign in" in err:
                print("\n[!] YouTube requires authentication to view this playlist.")
                print("Make sure you are logged into YouTube in your chosen browser.")
            return False

        playlist_data = json.loads(result.stdout)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(playlist_data, f, indent=2, ensure_ascii=False)

        entries = playlist_data.get("entries", [])
        print(f"[+] Successfully saved {len(entries)} videos to {output_path.name}!")

        # Automatic ingestion into Vidura SQLite database
        try:
            from dhriti.constants import DB_VIDURA_PATH
            from dhriti.vidura_corpus import ViduraCorpus

            corpus = ViduraCorpus(DB_VIDURA_PATH)
            ingested_count = corpus.ingest_youtube_playlist_json(playlist_data, source=source_name)
            print(f"[+] Ingested {ingested_count} videos into Vidura Corpus ({DB_VIDURA_PATH.name})")
            stats = corpus.stats()
            print(f"[+] Total Vidura Corpus items now: {stats['total_items']} ({stats['total_topics']} topic nodes)\n")
        except Exception as ingest_err:
            print(f"[!] Note: JSON saved, but Vidura corpus auto-ingest had a notice: {ingest_err}\n")

        return True

    except Exception as e:
        print(f"\n[-] Unexpected error during sync: {e}")
        return False


def sync_playlist():
    parser = argparse.ArgumentParser(description="Dhriti Vidura YouTube Sync Engine")
    parser.add_argument("--browser", default="brave", choices=["brave", "chrome", "edge", "firefox"], help="Browser to extract cookies from (default: brave)")
    parser.add_argument("--url", default=None, help="YouTube playlist URL (if omitted, syncs both Watch Later and Liked Videos)")
    parser.add_argument("--output", default=None, help="Output JSON path (optional)")
    parser.add_argument("--liked-only", action="store_true", help="Sync only Liked Videos")
    parser.add_argument("--watch-later-only", action="store_true", help="Sync only Watch Later")
    parser.add_argument("--no-cookies", action="store_true", help="Fetch without cookies (for public playlists)")
    args = parser.parse_args()

    targets = []
    if args.url:
        out = Path(args.output or "custom_playlist.json")
        targets.append((args.url, out, "youtube_custom"))
    elif args.liked_only:
        targets.append(("https://www.youtube.com/playlist?list=LL", Path(args.output or "liked_videos.json"), "youtube_liked"))
    elif args.watch_later_only:
        targets.append(("https://www.youtube.com/playlist?list=WL", Path(args.output or "watch_later.json"), "youtube_watch_later"))
    else:
        # Default: sync BOTH Watch Later and Liked Videos
        targets.append(("https://www.youtube.com/playlist?list=WL", Path("watch_later.json"), "youtube_watch_later"))
        targets.append(("https://www.youtube.com/playlist?list=LL", Path("liked_videos.json"), "youtube_liked"))

    overall_success = True
    for url, out_path, source in targets:
        ok = sync_single_playlist(url=url, output_path=out_path, source_name=source, browser=args.browser, no_cookies=args.no_cookies)
        if not ok:
            overall_success = False

    return overall_success


if __name__ == "__main__":
    success = sync_playlist()
    if not success:
        sys.exit(1)
