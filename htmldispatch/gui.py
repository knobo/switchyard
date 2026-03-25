import re
import tkinter as tk
from tkinter import messagebox

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox

from .browsers import get_available_browsers, get_chrome_profiles, get_firefox_profiles
from .config import load_config, save_config
from .dispatcher import open_url, resolve_destination
from .history import get_unique_destinations, load_history


class DispatcherApp:
    def __init__(self, url=None):
        self.url = url
        self.config = load_config()

        self.root = ttk.Window(
            title="HTML Dispatch",
            themename="darkly",
            size=(750, 600),
            resizable=(True, True),
        )
        self.root.place_window_center()

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=BOTH, expand=True, padx=10, pady=10)

        # Dispatch tab (shown when URL is provided)
        self.dispatch_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.dispatch_frame, text="Dispatch")
        self._build_dispatch_tab()

        # History tab
        self.history_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.history_frame, text="History")
        self._build_history_tab()

        # Rules tab
        self.rules_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.rules_frame, text="Rules")
        self._build_rules_tab()

        # Settings tab
        self.settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_frame, text="Settings")
        self._build_settings_tab()

        if url:
            self.notebook.select(0)
        else:
            self.notebook.select(1)

        # Keybindings
        self.root.bind("<Control-Return>", self._do_dispatch)
        self.root.bind("<Control-space>", self._auto_dispatch)
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.root.bind("<Up>", self._on_key_up)
        self.root.bind("<Down>", self._on_key_down)

    def run(self):
        self.root.mainloop()

    # ── Dispatch tab ──────────────────────────────────────────────

    def _build_dispatch_tab(self):
        frame = self.dispatch_frame

        ttk.Label(frame, text="URL:", font=("", 11, "bold")).pack(
            anchor=W, padx=10, pady=(10, 0)
        )
        self.url_var = tk.StringVar(value=self.url or "")
        url_entry = ttk.Entry(frame, textvariable=self.url_var, font=("", 10))
        url_entry.pack(fill=X, padx=10, pady=5)

        # Source label — shows where the suggestion came from
        self.source_var = tk.StringVar(value="")
        self.source_label = ttk.Label(
            frame, textvariable=self.source_var, font=("", 9), bootstyle="info"
        )
        self.source_label.pack(anchor=W, padx=10)

        ttk.Label(frame, text="Browser:").pack(anchor=W, padx=10, pady=(10, 0))
        self.browser_var = tk.StringVar()
        browsers = get_available_browsers()
        browser_names = list(browsers.keys())
        self.browser_combo = ttk.Combobox(
            frame, textvariable=self.browser_var, values=browser_names, state="readonly"
        )
        self.browser_combo.pack(fill=X, padx=10, pady=5)
        if browser_names:
            self.browser_combo.current(0)
        self.browser_combo.bind("<<ComboboxSelected>>", self._on_browser_change)

        ttk.Label(frame, text="Profile:").pack(anchor=W, padx=10, pady=(10, 0))
        self.profile_var = tk.StringVar()
        self.profile_combo = ttk.Combobox(
            frame, textvariable=self.profile_var, state="readonly"
        )
        self.profile_combo.pack(fill=X, padx=10, pady=5)
        self._update_profiles()

        # Build destinations list and pre-fill
        self._destinations = get_unique_destinations()
        self._dest_index = -1  # -1 means "resolved suggestion", not from list
        self._prefill_destination()

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=X, padx=10, pady=15)

        ttk.Button(
            btn_frame, text="Open (Ctrl+Enter)", bootstyle=SUCCESS, command=self._do_dispatch
        ).pack(side=LEFT, padx=5)

        ttk.Button(
            btn_frame,
            text="Auto (Ctrl+Space)",
            bootstyle=PRIMARY,
            command=self._auto_dispatch,
        ).pack(side=LEFT, padx=5)

        ttk.Button(
            btn_frame,
            text="Open & Save Rule",
            bootstyle=INFO,
            command=self._dispatch_and_save_rule,
        ).pack(side=LEFT, padx=5)

        ttk.Button(
            btn_frame, text="Cancel (Esc)", bootstyle=SECONDARY, command=self.root.destroy
        ).pack(side=RIGHT, padx=5)

    def _on_browser_change(self, event=None):
        self._update_profiles()

    def _update_profiles(self):
        browser = self.browser_var.get()
        if browser == "firefox":
            profiles = get_firefox_profiles()
        elif browser == "chrome":
            profiles = get_chrome_profiles()
        else:
            profiles = []
        profiles = ["(none)"] + profiles
        self.profile_combo.configure(values=profiles)
        if profiles:
            self.profile_combo.current(0)

    def _set_destination(self, browser, profile):
        """Set the browser and profile combos to given values."""
        if browser:
            self.browser_var.set(browser)
            self._update_profiles()
            self.profile_var.set(profile if profile else "(none)")

    def _prefill_destination(self):
        """Pre-fill browser/profile using the resolve fallback chain."""
        url = self.url_var.get().strip()
        if not url:
            self.source_var.set("")
            return
        browser, profile, source = resolve_destination(url)
        self._set_destination(browser, profile)
        self.source_var.set(source)
        self._dest_index = -1

    def _on_key_up(self, event=None):
        """Navigate to previous destination in history."""
        if not self._destinations:
            return
        if self._dest_index < len(self._destinations) - 1:
            self._dest_index += 1
        self._apply_dest_from_list()

    def _on_key_down(self, event=None):
        """Navigate to next destination in history."""
        if self._dest_index > 0:
            self._dest_index -= 1
            self._apply_dest_from_list()
        elif self._dest_index == 0:
            # Go back to resolved suggestion
            self._dest_index = -1
            self._prefill_destination()

    def _apply_dest_from_list(self):
        """Apply the destination at current _dest_index."""
        if self._dest_index < 0 or self._dest_index >= len(self._destinations):
            return
        browser, profile = self._destinations[self._dest_index]
        self._set_destination(browser, profile)
        pos = self._dest_index + 1
        total = len(self._destinations)
        self.source_var.set(f"History ({pos}/{total})")

    def _auto_dispatch(self, event=None):
        """Dispatch URL using the resolve fallback chain."""
        url = self.url_var.get().strip()
        if not url:
            return
        browser, profile, source = resolve_destination(url)
        open_url(url, browser, profile, source)
        self.root.destroy()

    def _do_dispatch(self, event=None):
        url = self.url_var.get().strip()
        if not url:
            return
        browser = self.browser_var.get()
        profile = self.profile_var.get()
        if profile == "(none)":
            profile = None
        open_url(url, browser, profile, "manual")
        self.root.destroy()

    def _dispatch_and_save_rule(self):
        url = self.url_var.get().strip()
        if not url:
            return
        browser = self.browser_var.get()
        profile = self.profile_var.get()
        if profile == "(none)":
            profile = None

        # Ask for rule pattern
        dialog = RuleDialog(self.root, url, browser, profile)
        self.root.wait_window(dialog.top)
        if dialog.result:
            rule = dialog.result
            self.config["rules"].append(rule)
            save_config(self.config)
            open_url(url, browser, profile, rule["name"])
            self._refresh_rules_list()
            self.root.destroy()

    # ── History tab ───────────────────────────────────────────────

    def _build_history_tab(self):
        frame = self.history_frame

        # Toolbar
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill=X, padx=10, pady=(10, 0))
        ttk.Button(
            toolbar, text="Refresh", bootstyle=SECONDARY, command=self._refresh_history
        ).pack(side=LEFT)
        ttk.Button(
            toolbar, text="Re-open selected", bootstyle=SUCCESS, command=self._reopen_from_history
        ).pack(side=LEFT, padx=10)
        ttk.Button(
            toolbar,
            text="Re-dispatch selected",
            bootstyle=INFO,
            command=self._redispatch_from_history,
        ).pack(side=LEFT)

        cols = ("timestamp", "url", "browser", "profile", "rule")
        self.history_tree = ttk.Treeview(frame, columns=cols, show="headings", height=15)
        self.history_tree.heading("timestamp", text="Time")
        self.history_tree.heading("url", text="URL")
        self.history_tree.heading("browser", text="Browser")
        self.history_tree.heading("profile", text="Profile")
        self.history_tree.heading("rule", text="Rule")
        self.history_tree.column("timestamp", width=140)
        self.history_tree.column("url", width=300)
        self.history_tree.column("browser", width=70)
        self.history_tree.column("profile", width=80)
        self.history_tree.column("rule", width=100)

        scrollbar = ttk.Scrollbar(frame, orient=VERTICAL, command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)

        self.history_tree.pack(fill=BOTH, expand=True, padx=(10, 0), pady=10)
        scrollbar.pack(side=RIGHT, fill=Y, pady=10, padx=(0, 10))

        self._refresh_history()

    def _refresh_history(self):
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        history = load_history()
        for entry in reversed(history):
            ts = entry.get("timestamp", "")[:19].replace("T", " ")
            self.history_tree.insert(
                "",
                END,
                values=(
                    ts,
                    entry.get("url", ""),
                    entry.get("browser", ""),
                    entry.get("profile", ""),
                    entry.get("rule", ""),
                ),
            )

    def _get_selected_history_url(self):
        sel = self.history_tree.selection()
        if not sel:
            Messagebox.show_info("Select a history entry first.", "No selection")
            return None
        values = self.history_tree.item(sel[0], "values")
        return values[1]  # url

    def _reopen_from_history(self):
        sel = self.history_tree.selection()
        if not sel:
            Messagebox.show_info("Select a history entry first.", "No selection")
            return
        values = self.history_tree.item(sel[0], "values")
        url, browser, profile = values[1], values[2], values[3]
        if not profile:
            profile = None
        open_url(url, browser, profile, "re-open")
        self._refresh_history()

    def _redispatch_from_history(self):
        url = self._get_selected_history_url()
        if url:
            self.url_var.set(url)
            self._prefill_destination()
            self.notebook.select(0)

    # ── Rules tab ─────────────────────────────────────────────────

    def _build_rules_tab(self):
        frame = self.rules_frame

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill=X, padx=10, pady=(10, 0))
        ttk.Button(
            toolbar, text="Add Rule", bootstyle=SUCCESS, command=self._add_rule
        ).pack(side=LEFT)
        ttk.Button(
            toolbar, text="Edit Rule", bootstyle=INFO, command=self._edit_rule
        ).pack(side=LEFT, padx=10)
        ttk.Button(
            toolbar, text="Delete Rule", bootstyle=DANGER, command=self._delete_rule
        ).pack(side=LEFT)
        ttk.Button(
            toolbar, text="Move Up", bootstyle=SECONDARY, command=self._move_rule_up
        ).pack(side=LEFT, padx=10)
        ttk.Button(
            toolbar, text="Move Down", bootstyle=SECONDARY, command=self._move_rule_down
        ).pack(side=LEFT)

        cols = ("name", "pattern", "browser", "profile", "confirm")
        self.rules_tree = ttk.Treeview(frame, columns=cols, show="headings", height=12)
        self.rules_tree.heading("name", text="Name")
        self.rules_tree.heading("pattern", text="Pattern (regex)")
        self.rules_tree.heading("browser", text="Browser")
        self.rules_tree.heading("profile", text="Profile")
        self.rules_tree.heading("confirm", text="Confirm")
        self.rules_tree.column("name", width=120)
        self.rules_tree.column("pattern", width=250)
        self.rules_tree.column("browser", width=80)
        self.rules_tree.column("profile", width=100)
        self.rules_tree.column("confirm", width=60)
        self.rules_tree.pack(fill=BOTH, expand=True, padx=10, pady=10)

        self._refresh_rules_list()

    def _refresh_rules_list(self):
        for item in self.rules_tree.get_children():
            self.rules_tree.delete(item)
        for rule in self.config.get("rules", []):
            self.rules_tree.insert(
                "",
                END,
                values=(
                    rule.get("name", ""),
                    rule.get("pattern", ""),
                    rule.get("browser", ""),
                    rule.get("profile", ""),
                    "Yes" if rule.get("confirm") else "",
                ),
            )

    def _add_rule(self):
        dialog = RuleDialog(self.root)
        self.root.wait_window(dialog.top)
        if dialog.result:
            self.config["rules"].append(dialog.result)
            save_config(self.config)
            self._refresh_rules_list()

    def _edit_rule(self):
        sel = self.rules_tree.selection()
        if not sel:
            return
        idx = self.rules_tree.index(sel[0])
        rule = self.config["rules"][idx]
        dialog = RuleDialog(self.root, rule=rule)
        self.root.wait_window(dialog.top)
        if dialog.result:
            self.config["rules"][idx] = dialog.result
            save_config(self.config)
            self._refresh_rules_list()

    def _delete_rule(self):
        sel = self.rules_tree.selection()
        if not sel:
            return
        idx = self.rules_tree.index(sel[0])
        if Messagebox.yesno("Delete this rule?", "Confirm") == "Yes":
            self.config["rules"].pop(idx)
            save_config(self.config)
            self._refresh_rules_list()

    def _move_rule_up(self):
        sel = self.rules_tree.selection()
        if not sel:
            return
        idx = self.rules_tree.index(sel[0])
        if idx > 0:
            rules = self.config["rules"]
            rules[idx - 1], rules[idx] = rules[idx], rules[idx - 1]
            save_config(self.config)
            self._refresh_rules_list()

    def _move_rule_down(self):
        sel = self.rules_tree.selection()
        if not sel:
            return
        idx = self.rules_tree.index(sel[0])
        rules = self.config["rules"]
        if idx < len(rules) - 1:
            rules[idx], rules[idx + 1] = rules[idx + 1], rules[idx]
            save_config(self.config)
            self._refresh_rules_list()

    # ── Settings tab ──────────────────────────────────────────────

    def _build_settings_tab(self):
        frame = self.settings_frame

        self.popup_var = tk.BooleanVar(value=self.config.get("popup_on_unknown", True))
        ttk.Checkbutton(
            frame,
            text="Show popup for unknown URLs",
            variable=self.popup_var,
            bootstyle="round-toggle",
            command=self._save_settings,
        ).pack(anchor=W, padx=10, pady=(15, 5))

        ttk.Label(frame, text="Default browser for unknown URLs:").pack(
            anchor=W, padx=10, pady=(15, 0)
        )
        self.default_browser_var = tk.StringVar(
            value=self.config.get("default_browser", "firefox")
        )
        browsers = list(get_available_browsers().keys())
        ttk.Combobox(
            frame,
            textvariable=self.default_browser_var,
            values=browsers,
            state="readonly",
        ).pack(fill=X, padx=10, pady=5)

        ttk.Label(frame, text="Default profile:").pack(anchor=W, padx=10, pady=(10, 0))
        self.default_profile_var = tk.StringVar(
            value=self.config.get("default_profile") or ""
        )
        ttk.Entry(frame, textvariable=self.default_profile_var).pack(
            fill=X, padx=10, pady=5
        )

        ttk.Button(
            frame, text="Save Settings", bootstyle=SUCCESS, command=self._save_settings
        ).pack(anchor=W, padx=10, pady=15)

        ttk.Separator(frame).pack(fill=X, padx=10, pady=5)

        self.default_status_var = tk.StringVar()
        self._check_default_browser()
        ttk.Label(frame, textvariable=self.default_status_var).pack(
            anchor=W, padx=10, pady=(10, 0)
        )
        ttk.Button(
            frame,
            text="Set as default browser",
            bootstyle=WARNING,
            command=self._set_as_default,
        ).pack(anchor=W, padx=10, pady=5)

    def _check_default_browser(self):
        import subprocess
        try:
            result = subprocess.run(
                ["xdg-settings", "get", "default-web-browser"],
                capture_output=True, text=True, timeout=5,
            )
            current = result.stdout.strip()
            if current == "htmldispatch.desktop":
                self.default_status_var.set("htmldispatch is the default browser")
            else:
                self.default_status_var.set(f"Default browser: {current}")
        except Exception:
            self.default_status_var.set("Could not detect default browser")

    def _set_as_default(self):
        import subprocess
        for cmd in [
            ["xdg-settings", "set", "default-web-browser", "htmldispatch.desktop"],
            ["xdg-mime", "default", "htmldispatch.desktop", "x-scheme-handler/http"],
            ["xdg-mime", "default", "htmldispatch.desktop", "x-scheme-handler/https"],
        ]:
            subprocess.run(cmd, capture_output=True, timeout=5)
        self._check_default_browser()

    def _save_settings(self):
        self.config["popup_on_unknown"] = self.popup_var.get()
        self.config["default_browser"] = self.default_browser_var.get()
        profile = self.default_profile_var.get().strip()
        self.config["default_profile"] = profile if profile else None
        save_config(self.config)


