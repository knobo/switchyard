import json
from datetime import datetime
from urllib.parse import urlparse

from .config import HISTORY_FILE, ensure_config_dir

MAX_HISTORY = 500


def load_history():
    ensure_config_dir()
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return []


def save_history(history):
    ensure_config_dir()
    with open(HISTORY_FILE, "w") as f:
        json.dump(history[-MAX_HISTORY:], f, indent=2)


def add_entry(url, browser, profile, rule_name=None):
    history = load_history()
    history.append({
        "url": url,
        "browser": browser,
        "profile": profile,
        "rule": rule_name,
        "timestamp": datetime.now().isoformat(),
    })
    save_history(history)


def get_last_used(url=None):
    """Return (browser, profile) from history.

    If url is given, find the last time that specific URL was opened.
    Otherwise return the most recent entry.
    """
    history = load_history()
    if url:
        for entry in reversed(history):
            if entry.get("url") == url:
                return entry.get("browser"), entry.get("profile")
    if history:
        last = history[-1]
        return last.get("browser"), last.get("profile")
    return None, None


def _url_domain_prefix(url):
    """Extract domain + first path segment for domain matching."""
    try:
        parsed = urlparse(url)
        host = parsed.netloc or parsed.hostname or ""
        path_parts = parsed.path.strip("/").split("/")
        if path_parts and path_parts[0]:
            return f"{host}/{path_parts[0]}"
        return host
    except Exception:
        return None


def get_domain_last_used(url):
    """Return (browser, profile) from history matching same domain+first-path-segment."""
    prefix = _url_domain_prefix(url)
    if not prefix:
        return None, None
    history = load_history()
    for entry in reversed(history):
        entry_prefix = _url_domain_prefix(entry.get("url", ""))
        if entry_prefix == prefix:
            return entry.get("browser"), entry.get("profile")
    return None, None


def get_unique_destinations():
    """Return list of unique (browser, profile) tuples from history, most recent first."""
    history = load_history()
    seen = set()
    destinations = []
    for entry in reversed(history):
        browser = entry.get("browser")
        profile = entry.get("profile")
        key = (browser, profile)
        if key not in seen:
            seen.add(key)
            destinations.append(key)
    return destinations
