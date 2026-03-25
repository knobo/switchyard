#!/usr/bin/env python3
"""Entry point for HTML Dispatch."""

import sys
import os

# Add project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from htmldispatch.main import main

main()
