import base64
import re
import tkinter as tk
from pathlib import Path
from urllib.parse import urlparse

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox

from .browsers import (
    get_available_browsers,
    get_chrome_profile_names,
    get_chrome_profiles,
    get_claude_profiles,
    get_firefox_profiles,
)
from .config import load_config, save_config
from .dispatcher import open_url, resolve_destination
from .lookup import lookup
from .history import get_unique_destinations, load_history
from .themes import register_themes, theme_mode, themes_by_mode


COLORS = ["primary", "secondary", "success", "info", "warning", "danger", "light"]
DEFAULT_BROWSER_COLORS = {"firefox": "warning", "chrome": "info"}
BROWSER_ICONS = {
    "firefox": ["firefox"],
    "chrome": ["google-chrome", "chromium", "chromium-browser"],
}


def find_browser_icon(browser, size=32):
    """Return the path of the browser's PNG icon from the hicolor theme, or None."""
    dirs = [Path.home() / ".local/share/icons/hicolor", Path("/usr/share/icons/hicolor")]
    for name in BROWSER_ICONS.get(browser, [browser]):
        for d in dirs:
            path = d / f"{size}x{size}/apps/{name}.png"
            if path.exists():
                return path
    return None


def suggest_pattern(url):
    """Suggest a rule regex from the URL's host and first path segment."""
    parsed = urlparse(url)
    # http and https are interchangeable; any other scheme is matched as-is
    scheme = "https?" if parsed.scheme in ("http", "https") else re.escape(parsed.scheme)
    base = rf"{scheme}://{re.escape(parsed.netloc)}"
    first = parsed.path.strip("/").split("/")[0]
    return f"{base}/{re.escape(first)}" if first else base


ICON_RELATIVE_PATH = "hicolor/128x128/apps/switchyard.png"
ICON_SEARCH_DIRS = [
    Path.home() / ".local/share/icons",
    Path(__file__).resolve().parent.parent / "icons",
]


def set_window_icon(window):
    """Give the window our own icon in the taskbar and alt-tab switcher."""
    for base in ICON_SEARCH_DIRS:
        icon = base / ICON_RELATIVE_PATH
        if icon.exists():
            try:
                window._icon_image = tk.PhotoImage(file=str(icon))
                window.iconphoto(True, window._icon_image)
            except tk.TclError:
                pass
            return


def profiles_for_browser(browser):
    """Profile choices for a browser. Claude always names one, so it gets no "(none)"."""
    if browser == "claude":
        return get_claude_profiles()
    if browser == "firefox":
        profiles = get_firefox_profiles()
    elif browser == "chrome":
        profiles = get_chrome_profiles()
    else:
        profiles = []
    return ["(none)"] + profiles


