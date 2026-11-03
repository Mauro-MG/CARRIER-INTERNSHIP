#!/usr/bin/env python
"""Django command-line utility for the ValidateSAP replacement."""
import os
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
LOCAL_DEPS = BASE_DIR / ".deps"
if LOCAL_DEPS.exists():
    sys.path.insert(0, str(LOCAL_DEPS))


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
