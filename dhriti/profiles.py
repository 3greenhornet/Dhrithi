"""Task profiles (dossier 6.3): same site can be work in one task and a
detour in another. Authored personally; start with the profiles you
actually use. No universal taxonomy, no weeks of design.

D-050 — THE CONFIGURATION IMMUTABILITY LAW (a law since v0.3, true by
accident before it): profile and category edits are COLD-STATE acts.
The daemon loads config + profiles exactly once at start and never
hot-reloads them; an edit on disk takes effect at the next daemon
start, and the drift between the loaded fingerprint and the disk is
recorded as `config_drift_detected` at the next session start. The
edit itself is builder-domain activity: Specimen 001 documents
tool/config choice as avoidance ("what about C? or Python?" —
"language choice is just another audience chair"), so the act of
reconfiguring the guardrail is itself visible in the record.

Profile schema (JSON, in configs/profiles/ or <home>/profiles/):
  {
    "allowed_domains": ["developer.mozilla.org", "docs.oracle.com"],
    "allowed_apps": ["Code.exe", "WindowsTerminal.exe", "java.exe"],
    "blocked_categories": ["video", "social", "ai_chat", "games", "news",
                           "shopping", "entertainment"],
    "research_bounds": {"max_minutes": 20, "max_sources": 5}
  }

Category domain lists live in one place (CATEGORY_DOMAINS below) and are
edited by the user — deliberately boring, deterministic and inspectable,
not inferred by a model (decision D-014).
"""

import json
from pathlib import Path

DEFAULT_PROFILES = {
    "coding": {
        "allowed_domains": [
            "docs.oracle.com", "developer.mozilla.org", "stackoverflow.com",
            "github.com", "www.typescriptlang.org", "docs.python.org",
            "maven.apache.org", "spring.io", "docs.rs",
        ],
        "allowed_apps": [
            "code.exe", "code", "java.exe", "javac.exe", "python.exe",
            "python3", "pwsh.exe", "powershell.exe", "wt.exe", "cmd.exe",
            "bash", "git.exe", "mvn", "gradle", "idea64.exe",
        ],
        "blocked_categories": ["video", "social", "ai_chat", "games",
                               "news", "shopping", "entertainment"],
        "research_bounds": {"max_minutes": 20, "max_sources": 5},
    },
    "study": {
        "allowed_domains": [],
        "allowed_apps": ["code.exe", "acrobat.exe", "sumatrapdf.exe",
                         "obsidian.exe", "notepad.exe"],
        "blocked_categories": ["video", "social", "ai_chat", "games",
                               "news", "shopping", "entertainment"],
        "research_bounds": {"max_minutes": 15, "max_sources": 3},
    },
    "research": {
        "allowed_domains": [
            "scholar.google.com", "arxiv.org", "pubmed.ncbi.nlm.nih.gov",
            "pmc.ncbi.nlm.nih.gov", "www.nature.com", "dl.acm.org",
            "ieeexplore.ieee.org", "github.com",
        ],
        "allowed_apps": ["code.exe", "zotero.exe", "acrobat.exe"],
        "blocked_categories": ["social", "games", "shopping", "entertainment"],
        "research_bounds": {"max_minutes": 45, "max_sources": 10},
    },
    "writing": {
        "allowed_domains": [],
        "allowed_apps": ["code.exe", "winword.exe", "obsidian.exe",
                         "notepad.exe"],
        "blocked_categories": ["video", "social", "ai_chat", "games",
                               "news", "shopping", "entertainment"],
        "research_bounds": {"max_minutes": 15, "max_sources": 5},
    },
    "placement_prep": {
        "allowed_domains": [
            "gitam.edu", "login.gitam.edu", "vtop.gitam.edu",
            "linkedin.com", "www.linkedin.com",
            "quantguide.io", "www.quantguide.io",
            "github.com", "gist.github.com",
            "chatgpt.com", "chat.openai.com", "claude.ai",
            "gemini.google.com", "chat.deepseek.com",
            "music.youtube.com",
            "docs.oracle.com", "geeksforgeeks.org", "leetcode.com",
            "hackerrank.com", "stackoverflow.com",
        ],
        "allowed_apps": [
            "code.exe", "code", "java.exe", "javac.exe", "python.exe",
            "python3", "pwsh.exe", "powershell.exe", "wt.exe", "cmd.exe",
            "chrome.exe", "msedge.exe", "brave.exe",
        ],
        "blocked_categories": ["games", "shopping", "entertainment"],
        "research_bounds": {"max_minutes": 25, "max_sources": 6},
    },
}

# Editable category lists. Domains match on the registrable suffix
# (e.g. youtube.com also matches m.youtube.com).
CATEGORY_DOMAINS = {
    "video": [
        "youtube.com", "youtu.be", "netflix.com", "primevideo.com",
        "hotstar.com", "twitch.tv", "vimeo.com", "primevideo.co.in",
    ],
    "social": [
        "instagram.com", "x.com", "twitter.com", "facebook.com",
        "reddit.com", "threads.net", "linkedin.com", "snapchat.com",
        "whatsapp.com", "web.whatsapp.com", "discord.com",
    ],
    "ai_chat": [
        "chat.openai.com", "chatgpt.com", "claude.ai", "gemini.google.com",
        "copilot.microsoft.com", "chat.deepseek.com", "poe.com",
        "character.ai", "grok.com", "x.com/i/grok",
    ],
    "games": [
        "steampowered.com", "store.steampowered.com", "epicgames.com",
        "roblox.com", "chess.com", "lichess.org", "miniclip.com",
        "poki.com", "crazygames.com",
    ],
    "news": [
        "news.ycombinator.com", "bbc.com", "cnn.com", "theverge.com",
        "timesofindia.indiatimes.com", "indianexpress.com", "thehindu.com",
        "reuters.com", "apnews.com", "arstechnica.com",
    ],
    "shopping": [
        "amazon.in", "amazon.com", "flipkart.com", "myntra.com",
        "ajio.com", "ebay.com", "aliexpress.com",
    ],
    "entertainment": [
        "9gag.com", "knowyourmeme.com", "quora.com", "pinterest.com",
        "tiktok.com", "imasdk.googleapis.com",
    ],
}


def load_profiles(home: Path) -> dict:
    """User profiles in <home>/profiles/ override built-in defaults."""
    profiles = json.loads(json.dumps(DEFAULT_PROFILES))
    custom_dir = home / "profiles"
    if custom_dir.is_dir():
        for path in sorted(custom_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                profiles[data.get("name", path.stem)] = data
            except Exception:
                continue  # a broken custom profile must not crash the core
    return profiles
