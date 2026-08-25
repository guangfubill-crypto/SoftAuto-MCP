from __future__ import annotations

import multiprocessing

from softauto.picker import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
