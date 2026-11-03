"""Extra dark themes on top of the ones ttkbootstrap ships.

Palettes follow the published colors of each scheme. Their accents are
pastel, where ttkbootstrap's default white button text is unreadable, so
text on filled accent widgets is picked by contrast (see _readable_foreground).
"""

from ttkbootstrap.constants import DARK, LIGHT
from ttkbootstrap.style import Colors, ThemeDefinition
from ttkbootstrap.themes.standard import STANDARD_THEMES


def _dark(bg, fg, surface, overlay, active, primary, secondary, success, info, warning, danger, light):
    return {
        "primary": primary,
        "secondary": secondary,
        "success": success,
        "info": info,
        "warning": warning,
        "danger": danger,
        "light": light,
        "dark": active,
        "bg": bg,
        "fg": fg,
        "selectbg": overlay,
        "selectfg": fg,
        "border": overlay,
        "inputfg": fg,
        "inputbg": surface,
        "active": active,
    }


EXTRA_DARK_THEMES = {
    "nord": _dark(
        "#2E3440", "#ECEFF4", "#3B4252", "#4C566A", "#272C36",
        "#88C0D0", "#4C566A", "#A3BE8C", "#81A1C1", "#EBCB8B", "#BF616A", "#D8DEE9",
    ),
    "dracula": _dark(
        "#282A36", "#F8F8F2", "#343746", "#44475A", "#21222C",
        "#BD93F9", "#6272A4", "#50FA7B", "#8BE9FD", "#FFB86C", "#FF5555", "#F8F8F2",
    ),
    "gruvbox": _dark(
        "#282828", "#EBDBB2", "#3C3836", "#504945", "#1D2021",
        "#83A598", "#665C54", "#B8BB26", "#8EC07C", "#FABD2F", "#FB4934", "#D5C4A1",
    ),
    "catppuccin": _dark(
        "#1E1E2E", "#CDD6F4", "#313244", "#45475A", "#181825",
        "#89B4FA", "#585B70", "#A6E3A1", "#89DCEB", "#F9E2AF", "#F38BA8", "#BAC2DE",
    ),
    "tokyonight": _dark(
        "#1A1B26", "#C0CAF5", "#24283B", "#414868", "#16161E",
        "#7AA2F7", "#414868", "#9ECE6A", "#7DCFFF", "#E0AF68", "#F7768E", "#A9B1D6",
    ),
}


_original_get_foreground = Colors.get_foreground


def _readable_foreground(self, color_label):
    """Text color for a filled accent: fg or bg, whichever contrasts more."""
    if color_label in (LIGHT, DARK):
        return _original_get_foreground(self, color_label)
    accent = self.get_luminance(self.get(color_label))
    return max(
        (self.fg, self.bg),
        key=lambda c: self.get_contrast_ration(accent, self.get_luminance(c)),
    )


def register_themes(style):
    # Patches a ttkbootstrap method; drop it if the library gains
    # contrast-aware button text itself.
    Colors.get_foreground = _readable_foreground
    for name, colors in EXTRA_DARK_THEMES.items():
        if name not in style.theme_names():
            style.register_theme(ThemeDefinition(name, colors, "dark"))


def themes_by_mode(mode):
    """Theme names for 'dark' or 'light', standard and extra, sorted."""
    names = [n for n, t in STANDARD_THEMES.items() if t["type"] == mode]
    if mode == "dark":
        names += list(EXTRA_DARK_THEMES)
    return sorted(names)


def theme_mode(name):
    if name in EXTRA_DARK_THEMES:
        return "dark"
    return STANDARD_THEMES.get(name, {}).get("type", "dark")
