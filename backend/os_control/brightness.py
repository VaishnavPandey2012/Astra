# backend/os_control/brightness.py
"""
Display Brightness Control
──────────────────────────
Supports Windows (screen-brightness-control / wmi), macOS (brightness CLI),
and Linux (xrandr / screen-brightness-control).
"""

from __future__ import annotations

import logging
import platform
import subprocess

log = logging.getLogger(__name__)

_SYSTEM = platform.system()


def set_brightness(level: int) -> bool:
    """
    Set display brightness to *level* (0-100).
    Returns True on success.
    """
    level = max(0, min(100, int(level)))
    log.info("Setting brightness to %d%%", level)

    if _SYSTEM == "Windows":
        return _set_brightness_windows(level)
    elif _SYSTEM == "Darwin":
        return _set_brightness_macos(level)
    else:
        return _set_brightness_linux(level)


def get_brightness() -> int | None:
    """Return current brightness (0-100) or None on failure."""
    if _SYSTEM == "Windows":
        return _get_brightness_windows()
    elif _SYSTEM == "Darwin":
        return _get_brightness_macos()
    else:
        return _get_brightness_linux()


# ── Windows ───────────────────────────────────────────────────────────────────

def _set_brightness_windows(level: int) -> bool:
    # Primary: screen-brightness-control
    try:
        import screen_brightness_control as sbc  # type: ignore
        sbc.set_brightness(level)
        return True
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001
        log.warning("screen-brightness-control failed: %s", exc)

    # Fallback: WMI
    try:
        import wmi  # type: ignore
        wmi_obj = wmi.WMI(namespace="wmi")
        methods = wmi_obj.WmiMonitorBrightnessMethods()[0]
        methods.WmiSetBrightness(level, 0)
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("WMI brightness error: %s", exc)
        return False


def _get_brightness_windows() -> int | None:
    try:
        import screen_brightness_control as sbc  # type: ignore
        result = sbc.get_brightness()
        return result[0] if isinstance(result, list) else int(result)
    except Exception:  # noqa: BLE001
        return None


# ── macOS ─────────────────────────────────────────────────────────────────────

def _set_brightness_macos(level: int) -> bool:
    """Requires the 'brightness' CLI: brew install brightness"""
    try:
        subprocess.run(
            ["brightness", str(level / 100)],
            check=True, capture_output=True,
        )
        return True
    except FileNotFoundError:
        log.warning("'brightness' CLI not found; install with: brew install brightness")
    except Exception as exc:  # noqa: BLE001
        log.error("macOS brightness error: %s", exc)
    return False


def _get_brightness_macos() -> int | None:
    try:
        result = subprocess.run(
            ["brightness", "-l"],
            capture_output=True, text=True,
        )
        import re
        match = re.search(r"brightness\s+([\d.]+)", result.stdout)
        if match:
            return round(float(match.group(1)) * 100)
    except Exception:  # noqa: BLE001
        pass
    return None


# ── Linux ─────────────────────────────────────────────────────────────────────

def _set_brightness_linux(level: int) -> bool:
    # Try screen-brightness-control first
    try:
        import screen_brightness_control as sbc  # type: ignore
        sbc.set_brightness(level)
        return True
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001
        log.warning("sbc failed: %s", exc)

    # Fallback: xrandr
    try:
        normalized = level / 100.0
        result = subprocess.run(
            ["xrandr", "--listmonitors"],
            capture_output=True, text=True,
        )
        import re
        monitors = re.findall(r"\+(\S+)\s+\d+/", result.stdout)
        if monitors:
            subprocess.run(
                ["xrandr", "--output", monitors[0], "--brightness", str(normalized)],
                check=True,
            )
            return True
    except Exception as exc:  # noqa: BLE001
        log.error("xrandr brightness error: %s", exc)

    return False


def _get_brightness_linux() -> int | None:
    try:
        import screen_brightness_control as sbc  # type: ignore
        result = sbc.get_brightness()
        return result[0] if isinstance(result, list) else int(result)
    except Exception:  # noqa: BLE001
        return None
