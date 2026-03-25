#!/usr/bin/env python3
"""HTML Dispatch - URL dispatcher for Linux."""

import argparse
import sys

from .dispatcher import dispatch
from .gui import DispatcherApp


def main():
    parser = argparse.ArgumentParser(description="HTML Dispatch - URL router for Linux")
    parser.add_argument("url", nargs="?", help="URL to dispatch")
    parser.add_argument(
        "--manage", action="store_true", help="Open manager GUI (history, rules, settings)"
    )
    args = parser.parse_args()

    if args.manage or not args.url:
        # Open the GUI manager
        app = DispatcherApp(url=args.url)
        app.run()
        return

    url = args.url

    # Try automatic dispatch
    if dispatch(url):
        return

    # No rule matched and popup is enabled - show GUI
    app = DispatcherApp(url=url)
    app.run()


if __name__ == "__main__":
    main()
