#!/usr/bin/env python3
"""Entry point for Switchyard."""

import sys
import os

# Add project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from switchyard.main import main

main()
