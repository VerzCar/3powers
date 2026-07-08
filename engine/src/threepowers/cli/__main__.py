"""``python -m threepowers.cli`` — delegate to the package entry point."""

import sys

from . import main

if __name__ == "__main__":
    sys.exit(main())
