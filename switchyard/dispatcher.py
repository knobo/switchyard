import re
import subprocess

from .browsers import get_firefox_profile_path
from .config import load_config
from .history import (
    add_entry,
    get_domain_last_used,
    get_last_used,
)


def find_matching_rule(url):
    config = load_config()
    for rule in config.get("rules", []):
        if re.search(rule["pattern"], url):
            return rule
    return None


def resolve_destination(url):
    """Resolve where a URL should open. Returns (browser, profile, source_label).

    Fallback chain:
    1. Regexp rules
    2. Exact URL history
    3. Domain history (domain + first path segment)
    4. Global default from config
    """
    # 1. Regexp rules
    rule = find_matching_rule(url)
    if rule:
        return rule["browser"], rule.get("profile"), f"Rule: {rule['name']}"

    # 2. Exact URL history
    browser, profile = get_last_used(url)
    if browser:
        return browser, profile, "URL history"

    # 3. Domain history
    browser, profile = get_domain_last_used(url)
    if browser:
        return browser, profile, "Domain match"

    # 4. Global default
    config = load_config()
    browser = config.get("default_browser", "firefox")
    profile = config.get("default_profile")

    # Check if there's any history at all for "last used" fallback
    last_browser, last_profile = get_last_used()
    if last_browser:
        return last_browser, last_profile, "Last used"

    return browser, profile, "Default"


def open_url(url, browser, profile=None, rule_name=None):
    cmd = build_command(browser, profile, url)
    subprocess.Popen(cmd)
    add_entry(url, browser, profile, rule_name)


def build_command(browser, profile, url):
    if browser == "firefox":
        cmd = ["firefox"]
        if profile:
            profile_path = get_firefox_profile_path(profile)
            if profile_path:
                cmd += ["--profile", profile_path]
            else:
                cmd += ["-P", profile]
        cmd.append(url)
        return cmd
    elif browser == "chrome":
        cmd = ["google-chrome"]
        if profile:
            cmd += [f"--profile-directory={profile}"]
        cmd.append(url)
        return cmd
    else:
        return [browser, url]


def dispatch(url):
    """Auto-dispatch URL without GUI. Returns True if dispatched."""
    config = load_config()
    if config.get("popup_on_unknown", True):
        # Only auto-dispatch if we have a rule match
        rule = find_matching_rule(url)
        if rule:
            if rule.get("confirm"):
                return False
            open_url(url, rule["browser"], rule.get("profile"), rule.get("name"))
            return True
        return False

    # Intercept off — still check for confirm rules
    rule = find_matching_rule(url)
    if rule and rule.get("confirm"):
        return False

    browser, profile, source = resolve_destination(url)
    open_url(url, browser, profile, source)
    return True
