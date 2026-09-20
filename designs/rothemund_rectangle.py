"""The reference rectangle: 22 helices, square lattice, twist-corrected.

One script per design, deterministic, per DESIGN.md section 6. Run it and the
same files come out every time; nothing here is hand-edited afterwards.

    uv run python designs/rothemund_rectangle.py [output_dir]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from dobladilo import _scadnano as ad
from dobladilo.parts.rectangle import rothemund_rectangle

NAME = "rothemund_rectangle"


def main(directory: Path) -> int:
    part = rothemund_rectangle(twist_corrected=True)
    written = ad.write_all(part.design, directory=directory, name=NAME)
    summary = part.as_dict() | {"files": {k: str(v) for k, v in written.items()}}
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("build") / NAME
    raise SystemExit(main(out))
