# backend/os_control/apps.py
"""
Application Launcher / Closer
──────────────────────────────
Cross-platform helpers for opening and closing desktop applications.
The Gemini AI provides the app name as a plain string (e.g. "notepad",
"chrome"); this module maps common names to platform-specific commands.
"""

from __future__ import annotations

import logging
import platform
import subprocess

log = logging.getLogger(__name__)

_SYSTEM = platform.system()

# ── Well-known app aliases ─────────────────────────────────────────────────────
# Maps a normalised name to (windows_cmd, macos_bundle, linux_cmd)
_APP_ALIASES: dict[str, tuple[str, str, str]] = {
    "notepad":       ("notepad.exe",                  "TextEdit",               "gedit"),
    "calculator":    ("calc.exe",                     "Calculator",             "gnome-calculator"),
    "chrome":        ("chrome",                       "Google Chrome",          "google-chrome"),
    "firefox":       ("firefox",                      "Firefox",                "firefox"),
    "spotify":       ("spotify",                      "Spotify",                "spotify"),
    "vscode":        ("code",                         "Visual Studio Code",     "code"),
    "explorer":      ("explorer.exe",                 "Finder",                 "nautilus"),
    "terminal":      ("cmd.exe",                      "Terminal",               "gnome-terminal"),
    "task manager":  ("taskmgr.exe",                  "Activity Monitor",       "gnome-system-monitor"),
    "paint":         ("mspaint.exe",                  "Preview",                "gimp"),
    "word":          ("winword.exe",                  "Microsoft Word",         "libreoffice --writer"),
    "excel":         ("excel.exe",                    "Microsoft Excel",        "libreoffice --calc"),
    "powerpoint":    ("powerpnt.exe",                 "Microsoft PowerPoint",   "libreoffice --impress"),
    "settings":      ("ms-settings:",                 "System Preferences",     "gnome-control-center"),
    "discord":       ("discord",                      "Discord",                "discord"),
    "slack":         ("slack",                        "Slack",                  "slack"),
    "zoom":          ("zoom",                         "zoom.us",                "zoom"),
    "vlc":           ("vlc",                          "VLC",                    "vlc"),
    "obsidian":      ("obsidian",                     "Obsidian",               "obsidian"),
}


def open_app(name: str) -> bool:
    """Launch an application by (fuzzy) name. Returns True on success."""
    normalised = _normalise(name)
    log.info("Opening app: %r (normalised: %r)", name, normalised)

    if _SYSTEM == "Windows":
        return _open_windows(normalised, name)
    elif _SYSTEM == "Darwin":
        return _open_macos(normalised, name)
    else:
        return _open_linux(normalised, name)


def close_app(name: str) -> bool:
    """Terminate a running application by name. Returns True on success."""
    normalised = _normalise(name)
    log.info("Closing app: %r (normalised: %r)", name, normalised)

    if _SYSTEM == "Windows":
        return _close_windows(normalised, name)
    elif _SYSTEM == "Darwin":
        return _close_macos(normalised, name)
    else:
        return _close_linux(normalised, name)


def search_web(query: str) -> bool:
    """Open the default browser with a web search for *query*."""
    import urllib.parse
    import webbrowser
    url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)
    webbrowser.open(url)
    return True


# ── Windows ───────────────────────────────────────────────────────────────────

def _open_windows(normalised: str, original: str) -> bool:
    cmd = _APP_ALIASES.get(normalised, (original, "", ""))[0]
    try:
        subprocess.Popen(cmd, shell=True)
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("Failed to open app on Windows: %s", exc)
        return False


def _close_windows(normalised: str, original: str) -> bool:
    process_name = _APP_ALIASES.get(normalised, (original, "", ""))[0]
    try:
        subprocess.run(["taskkill", "/F", "/IM", process_name], check=True, capture_output=True)
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("Failed to close app on Windows: %s", exc)
        return False


# ── macOS ─────────────────────────────────────────────────────────────────────

def _open_macos(normalised: str, original: str) -> bool:
    bundle = _APP_ALIASES.get(normalised, ("", original, ""))[1]
    try:
        subprocess.Popen(["open", "-a", bundle])
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("Failed to open app on macOS: %s", exc)
        return False


def _close_macos(normalised: str, original: str) -> bool:
    bundle = _APP_ALIASES.get(normalised, ("", original, ""))[1]
    try:
        subprocess.run(["osascript", "-e", f'quit app "{bundle}"'], check=True, capture_output=True)
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("Failed to close app on macOS: %s", exc)
        return False


# ── Linux ─────────────────────────────────────────────────────────────────────

def _open_linux(normalised: str, original: str) -> bool:
    cmd = _APP_ALIASES.get(normalised, ("", "", original))[2]
    try:
        subprocess.Popen(cmd.split())
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("Failed to open app on Linux: %s", exc)
        return False


def _close_linux(normalised: str, original: str) -> bool:
    cmd = _APP_ALIASES.get(normalised, ("", "", original))[2].split()[0]
    try:
        subprocess.run(["pkill", "-f", cmd], check=True)
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("Failed to close app on Linux: %s", exc)
        return False


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalise(name: str) -> str:
    return name.lower().strip()
