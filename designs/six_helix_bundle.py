"""The reference strut: six helices, honeycomb, no twist correction needed.

uv run python designs/six_helix_bundle.py [output_dir]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from dobladilo import _scadnano as ad
from dobladilo.parts.bundle import six_helix_bundle

NAME = "six_helix_bundle"


def main(directory: Path) -> int:
    part = six_helix_bundle()
    written = ad.write_all(part.design, directory=directory, name=NAME)
    summary = part.as_dict() | {"files": {k: str(v) for k, v in written.items()}}
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("build") / NAME
    raise SystemExit(main(out))
