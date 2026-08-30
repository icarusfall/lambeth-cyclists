"""Shared setup for the helper scripts in this directory.

Import it first, before any project import:

    import _bootstrap  # noqa: F401

It does two things:

1. Puts the repo root on sys.path, so `python scripts/check_gmail.py` can
   import config/, services/ and models/.
2. Forces UTF-8 on stdout/stderr. Windows consoles default to cp1252, which
   cannot encode the check/cross marks these scripts print — without this they
   die with UnicodeEncodeError instead of reporting their result.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):  # not a reconfigurable stream (piped/redirected)
        pass
