"""Dependency policy: open source, EUPL-1.2 compatible, no network services.

dobladillo is EUPL-1.2 (LICENSE). Every dependency must be under an OSI licence
that can be combined with it. EUPL-1.2's compatibility appendix lists GPL v2
and v3, AGPL v3, LGPL, MPL 2, EPL 1.0, OSL, CeCILL and others, and permissive
licences combine with anything. A combined distribution that bundles GPL-3.0
code goes out under GPL-3.0, which the EUPL's compatibility clause permits.

The table below is curated, not scraped. Package metadata is inconsistent
enough -- scipy declares a copyright line, matplotlib a PSF variant -- that an
automatic check would either wave everything through or fail on noise. So a
person reviews each licence once, records it here with where it was checked,
and this test fails the moment a dependency appears that nobody reviewed.

Why it matters beyond hygiene: several tools this project first recommended
turned out to be non-commercial (NUPACK, SNUPI), commercial underneath
(CanDo runs on Abaqus), or unlicensed (NADOC). Each was caught by reading the
licence rather than the paper.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

#: SPDX identifiers that may be combined with EUPL-1.2.
ALLOWED = {
    # permissive
    "MIT",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "0BSD",
    "ISC",
    "Apache-2.0",
    "Zlib",
    "CC0-1.0",
    "PSF-2.0",
    "Matplotlib",
    # copyleft, listed in EUPL-1.2's compatibility appendix
    "GPL-2.0-or-later",
    "GPL-3.0-only",
    "GPL-3.0-or-later",
    "LGPL-2.1-or-later",
    "LGPL-3.0-only",
    "LGPL-3.0-or-later",
    "AGPL-3.0-only",
    "MPL-2.0",
    "EUPL-1.2",
}

#: Every dependency declared in pyproject.toml, with its reviewed licence.
#: Add a line here -- after reading the actual LICENSE file -- before adding a
#: dependency.
REVIEWED = {
    "typer": "MIT",
    "pyyaml": "MIT",
    "numpy": "BSD-3-Clause",
    "matplotlib": "Matplotlib",  # PSF-based, BSD-compatible
    "scadnano": "MIT",
    # primer3-py: its pyproject says GPL-2.0-or-later, and its C headers "or any later version";
    # the repo's LICENSE (libnano/primer3-py) is the GPL-2.0 text. A core dependency since it
    # became the source of the duplex thermodynamics: GPL-2.0-or-later is on EUPL-1.2's list.
    "primer3-py": "GPL-2.0-or-later",
    "scipy": "BSD-3-Clause",
    "pytest": "MIT",
    "ruff": "MIT",
    "mypy": "MIT",
}

#: Reviewed and rejected, so nobody re-proposes them without re-reading this.
REJECTED = {
    "nupack": "non-commercial academic licence; not open source",
    "snupi": "distributed as a binary in a paper supplement, non-commercial",
    "cando": "a web service, running on commercial Abaqus",
    "nadoc": "public code with no licence file: all rights reserved",
}

#: Imports that mean the code talks to a network. The toolchain runs on
#: hardware we control and never calls out; `gh` in the scripts directory is
#: the operator's tool, not the package's.
NETWORK_IMPORTS = re.compile(
    r"^\s*(import|from)\s+(requests|httpx|aiohttp|urllib3|urllib\.request|http\.client|socket|ftplib|smtplib)\b",
    re.MULTILINE,
)


def _declared() -> set[str]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    specs = list(project.get("dependencies", []))
    for extra in project.get("optional-dependencies", {}).values():
        specs.extend(extra)
    return {re.split(r"[<>=!~\[; ]", spec)[0].lower() for spec in specs}


def test_dobladillo_is_eupl() -> None:
    assert (ROOT / "LICENSE").read_text().startswith("EUROPEAN UNION PUBLIC LICENCE v. 1.2")
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert project["license"]["text"] == "EUPL-1.2"


def test_every_dependency_has_been_reviewed() -> None:
    unreviewed = _declared() - set(REVIEWED)
    assert not unreviewed, (
        f"dependencies nobody has reviewed the licence of: {sorted(unreviewed)}. "
        "Read the actual LICENSE file and add them to REVIEWED."
    )


@pytest.mark.parametrize(("package", "licence"), sorted(REVIEWED.items()))
def test_every_reviewed_licence_is_compatible(package: str, licence: str) -> None:
    assert licence in ALLOWED, f"{package} is {licence}, which is not EUPL-1.2 compatible"


def test_no_rejected_tool_is_a_dependency() -> None:
    assert not (_declared() & set(REJECTED))


def test_the_package_never_talks_to_a_network() -> None:
    offenders = [
        str(path.relative_to(ROOT))
        for path in (ROOT / "dobladillo").rglob("*.py")
        if NETWORK_IMPORTS.search(path.read_text())
    ]
    assert not offenders, f"network access in: {offenders}"
