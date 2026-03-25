import os
from pathlib import Path

import yaml

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "htmldispatch"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
HISTORY_FILE = CONFIG_DIR / "history.json"

DEFAULT_CONFIG = {
    "popup_on_unknown": True,
    "default_browser": "firefox",
    "default_profile": None,
    "rules": [
        {
            "name": "Work GitHub",
            "pattern": r"https?://github\.com/myorg",
            "browser": "firefox",
            "profile": "Work",
        },
        {
            "name": "Teams",
            "pattern": r"https?://teams\.microsoft\.com",
            "browser": "chrome",
            "profile": None,
        },
        {
            "name": "Teams links",
            "pattern": r"https?://.*\.teams\.microsoft\.com",
            "browser": "chrome",
            "profile": None,
        },
    ],
}


def ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config():
    ensure_config_dir()
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            config = yaml.safe_load(f)
            if config:
                return config
    save_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG.copy()


def save_config(config):
    ensure_config_dir()
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