class DispatcherApp:
    def __init__(self, url=None):
        self.url = url
        self.config = load_config()

        self.root = ttk.Window(
            title="Switchyard",
            themename="darkly",
            resizable=(True, True),
        )
        register_themes(self.root.style)
        try:
            self.root.style.theme_use(self.config.get("theme", "darkly"))
        except tk.TclError:
            pass  # theme from config no longer exists; keep darkly
        set_window_icon(self.root)

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

        self._fit_window()
        self.root.place_window_center()

        if url:
            self.notebook.select(0)
        else:
            self.notebook.select(1)

        # Keybindings
        self.root.bind("<Control-Return>", self._do_dispatch)
        self.root.bind("<Return>", self._do_dispatch)
        self.root.bind("<Left>", lambda e: self._on_key_side(-1))
        self.root.bind("<Right>", lambda e: self._on_key_side(1))
        self.root.bind("<Key>", self._on_digit)
        self.root.bind("<Control-space>", self._auto_dispatch)
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.root.bind("<Up>", self._on_key_up)
        self.root.bind("<Down>", self._on_key_down)

    def _fit_window(self):
        """Never let the window get smaller than what its widgets need."""
        self.root.update_idletasks()
        w, h = self.root.winfo_reqwidth(), self.root.winfo_reqheight()
        self.root.minsize(w, h)
        self.root.geometry(
            f"{max(w, self.root.winfo_width())}x{max(h, self.root.winfo_height())}"
        )

    def run(self):
        self.root.mainloop()

    # ── Dispatch tab ──────────────────────────────────────────────

    def _build_dispatch_tab(self):
        frame = self.dispatch_frame
        pad = 16

        # Page identity from local browser history: favicon and title
        self.page_row = ttk.Frame(frame)
        self.page_icon_label = ttk.Label(self.page_row)
        self.page_icon_label.pack(side=LEFT, padx=(0, 10))
        self.page_title_var = tk.StringVar()
        ttk.Label(
            self.page_row, textvariable=self.page_title_var, font=("", 13, "bold")
        ).pack(side=LEFT, fill=X)

        self.url_var = tk.StringVar(value=self.url or "")
        self.url_entry = ttk.Entry(frame, textvariable=self.url_var, font=("", 11))
        self.url_entry.pack(fill=X, padx=pad, pady=(pad, 6))

        # Where the suggestion came from (rule, history, default)
        self.source_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.source_var, bootstyle=INFO).pack(
            anchor=W, padx=pad
        )

        # Footer first, so it stays at the bottom when the window grows
        footer = ttk.Frame(frame)
        footer.pack(side=BOTTOM, fill=X, padx=pad, pady=pad)
        ttk.Button(
            footer, text="Cancel", bootstyle=SECONDARY, command=self.root.destroy
        ).pack(side=RIGHT)
        ttk.Button(
            footer, text="Auto", bootstyle="info-outline", command=self._auto_dispatch
        ).pack(side=RIGHT, padx=8)
        ttk.Label(
            footer,
            text="Enter open  ·  1–9 pick  ·  Left/Right move  ·  Up/Down history"
            "  ·  Ctrl+Space auto  ·  Esc cancel",
            font=("", 9),
        ).pack(side=LEFT)

        ttk.Label(frame, text="Open with", font=("", 12, "bold")).pack(
            anchor=W, padx=pad, pady=(22, 8)
        )
        self.options_frame = ttk.Frame(frame)
        self.options_frame.pack(fill=X, padx=pad)

        rule_row = ttk.Frame(frame)
        rule_row.pack(fill=X, padx=pad, pady=(22, 0))
        self.save_rule_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            rule_row,
            text="Save as rule for",
            variable=self.save_rule_var,
            command=self._on_save_rule_toggle,
        ).pack(side=LEFT)
        self.rule_pattern_var = tk.StringVar()
        self.rule_pattern_entry = ttk.Entry(rule_row, textvariable=self.rule_pattern_var)
        # Editing the pattern means you want the rule
        self.rule_pattern_entry.bind(
            "<KeyRelease>",
            lambda e: e.char and self.save_rule_var.set(True),
        )
        self.rule_pattern_entry.pack(side=LEFT, fill=X, expand=True, padx=(8, 0))

        self._chrome_names = get_chrome_profile_names()
        self._lookup = {"title": None, "icon": None, "visits": {}}
        self._options = []  # [(browser, profile)], in button order
        self._option_buttons = []
        self._selected = 0
        self._suggested = None

        # History destinations for Up/Down
        self._destinations = get_unique_destinations()
        self._dest_index = -1  # -1 means "resolved suggestion", not from list
        self._prefill_destination()

    def _scale(self):
        """Display scale factor; tk scaling is 1.33 at 96 dpi."""
        return float(self.root.tk.call("tk", "scaling")) / (96 / 72)

    def _favicon(self, size):
        """The looked-up favicon as a PhotoImage about size px wide, or None."""
        icon = self._lookup["icon"]
        if not icon:
            return None
        width, data = icon
        try:
            image = tk.PhotoImage(data=base64.b64encode(data))
        except tk.TclError:
            return None
        factor = max(1, round(width / size))
        return image.subsample(factor) if factor > 1 else image

    def _show_page_identity(self, url):
        icon = self._favicon(int(32 * self._scale()))
        title = self._lookup["title"]
        if not (icon or title):
            self.page_row.pack_forget()
            return
        self._page_icon = icon  # keep a reference
        self.page_icon_label.configure(image=icon or "")
        self.page_title_var.set(title or urlparse(url).hostname or url)
        self.page_row.pack(fill=X, padx=16, pady=(16, 0), before=self.url_entry)

    def _profile_label(self, browser, profile):
        if not profile:
            return "Browser default"
        if browser == "chrome":
            return self._chrome_names.get(profile, profile)
        return profile

    def _browser_color(self, browser):
        colors = {**DEFAULT_BROWSER_COLORS, **(self.config.get("browser_colors") or {})}
        return colors.get(browser, "secondary")

    def _build_options(self, extra=()):
        """Lay out one group per browser: icon and name, then its profile buttons."""
        for child in self.options_frame.winfo_children():
            child.destroy()
        self._options = []
        self._option_buttons = []
        self._icons = []  # keep PhotoImage references alive
        per_row = 4

        # Profiles with at least 10% of this site's visits get the favicon
        visits = self._lookup["visits"]
        total = sum(visits.values())
        regulars = {d for d, n in visits.items() if total and n / total >= 0.1}
        mark = self._favicon(int(16 * self._scale())) if regulars else None
        if regulars and not mark:
            mark = self._dot()
        self._icons.append(mark)

        browsers = list(get_available_browsers())
        for browser, _ in extra:
            if browser not in browsers:
                browsers.append(browser)

        for n, browser in enumerate(browsers):
            if browser == "claude":
                profiles = get_claude_profiles()
            elif browser == "firefox":
                profiles = get_firefox_profiles()
            elif browser == "chrome":
                profiles = get_chrome_profiles()
            else:
                profiles = []
            profiles += [p for b, p in extra if b == browser and p and p not in profiles]
            if browser != "claude":  # Claude always names a profile
                profiles.append(None)
            color = self._browser_color(browser)

            if n:
                ttk.Separator(self.options_frame).pack(fill=X, pady=10)
            group = ttk.Frame(self.options_frame)
            group.pack(fill=X)

            # Browser identity column: icon above the name, in the browser's color
            # Icon follows display scaling (tk scaling is 1.33 at 96 dpi)
            scale = self._scale()
            head = ttk.Frame(group)
            head.pack(side=LEFT, anchor=N, padx=(0, 14))
            ttk.Frame(head, width=int(96 * scale), height=0).pack()  # minimum column width
            size = min((32, 48, 64), key=lambda px: abs(px - 32 * scale))
            icon_path = find_browser_icon(browser, size) or find_browser_icon(browser)
            if icon_path:
                icon = tk.PhotoImage(file=str(icon_path))
                self._icons.append(icon)
                ttk.Label(head, image=icon).pack(pady=(4, 2))
            ttk.Label(
                head, text=browser.capitalize(), font=("", 11, "bold"), bootstyle=color
            ).pack()

            grid = ttk.Frame(group)
            grid.pack(side=LEFT, fill=X, expand=True)
            for col in range(per_row):
                grid.columnconfigure(col, weight=1, uniform="option")
            for i, profile in enumerate(profiles):
                index = len(self._options)
                text = self._profile_label(browser, profile)
                if index < 9:
                    text = f"{index + 1}  {text}"
                btn = ttk.Button(
                    grid, text=text, command=lambda n=index: self._open_option(n)
                )
                if (browser, profile) in regulars:
                    btn.configure(image=mark, compound=LEFT, text=f" {text}")
                btn.grid(row=i // per_row, column=i % per_row, sticky=EW, padx=3, pady=3)
                self._options.append((browser, profile))
                self._option_buttons.append(btn)

    def _dot(self):
        """Small filled circle in the text color, for sites without a favicon."""
        d = max(6, int(8 * self._scale()))
        image = tk.PhotoImage(width=d, height=d)
        color = self.root.style.colors.fg
        r = d / 2
        for y in range(d):
            for x in range(d):
                if (x + 0.5 - r) ** 2 + (y + 0.5 - r) ** 2 <= r * r:
                    image.put(color, (x, y))
        return image

    def _select(self, index):
        if not self._options:
            return
        self._selected = index % len(self._options)
        for i, btn in enumerate(self._option_buttons):
            color = self._browser_color(self._options[i][0])
            btn.configure(bootstyle=color if i == self._selected else f"{color}-outline")
        self._option_buttons[self._selected].focus_set()

    def _set_destination(self, browser, profile):
        """Select the button for browser/profile, adding one if it is missing."""
        if not browser:
            return
        dest = (browser, profile or None)
        if dest not in self._options:
            self._build_options(extra=[dest])
        self._select(self._options.index(dest))

    def _prefill_destination(self):
        """Pre-select browser/profile using the resolve fallback chain."""
        url = self.url_var.get().strip()
        self.rule_pattern_var.set(suggest_pattern(url) if url else "")
        self._lookup = {"title": None, "icon": None, "visits": {}}
        if url and self.config.get("history_lookup", True):
            self._lookup = lookup(url, int(32 * self._scale()))
        self._show_page_identity(url)
        self._build_options()
        if not url:
            self.source_var.set("")
            self._suggested = None
            self._select(0)
            return
        browser, profile, source = resolve_destination(url)
        self._suggested = (browser, profile or None)
        self._set_destination(browser, profile)
        self.source_var.set(
            f"Suggested: {browser.capitalize()} · {self._profile_label(browser, profile)}"
            f"   ({source})"
        )
        self._dest_index = -1

    def _on_dispatch_tab(self):
        return self.notebook.select() == str(self.dispatch_frame)

    def _typing(self):
        return isinstance(self.root.focus_get(), (tk.Entry, ttk.Entry))

    def _on_key_up(self, event=None):
        """Navigate to previous destination in history."""
        if not self._on_dispatch_tab() or not self._destinations:
            return
        if self._dest_index < len(self._destinations) - 1:
            self._dest_index += 1
        self._apply_dest_from_list()

    def _on_key_down(self, event=None):
        """Navigate to next destination in history."""
        if not self._on_dispatch_tab():
            return
        if self._dest_index > 0:
            self._dest_index -= 1
            self._apply_dest_from_list()
        elif self._dest_index == 0:
            # Go back to resolved suggestion
            self._dest_index = -1
            self._prefill_destination()

    def _on_key_side(self, step):
        if self._on_dispatch_tab() and not self._typing():
            self._select(self._selected + step)
            return "break"

    def _on_digit(self, event):
        if self._on_dispatch_tab() and not self._typing() and len(event.char) == 1 and event.char in "123456789":
            index = int(event.char) - 1
            if index < len(self._options):
                self._open_option(index)

    def _apply_dest_from_list(self):
        """Apply the destination at current _dest_index."""
        if self._dest_index < 0 or self._dest_index >= len(self._destinations):
            return
        browser, profile = self._destinations[self._dest_index]
        self._set_destination(browser, profile)
        pos = self._dest_index + 1
        total = len(self._destinations)
        self.source_var.set(f"History ({pos}/{total})")

    def _on_save_rule_toggle(self):
        if self.save_rule_var.get():
            self.rule_pattern_entry.focus_set()
            self.rule_pattern_entry.icursor(END)
        else:
            self._select(self._selected)

    def _auto_dispatch(self, event=None):
        """Dispatch URL using the resolve fallback chain."""
        if not self._on_dispatch_tab():
            return
        url = self.url_var.get().strip()
        if not url:
            return
        browser, profile, source = resolve_destination(url)
        open_url(url, browser, profile, source)
        self.root.destroy()

    def _do_dispatch(self, event=None):
        if self._on_dispatch_tab():
            self._open_option(self._selected)

    def _open_option(self, index):
        url = self.url_var.get().strip()
        if not url or not self._options:
            return
        browser, profile = self._options[index]
        source = "manual"
        if self.save_rule_var.get():
            pattern = self.rule_pattern_var.get().strip()
            try:
                re.compile(pattern)
            except re.error as e:
                Messagebox.show_error(f"Invalid regex: {e}", "Error")
                return
            if not pattern:
                Messagebox.show_error("Enter a URL pattern for the rule.", "Error")
                return
            source = urlparse(url).netloc or pattern
            self.config["rules"].append(
                {"name": source, "pattern": pattern, "browser": browser, "profile": profile}
            )
            save_config(self.config)
        open_url(url, browser, profile, source)
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

        look = ttk.Frame(frame)
        look.pack(fill=X, padx=10, pady=(15, 5))
        current = self.root.style.theme.name
        ttk.Label(look, text="Mode:").grid(row=0, column=0, sticky=W, pady=3)
        self.mode_var = tk.StringVar(value=theme_mode(current))
        modes = ttk.Frame(look)
        modes.grid(row=0, column=1, sticky=W, padx=10, pady=3)
        for mode in ("dark", "light"):
            ttk.Radiobutton(
                modes,
                text=mode.capitalize(),
                value=mode,
                variable=self.mode_var,
                command=self._on_mode_change,
            ).pack(side=LEFT, padx=(0, 16))

        ttk.Label(look, text="Theme:").grid(row=0, column=2, sticky=W, padx=(20, 0), pady=3)
        self.theme_var = tk.StringVar(value=current)
        self.theme_combo = ttk.Combobox(
            look,
            textvariable=self.theme_var,
            values=themes_by_mode(self.mode_var.get()),
            state="readonly",
        )
        self.theme_combo.grid(row=0, column=3, sticky=W, padx=10, pady=3)
        self.theme_combo.bind("<<ComboboxSelected>>", self._on_theme_change)

        self.browser_color_vars = {}
        for row, browser in enumerate(get_available_browsers(), start=1):
            ttk.Label(look, text=f"{browser.capitalize()} color:").grid(
                row=row, column=0, sticky=W, pady=3
            )
            var = tk.StringVar(value=self._browser_color(browser))
            combo = ttk.Combobox(look, textvariable=var, values=COLORS, state="readonly")
            combo.grid(row=row, column=1, sticky=W, padx=10, pady=3)
            combo.bind("<<ComboboxSelected>>", self._on_browser_color_change)
            self.browser_color_vars[browser] = var

        ttk.Separator(frame).pack(fill=X, padx=10, pady=10)

        self.history_lookup_var = tk.BooleanVar(value=self.config.get("history_lookup", True))
        ttk.Checkbutton(
            frame,
            text="Show page title and icon from local browser history (no network)",
            variable=self.history_lookup_var,
            bootstyle="round-toggle",
            command=self._on_history_lookup_toggle,
        ).pack(anchor=W, padx=10, pady=(5, 5))

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

    def _on_mode_change(self):
        names = themes_by_mode(self.mode_var.get())
        self.theme_combo.configure(values=names)
        if self.theme_var.get() not in names:
            self.theme_var.set("darkly" if self.mode_var.get() == "dark" else "flatly")
            self._on_theme_change()

    def _on_theme_change(self, event=None):
        self.root.style.theme_use(self.theme_var.get())
        self.config["theme"] = self.theme_var.get()
        save_config(self.config)

    def _on_browser_color_change(self, event=None):
        self.config["browser_colors"] = {b: v.get() for b, v in self.browser_color_vars.items()}
        save_config(self.config)
        selected = self._selected
        self._build_options(extra=[self._options[selected]] if self._options else ())
        self._select(selected)
        self._fit_window()

    def _check_default_browser(self):
        import subprocess
        try:
            result = subprocess.run(
                ["xdg-settings", "get", "default-web-browser"],
                capture_output=True, text=True, timeout=5,
            )
            current = result.stdout.strip()
            if current == "switchyard.desktop":
                self.default_status_var.set("switchyard is the default browser")
            else:
                self.default_status_var.set(f"Default browser: {current}")
        except Exception:
            self.default_status_var.set("Could not detect default browser")

    def _set_as_default(self):
        import subprocess
        for cmd in [
            ["xdg-settings", "set", "default-web-browser", "switchyard.desktop"],
            ["xdg-mime", "default", "switchyard.desktop", "x-scheme-handler/http"],
            ["xdg-mime", "default", "switchyard.desktop", "x-scheme-handler/https"],
        ]:
            subprocess.run(cmd, capture_output=True, timeout=5)
        self._check_default_browser()

    def _on_history_lookup_toggle(self):
        self.config["history_lookup"] = self.history_lookup_var.get()
        save_config(self.config)
        self._prefill_destination()
        self._fit_window()

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
            default_pattern = suggest_pattern(url)
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
        profiles = profiles_for_browser(self.browser_var.get())
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
