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
    # AFMReader: its COPYING is the GPL v3 text, its CITATION.cff says
    # GPL-3.0-or-later, and its PyPI classifier says LGPLv3. The most
    # restrictive reading is recorded. What it pulls in was read too: pySPM
    # Apache-2.0, igor2 LGPL-3.0-or-later, tifffile and h5py BSD-3-Clause,
    # loguru and ruamel.yaml MIT. Matters the day anything is distributed.
    "afmreader": "GPL-3.0-only",
    # oxDNA-analysis-tools: the oxDNA repository's LICENSE (lorenzo-rovigatti/oxDNA) is the
    # GPL-3.0 text, and nothing in the analysis package grants "or later", so it is recorded as
    # 3.0-only. Its wheel ships no licence file. What it pulls in transitively was read too:
    # scikit-learn, joblib, threadpoolctl, cloudpickle BSD-3-Clause; narwhals MIT.
    "oxdna-analysis-tools": "GPL-3.0-only",
    # scikit-image 0.26.0: its LICENSE.txt (installed dist-info) is a Debian-style file whose
    # default stanza (Files: *) is BSD-3-Clause; the exceptions it lists are BSD-3-Clause,
    # BSD-2-Clause and MIT, all permissive. Used for skeletonize (Zhang-Suen thinning), whose
    # file is listed under BSD-3-Clause. What it pulls in: imageio BSD-2-Clause, lazy-loader
    # BSD-3-Clause, networkx BSD-3-Clause, pillow MIT-CMU, tifffile BSD-3-Clause, all
    # permissive (read from their metadata, not their LICENSE files). Reviewed 2026-09-28.
    "scikit-image": "BSD-3-Clause",
    "pytest": "MIT",
    "ruff": "MIT",
    "mypy": "MIT",
    # hypothesis (dev only, property-based tests): its wheel's LICENSE.txt, read 2026-09-29,
    # is the MPL-2.0 text ("All code in this repository ... is released under the Mozilla
    # Public License v 2.0"); MPL 2 is on EUPL-1.2's list. Its one dependency on Python
    # >= 3.11, sortedcontainers, ships the Apache-2.0 text.
    "hypothesis": "MPL-2.0",
    # The official MCP Python SDK, modelcontextprotocol/python-sdk. Used over
    # stdio only; the package itself still opens no connection.
    "mcp": "MIT",
    # The `web` extra (the local web UI, `dobladillo web`). Each licence file read in the
    # installed dist-info on 2026-09-29, to its last clause:
    # starlette 1.7.0 licenses/LICENSE.md: BSD 3-clause text (Encode OSS Ltd).
    "starlette": "BSD-3-Clause",
    # uvicorn 0.54.0 licenses/LICENSE.md: BSD 3-clause text (Encode OSS Ltd). Pulls in click
    # (LICENSE.txt, BSD-3-Clause, Pallets) and h11 (LICENSE.txt, MIT).
    "uvicorn": "BSD-3-Clause",
    # jinja2 3.1.6 licenses/LICENSE.txt: BSD 3-clause text (Pallets). Pulls in MarkupSafe
    # 3.0.3, whose LICENSE.txt is the same BSD 3-clause text.
    "jinja2": "BSD-3-Clause",
    # python-multipart 0.0.32 licenses/LICENSE.txt: the Apache License 2.0 text.
    "python-multipart": "Apache-2.0",
    # markdown-it-py 4.2.0: LICENSE is the MIT text (ExecutableBookProject); LICENSE.markdown-it,
    # for the JavaScript original it ports, is MIT too. Pulls in mdurl 0.1.2, LICENSE MIT.
    "markdown-it-py": "MIT",
    # httpx2 2.13.1 (dev only: Starlette's TestClient drives the web tests through it):
    # licenses/LICENSE.md is BSD 3-clause text. Pulls in httpcore2 (LICENSE.md BSD-3-Clause),
    # idna (LICENSE.md BSD-3-Clause), truststore (LICENSE MIT) and anyio (LICENSE MIT).
    "httpx2": "BSD-3-Clause",
}

#: Reviewed and rejected, so nobody re-proposes them without re-reading this.
REJECTED = {
    "nupack": "non-commercial academic licence; not open source",
    "snupi": "distributed as a binary in a paper supplement, non-commercial",
    "cando": "a web service, running on commercial Abaqus",
    "nadoc": "public code with no licence file: all rights reserved",
    # Checked 2026-09-28 for #8, at TopoStats 2.4.2 and main (41cfcc5). Every
    # release since 2.3.0 requires topoly, and `topostats.grains` imports keras
    # and TensorFlow at module level, so grain finding cannot be had without
    # them. Also requires-python < 3.12. Re-check if topoly becomes optional.
    "topostats": "hard-requires topoly (no source) and TensorFlow; Python < 3.12",
    # topoly 1.1.0: binary wheels only, no sdist in any release and no public
    # source repository (github.com/ilbsm has a tutorial, not the code). Its
    # PyPI classifier says "Free for non-commercial use"; its documentation's
    # licence page is BSD-3-Clause text. Without source it is not open source
    # under the OSD whichever text is meant, and the two texts disagree.
    "topoly": "binary-only; PyPI says non-commercial, its docs say BSD-3-Clause",
}

#: Imports that mean the code talks to a network. The toolchain runs on
#: hardware we control and never calls out; `gh` in the scripts directory is
#: the operator's tool, not the package's. The one listener is `dobladillo web`
#: (uvicorn, 127.0.0.1 unless `--host` says otherwise, and then behind a token);
#: it imports none of these except in `ADDRESS_LOOKUP`, which reads this
#: machine's own addresses to print its URLs and sends nothing.
NETWORK_IMPORTS = re.compile(
    r"^\s*(import|from)\s+(requests|httpx|aiohttp|urllib3|urllib\.request|http\.client|socket|ftplib|smtplib)\b",
    re.MULTILINE,
)


#: The one file allowed `socket`, and only `socket`: see its docstring.
ADDRESS_LOOKUP = "dobladillo/web/addresses.py"


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
        and str(path.relative_to(ROOT)) != ADDRESS_LOOKUP
    ]
    assert not offenders, f"network access in: {offenders}"
    imported = {m.group(2) for m in NETWORK_IMPORTS.finditer((ROOT / ADDRESS_LOOKUP).read_text())}
    assert imported == {"socket"}
