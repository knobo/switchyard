"""Detect available browsers and Firefox profiles."""

import configparser
import shutil
from pathlib import Path

FIREFOX_PROFILE_DIRS = [
    Path.home() / "snap/firefox/common/.mozilla/firefox",
    Path.home() / ".mozilla/firefox",
]


def get_firefox_profiles():
    """Return list of Firefox profile names."""
    profiles = []
    for profiles_ini in [d / "profiles.ini" for d in FIREFOX_PROFILE_DIRS]:
        if profiles_ini.exists():
            config = configparser.ConfigParser()
            config.read(profiles_ini)
            for section in config.sections():
                if section.startswith("Profile"):
                    name = config.get(section, "Name", fallback=None)
                    if name:
                        profiles.append(name)
    return profiles


def get_firefox_profile_path(profile_name):
    """Return the full path to a Firefox profile directory, or None."""
    for base_dir in FIREFOX_PROFILE_DIRS:
        profiles_ini = base_dir / "profiles.ini"
        if profiles_ini.exists():
            config = configparser.ConfigParser()
            config.read(profiles_ini)
            for section in config.sections():
                if section.startswith("Profile"):
                    name = config.get(section, "Name", fallback=None)
                    if name == profile_name:
                        path = config.get(section, "Path", fallback=None)
                        is_relative = config.getboolean(section, "IsRelative", fallback=True)
                        if path:
                            if is_relative:
                                return str(base_dir / path)
                            return path
    return None



def get_chrome_profiles():
    """Return list of Chrome profile directory names."""
    profiles = []
    for chrome_dir in [
        Path.home() / ".config/google-chrome",
        Path.home() / "snap/chromium/common/chromium",
    ]:
        if chrome_dir.exists():
            for p in sorted(chrome_dir.iterdir()):
                if p.is_dir() and (p / "Preferences").exists():
                    profiles.append(p.name)
    return profiles


def get_available_browsers():
    """Return dict of browser name -> path."""
    browsers = {}
    for name, cmds in [
        ("firefox", ["firefox"]),
        ("chrome", ["google-chrome", "chromium-browser", "chromium"]),
    ]:
        for cmd in cmds:
            if shutil.which(cmd):
                browsers[name] = cmd
                break
    return browsers