class RuleDialog:
    def __init__(self, parent, url=None, browser=None, profile=None, rule=None):
        self.result = None
        self.top = tk.Toplevel(parent)
        self.top.title("Rule")
        self.top.geometry("500x340")
        self.top.transient(parent)
        self.top.grab_set()

        ttk.Label(self.top, text="Rule name:").pack(anchor=W, padx=10, pady=(10, 0))
        self.name_var = tk.StringVar(value=rule["name"] if rule else "")
        ttk.Entry(self.top, textvariable=self.name_var).pack(fill=X, padx=10, pady=2)

        ttk.Label(self.top, text="URL pattern (regex):").pack(
            anchor=W, padx=10, pady=(10, 0)
        )
        default_pattern = ""
        if rule:
            default_pattern = rule["pattern"]
        elif url:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            # Suggest a pattern based on the domain + first path segment
            path_parts = parsed.path.strip("/").split("/")
            if path_parts and path_parts[0]:
                default_pattern = (
                    rf"https?://{re.escape(parsed.netloc)}/{re.escape(path_parts[0])}"
                )
            else:
                default_pattern = rf"https?://{re.escape(parsed.netloc)}"
        self.pattern_var = tk.StringVar(value=default_pattern)
        ttk.Entry(self.top, textvariable=self.pattern_var).pack(fill=X, padx=10, pady=2)

        ttk.Label(self.top, text="Browser:").pack(anchor=W, padx=10, pady=(10, 0))
        self.browser_var = tk.StringVar(value=rule["browser"] if rule else (browser or "firefox"))
        browsers = list(get_available_browsers().keys())
        browser_combo = ttk.Combobox(
            self.top, textvariable=self.browser_var, values=browsers, state="readonly"
        )
        browser_combo.pack(fill=X, padx=10, pady=2)
        browser_combo.bind("<<ComboboxSelected>>", self._on_browser_change)

        ttk.Label(self.top, text="Profile:").pack(anchor=W, padx=10, pady=(10, 0))
        self.profile_var = tk.StringVar(
            value=rule.get("profile", "") if rule else (profile or "")
        )
        self.profile_combo = ttk.Combobox(
            self.top, textvariable=self.profile_var, state="readonly"
        )
        self.profile_combo.pack(fill=X, padx=10, pady=2)
        self._update_profiles()

        self.confirm_var = tk.BooleanVar(value=rule.get("confirm", False) if rule else False)
        ttk.Checkbutton(
            self.top,
            text="Always confirm (show popup before opening)",
            variable=self.confirm_var,
            bootstyle="round-toggle",
        ).pack(anchor=W, padx=10, pady=(10, 0))

        btn_frame = ttk.Frame(self.top)
        btn_frame.pack(fill=X, padx=10, pady=15)
        ttk.Button(btn_frame, text="Save", bootstyle=SUCCESS, command=self._save).pack(
            side=LEFT, padx=5
        )
        ttk.Button(
            btn_frame, text="Cancel", bootstyle=SECONDARY, command=self.top.destroy
        ).pack(side=LEFT, padx=5)

    def _on_browser_change(self, event=None):
        self._update_profiles()

    def _update_profiles(self):
        browser = self.browser_var.get()
        if browser == "firefox":
            profiles = get_firefox_profiles()
        elif browser == "chrome":
            profiles = get_chrome_profiles()
        else:
            profiles = []
        profiles = ["(none)"] + profiles
        self.profile_combo.configure(values=profiles)
        current = self.profile_var.get()
        if current not in profiles:
            self.profile_combo.current(0)

    def _save(self):
        name = self.name_var.get().strip()
        pattern = self.pattern_var.get().strip()
        if not name or not pattern:
            Messagebox.show_error("Name and pattern are required.", "Error")
            return
        try:
            re.compile(pattern)
        except re.error as e:
            Messagebox.show_error(f"Invalid regex: {e}", "Error")
            return
        profile = self.profile_var.get()
        if profile == "(none)":
            profile = None
        self.result = {
            "name": name,
            "pattern": pattern,
            "browser": self.browser_var.get(),
            "profile": profile,
        }
        if self.confirm_var.get():
            self.result["confirm"] = True
        self.top.destroy()
