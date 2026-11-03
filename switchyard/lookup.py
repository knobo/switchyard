"""Look up page title, favicon and visiting profiles in local browser history.

Reads each profile's own SQLite files (Firefox places/favicons, Chrome
History/Favicons) read-only. Nothing goes over the network, so one-time links
are never consumed and logged-in pages keep their real titles.
"""

import sqlite3
from contextlib import closing
from pathlib import Path
from urllib.parse import urlparse

from .browsers import CHROME_DIRS, get_chrome_profiles, get_firefox_profile_path, get_firefox_profiles

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
END = "￿"  # upper bound for prefix range queries


def _open(path):
    # immutable=1 reads without taking locks, so a running browser is no problem.
    # It skips the -wal file, so the last few minutes of history may be missing.
    return closing(sqlite3.connect(f"file:{path}?immutable=1", uri=True))


def _prefix(url):
    """scheme://host/first-segment, the same grouping as domain history."""
    p = urlparse(url)
    first = p.path.strip("/").split("/")[0]
    return f"{p.scheme}://{p.netloc}/{first}"


def _firefox(profile_dir, url, prefix, origin):
    title, visits, icons = None, 0, []
    rev_host = (urlparse(url).hostname or "")[::-1] + "."
    with _open(profile_dir / "places.sqlite") as db:
        row = db.execute(
            "select title from moz_places where rev_host = ? and url = ?", (rev_host, url)
        ).fetchone()
        title = row and row[0]
        visits = db.execute(
            "select coalesce(sum(visit_count), 0) from moz_places"
            " where rev_host = ? and url >= ? and url < ?",
            (rev_host, prefix, prefix + END),
        ).fetchone()[0]
    with _open(profile_dir / "favicons.sqlite") as db:
        query = (
            "select i.width, i.data from moz_pages_w_icons p"
            " join moz_icons_to_pages ip on ip.page_id = p.id"
            " join moz_icons i on i.id = ip.icon_id where "
        )
        icons = db.execute(query + "p.page_url = ?", (url,)).fetchall()
        if not icons:
            icons = db.execute(
                query + "p.page_url >= ? and p.page_url < ?", (origin, origin + END)
            ).fetchall()
    return title, visits, icons


def _chrome(profile_dir, url, prefix, origin):
    title, visits, icons = None, 0, []
    with _open(profile_dir / "History") as db:
        row = db.execute("select title from urls where url = ?", (url,)).fetchone()
        title = row and row[0]
        visits = db.execute(
            "select coalesce(sum(visit_count), 0) from urls where url >= ? and url < ?",
            (prefix, prefix + END),
        ).fetchone()[0]
    with _open(profile_dir / "Favicons") as db:
        query = (
            "select b.width, b.image_data from icon_mapping m"
            " join favicon_bitmaps b on b.icon_id = m.icon_id where "
        )
        icons = db.execute(query + "m.page_url = ?", (url,)).fetchall()
        if not icons:
            icons = db.execute(
                query + "m.page_url >= ? and m.page_url < ?", (origin, origin + END)
            ).fetchall()
    return title, visits, icons


def _profile_dirs():
    for name in get_firefox_profiles():
        path = get_firefox_profile_path(name)
        if path:
            yield "firefox", name, Path(path), _firefox
    for name in get_chrome_profiles():
        for chrome_dir in CHROME_DIRS:
            if (chrome_dir / name).is_dir():
                yield "chrome", name, chrome_dir / name, _chrome
                break


def lookup(url, icon_size=32):
    """Return {"title", "icon": (width, png bytes) | None, "visits": {(browser, profile): n}}."""
    result = {"title": None, "icon": None, "visits": {}}
    if urlparse(url).scheme not in ("http", "https"):
        return result
    prefix = _prefix(url)
    origin = "{0.scheme}://{0.netloc}/".format(urlparse(url))
    pngs = []
    for browser, profile, path, read in _profile_dirs():
        try:
            title, visits, icons = read(path, url, prefix, origin)
        except (sqlite3.Error, OSError):
            continue  # profile never used, or a schema we don't know
        result["title"] = result["title"] or title
        if visits:
            result["visits"][(browser, profile)] = visits
        pngs += [(w, d) for w, d in icons if d and d.startswith(PNG_MAGIC) and w]
    if pngs:
        # Smallest icon at least icon_size wide, else the largest there is
        big = [p for p in pngs if p[0] >= icon_size]
        result["icon"] = min(big) if big else max(pngs)
    return result


if __name__ == "__main__":
    import sys

    r = lookup(sys.argv[1] if len(sys.argv) > 1 else "https://github.com/myorg")
    print(r["title"], r["icon"] and r["icon"][0], r["visits"])
