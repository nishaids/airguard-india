"""Add the repository root to ``sys.path`` so functions here can import ``src``.

``config.PROJECT_ROOT`` is computed from ``src/config.py``'s own file location
(``Path(__file__).resolve().parents[1]``), so it resolves correctly wherever the
repository lands on Vercel's filesystem, as long as this file's position two
levels below the repository root (``webapp/api/``) is preserved -- which it is,
because the Vercel project's Root Directory is ``webapp`` with "Include files
outside the Root Directory" enabled, and that carries the whole repository
along untouched.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
