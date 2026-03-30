# backend/os_control/volume.py
"""
System Volume Control
─────────────────────
Supports Windows (pycaw / ctypes), macOS (osascript), and Linux (amixer).
"""

from __future__ import annotations

import logging
import platform
import subprocess

log = logging.getLogger(__name__)

_SYSTEM = platform.system()


def set_volume(level: int) -> bool:
    """
    Set the system master volume to *level* (0-100).
    Returns True on success.
    """
    level = max(0, min(100, int(level)))
    log.info("Setting volume to %d%%", level)

    if _SYSTEM == "Windows":
        return _set_volume_windows(level)
    elif _SYSTEM == "Darwin":
        return _set_volume_macos(level)
    else:
        return _set_volume_linux(level)


def get_volume() -> int | None:
    """Return the current master volume (0-100), or None on failure."""
    if _SYSTEM == "Windows":
        return _get_volume_windows()
    elif _SYSTEM == "Darwin":
        return _get_volume_macos()
    else:
        return _get_volume_linux()


# ── Windows ───────────────────────────────────────────────────────────────────

def _set_volume_windows(level: int) -> bool:
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore
        import comtypes  # type: ignore
        from ctypes import cast, POINTER

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(
            IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None
        )
        volume_ctrl = cast(interface, POINTER(IAudioEndpointVolume))
        # pycaw uses scalar 0.0-1.0
        volume_ctrl.SetMasterVolumeLevelScalar(level / 100.0, None)
        return True
    except ImportError:
        log.warning("pycaw not available; falling back to nircmd / PowerShell")
        return _set_volume_windows_ps(level)
    except Exception as exc:  # noqa: BLE001
        log.error("Windows volume error: %s", exc)
        return False


def _set_volume_windows_ps(level: int) -> bool:
    """PowerShell / nircmd fallback."""
    try:
        script = (
            f"$obj = New-Object -ComObject WScript.Shell; "
            f"$vol = [math]::Round({level} * 655.35); "
            f"(New-Object -ComObject Shell.Application).SetVolume($vol)"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            check=True,
            capture_output=True,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("PowerShell volume error: %s", exc)
        return False


def _get_volume_windows() -> int | None:
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore
        import comtypes  # type: ignore
        from ctypes import cast, POINTER

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(
            IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None
        )
        volume_ctrl = cast(interface, POINTER(IAudioEndpointVolume))
        return round(volume_ctrl.GetMasterVolumeLevelScalar() * 100)
    except Exception:  # noqa: BLE001
        return None


# ── macOS ─────────────────────────────────────────────────────────────────────

def _set_volume_macos(level: int) -> bool:
    try:
        subprocess.run(
            ["osascript", "-e", f"set volume output volume {level}"],
            check=True, capture_output=True,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("macOS volume error: %s", exc)
        return False


def _get_volume_macos() -> int | None:
    try:
        result = subprocess.run(
            ["osascript", "-e", "output volume of (get volume settings)"],
            capture_output=True, text=True, check=True,
        )
        return int(result.stdout.strip())
    except Exception:  # noqa: BLE001
        return None


# ── Linux ─────────────────────────────────────────────────────────────────────

def _set_volume_linux(level: int) -> bool:
    try:
        subprocess.run(
            ["amixer", "-q", "sset", "Master", f"{level}%"],
            check=True, capture_output=True,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("Linux volume error: %s", exc)
        return False


def _get_volume_linux() -> int | None:
    try:
        result = subprocess.run(
            ["amixer", "sget", "Master"],
            capture_output=True, text=True, check=True,
        )
        import re
        match = re.search(r"\[(\d+)%\]", result.stdout)
        return int(match.group(1)) if match else None
    except Exception:  # noqa: BLE001
        return None
