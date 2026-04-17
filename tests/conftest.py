from __future__ import annotations

import os


# Keep test runs deterministic and offline by default.
os.environ.setdefault("ENABLE_NVIDIA_MODEL", "0")
