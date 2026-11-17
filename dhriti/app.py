"""Dhriti Desktop Application Launcher.

Launches the Dhriti Dashboard in a dedicated, native-framed desktop application
window using the system's local Chromium engine (Chrome/Edge in --app mode).
No Electron overhead, zero extra memory, native taskbar integration.
"""

import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def find_browser_app_binary() -> str:
    """Locates Chrome or Edge to run in native application window mode."""
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        shutil.which("chrome"),
        shutil.which("msedge"),
        shutil.which("brave"),
    ]
    for c in candidates:
        if c and Path(c).is_file():
            return str(c)
    return ""


def ensure_daemon_running(home: Path) -> None:
    """Checks if the local bridge is responding on port 7311; starts it if offline."""
    url = "http://127.0.0.1:7311/healthz"
    try:
        with urllib.request.urlopen(url, timeout=1.0) as resp:
            if resp.status == 200:
                return
    except Exception:
        pass

    # Start the daemon as a detached background process
    print("Starting Dhriti daemon in background...")
    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = subprocess.CREATE_NO_WINDOW | getattr(subprocess, "DETACHED_PROCESS", 0)

    repo_root = Path(__file__).parent.parent
    subprocess.Popen(
        [sys.executable, "-m", "dhriti.cli", "daemon"],
        cwd=str(repo_root),
        creationflags=creation_flags,
        close_fds=True
    )

    # Wait up to 5 seconds for healthz
    for _ in range(25):
        time.sleep(0.2)
        try:
            with urllib.request.urlopen(url, timeout=0.5) as resp:
                if resp.status == 200:
                    print("Dhriti daemon active.")
                    return
        except Exception:
            pass


def ensure_sidecar_running(home: Path, port: int = 8765) -> None:
    """Starts the classifier sidecar if not already running."""
    url = f"http://127.0.0.1:{port}/health"
    try:
        from .bridge import ensure_token
        tok = ensure_token(home)
        req = urllib.request.Request(url, headers={"X-Dhriti-Token": tok})
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            if resp.status == 200:
                return
    except Exception:
        pass

    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = subprocess.CREATE_NO_WINDOW | getattr(subprocess, "DETACHED_PROCESS", 0)

    repo_root = Path(__file__).parent.parent
    subprocess.Popen(
        [sys.executable, "-m", "dhriti.cli", "sidecar", "--port", str(port)],
        cwd=str(repo_root),
        creationflags=creation_flags,
        close_fds=True
    )
    time.sleep(0.5)


def launch_desktop_app(port: int = 7311, width: int = 1280, height: int = 860) -> None:
    """Launches the dedicated standalone app window."""
    repo_root = Path(__file__).parent.parent
    home = Path(os.environ.get("DHRITI_HOME", Path.home() / ".dhriti"))
    ensure_daemon_running(home)
    ensure_sidecar_running(home)

    token_file = home / "bridge_token"
    token = token_file.read_text(encoding="utf-8").strip() if token_file.exists() else ""
    target_url = f"http://127.0.0.1:{port}/dashboard" + (f"?token={token}" if token else "")

    browser_bin = find_browser_app_binary()
    if not browser_bin:
        # Fallback to standard browser launch
        import webbrowser
        print(f"Opening dashboard in default browser: {target_url}")
        webbrowser.open(target_url)
        return

    user_data_dir = home / "app_profile"
    user_data_dir.mkdir(parents=True, exist_ok=True)

    args = [
        browser_bin,
        f"--app={target_url}",
        f"--window-size={width},{height}",
        f"--user-data-dir={user_data_dir}",
        "--disable-extensions",
        "--no-first-run",
        "--no-default-browser-check"
    ]
    print(f"Launching Dhriti App Window ({Path(browser_bin).stem})...")
    subprocess.Popen(args)


if __name__ == "__main__":
    launch_desktop_app()

