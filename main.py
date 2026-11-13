"""Compatibility entry point. Prefer `python -m beammpy serve`."""
import sys
from beammpy import create_app
from beammpy.cli import main

if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.append("serve")
    main()
