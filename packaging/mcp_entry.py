from __future__ import annotations

import multiprocessing
import os


def main() -> None:
    os.environ.setdefault("SOFTAUTO_ALLOW_ACTIONS", "1")
    from softauto.server import mcp

    mcp.run("stdio")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
