#!/usr/bin/env python3
"""Convenience launcher: ``python run.py`` == ``python -m pyflipper``."""
import sys

from pyflipper.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
