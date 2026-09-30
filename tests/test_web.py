"""The local web UI: the whole lifecycle in a browser, and nothing the CLI would not do.

The full run is E1's, on a temporary git repository: a folder made from the
page, a gate, the lock, the instrument record, a synthetic scan uploaded,
`experiment report`, and the result shown beside the gate. Around it: every
POST needs the page's token, names outside the root are refused, and the
page changes the folder only through the commands.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("starlette")
pytest.importorskip("jinja2")
pytest.importorskip("markdown_it")
pytest.importorskip("httpx2")

from starlette.testclient import TestClient  # noqa: E402

from dobladillo.web import app as web  # noqa: E402

TOKEN = re.compile(r'name="csrf" value="([^"]+)"')


def _git(directory: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=directory, check=True, capture_output=True, text=True
    ).stdout


@pytest.fixture
def root(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "experiments").mkdir(parents=True)
    _git(repo, "init", "-q", ".")
    _git(repo, "config", "user.email", "bench@example.invalid")
    _git(repo, "config", "user.name", "Bench Person")
    return repo / "experiments"


def _client(root: Path, **kwargs: Any) -> TestClient:
    return TestClient(web.create_app(root, allowed_hosts=("testserver",), **kwargs))


def _token(client: TestClient) -> str:
    found = TOKEN.search(client.get("/new").text)
    assert found, "the page carries no CSRF token"
    return found.group(1)


def _tree(directory: Path) -> dict[str, str]:
    """Every file under `directory` (git's own excepted) and its content hash."""
    return {
        str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(directory.rglob("*"))
        if p.is_file() and ".git" not in p.relative_to(directory).parts
    }


def _changed(before: dict[str, str], after: dict[str, str]) -> set[str]:
    return {k for k in before.keys() | after.keys() if before.get(k) != after.get(k)}


def _synthetic_scan(path: Path) -> None:
    from dobladillo.imaging.readers import write_gsf
    from dobladillo.imaging.synthetic import synthetic_scan
    from dobladillo.parts.rectangle import rothemund_rectangle

    dims = sorted(rothemund_rectangle().as_dict()["approx_dimensions_nm"].values(), reverse=True)
    scan = synthetic_scan(seed=0, length_nm=dims[0], width_nm=dims[-1], n_aggregates=0)
    write_gsf(scan.image, path)


# --------------------------------------------------------------- security


def test_a_post_without_the_token_is_refused_and_does_nothing(root: Path) -> None:
    client = _client(root)
    response = client.post("/new", data={"slug": "e1", "part": "rectangle"})
    assert response.status_code == 403
    assert "csrf" in response.text
    assert not (root / "e1").exists()
    wrong = client.post("/new", data={"slug": "e1", "part": "rectangle", "csrf": "guess"})
    assert wrong.status_code == 403 and not (root / "e1").exists()


def test_a_post_from_another_origin_is_refused(root: Path) -> None:
    client = _client(root)
    token = _token(client)
    response = client.post(
        "/new",
        data={"slug": "e1", "part": "rectangle", "csrf": token},
        headers={"origin": "http://evil.example"},
    )
    assert response.status_code == 403 and not (root / "e1").exists()


def test_a_post_the_way_a_browser_sends_it_is_accepted(root: Path) -> None:
    """A real browser sends its own Origin on a same-origin form POST. With
    `Referrer-Policy: no-referrer` it sends `Origin: null` instead, and every
    form was refused in a browser while these tests (which sent no Origin)
    passed. So: the policy must not be no-referrer, and the page's own origin
    must be accepted while `null` is not."""
    client = _client(root)
    policy = client.get("/").headers["referrer-policy"]
    assert policy != "no-referrer"
    token = _token(client)
    refused = client.post(
        "/new",
        data={"slug": "e0", "part": "rectangle", "csrf": token},
        headers={"origin": "null"},
    )
    assert refused.status_code == 403 and not (root / "e0").exists()
    accepted = client.post(
        "/new",
        data={"slug": "e1", "part": "rectangle", "csrf": token},
        headers={"origin": "http://testserver"},
        follow_redirects=False,
    )
    assert accepted.status_code in (200, 303), accepted.text
    assert (root / "e1").exists()


def test_only_loopback_host_names_are_answered(root: Path) -> None:
    client = TestClient(web.create_app(root))  # the default: 127.0.0.1 and localhost only
    assert client.get("/", headers={"host": "rebound.example"}).status_code == 400
    assert client.get("/", headers={"host": "127.0.0.1:8765"}).status_code == 200


def test_pages_carry_a_policy_that_allows_no_script(root: Path) -> None:
    response = _client(root).get("/")
    policy = response.headers["content-security-policy"]
    assert "default-src 'none'" in policy and "script-src" not in policy
    assert response.headers["x-frame-options"] == "DENY"
    assert "<script" not in response.text


def test_a_body_over_the_cap_is_refused_before_it_is_read(root: Path) -> None:
    client = _client(root, max_upload=1000)
    token = _token(client)
    response = client.post(
        "/new", data={"slug": "e1", "part": "rectangle", "csrf": token, "pad": "x" * 2000}
    )
    assert response.status_code == 413 and not (root / "e1").exists()


def test_the_default_is_loopback_and_needs_no_token() -> None:
    import typer

    from dobladillo.cli import app

    web_command = typer.main.get_command(app).commands["web"]  # type: ignore[attr-defined]
    assert {p.name: p.default for p in web_command.params}["host"] == "127.0.0.1"
    local = web.plan("127.0.0.1", 8765)
    assert local.token is None and not local.exposed
    assert local.urls == ("http://127.0.0.1:8765/",)
    assert local.allowed_hosts == ("127.0.0.1", "localhost")
    assert web.plan("localhost", 8765).token is None


def test_any_other_host_gets_a_fresh_token_in_every_url() -> None:
    exposed = web.plan("0.0.0.0", 8765)
    assert exposed.exposed and exposed.token and len(exposed.token) >= 24
    assert all(url.endswith(f"/?token={exposed.token}") for url in exposed.urls)
    assert "http://127.0.0.1:8765/?token=" in exposed.urls[-1]
    assert web.plan("0.0.0.0", 8765).token != exposed.token
    one = web.plan("192.168.1.50", 9000)
    assert one.urls[0] == f"http://192.168.1.50:9000/?token={one.token}"
    assert "192.168.1.50" in one.allowed_hosts


def test_exposed_the_page_answers_nothing_without_its_token(root: Path) -> None:
    token = "a-test-token"
    app = web.create_app(root, allowed_hosts=("testserver",), access_token=token)
    client = TestClient(app)
    for path in ("/", "/new", "/e/anything", "/static/style.css", "/?token=wrong"):
        response = client.get(path)
        assert response.status_code == 401, path
        assert str(root) not in response.text and "csrf" not in response.text
    assert client.post("/new", data={"slug": "e1", "part": "rectangle"}).status_code == 401
    assert client.get("/?token=t\u00f6ken").status_code == 401  # non-ASCII: refused, no crash

    first = client.get(f"/?token={token}")
    assert first.status_code == 200
    cookie = first.headers["set-cookie"]
    assert f"dobladillo_token={token}" in cookie
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie
    # The cookie carries it from here: no token in the next URL.
    assert client.get("/new").status_code == 200
    # And a POST still needs the page's CSRF token as well.
    assert client.post("/new", data={"slug": "e1", "part": "rectangle"}).status_code == 403
    csrf = TOKEN.search(client.get("/new").text)
    assert csrf is not None
    made = client.post("/new", data={"slug": "e1", "part": "rectangle", "csrf": csrf.group(1)})
    assert made.status_code == 200 and (root / "e1").is_dir()
    # Another browser, without the cookie, is still refused.
    assert TestClient(app).get("/e/e1").status_code == 401


# ----------------------------------------------------------- path bounds


def test_names_outside_the_root_are_refused(root: Path, tmp_path: Path) -> None:
    (tmp_path / "secret.txt").write_text("not yours")
    client = _client(root)
    assert client.get("/e/%2E%2E").status_code == 404
    assert "outside_root" in client.get("/e/%2E%2E").text
    token = _token(client)
    response = client.post("/new", data={"slug": "../escaped", "part": "rectangle", "csrf": token})
    assert response.status_code == 400
    assert not (root.parent / "escaped").exists()


def test_every_file_of_the_experiment_downloads_and_nothing_outside_it(root: Path) -> None:
    client = _client(root)
    token = _token(client)
    client.post("/new", data={"slug": "e1", "part": "rectangle", "csrf": token})
    folder = root / "e1"
    (folder / "post" / "note.json").write_text("{}")
    for path in (
        "pre/order/rectangle_bulk.csv",
        "pre/prediction.json",
        "pre/plan.md",
        "during/instrument.json",
        "post/note.json",
    ):
        ok = client.get(f"/e/e1/files/{path}")
        assert ok.status_code == 200, path
        assert "attachment" in ok.headers["content-disposition"], path
    secret = root.parent / "secret.txt"
    secret.write_text("not yours")
    (folder / "during" / "raw" / "link.txt").symlink_to(secret)
    (folder / "pre" / ".hidden").write_text("x")
    for path in (
        "..%2F..%2Fsecret.txt",
        "pre/order/..%2F..%2F..%2Fx",
        "during/raw/link.txt",  # a symlink leading out of the folder
        "pre/.hidden",
        "pre",  # a directory
        "missing.txt",
    ):
        assert client.get(f"/e/e1/files/{path}").status_code == 404, path
    page = client.get("/e/e1").text
    assert 'id="files"' in page
    assert "/e/e1/files/pre/plan.md" in page and "/e/e1/files/during/instrument.json" in page
    assert "link.txt" not in page.split('id="files"')[1].split("</section>")[0]


# ------------------------------------------------------------ the lifecycle


def test_the_whole_lifecycle_through_the_page(root: Path, tmp_path: Path) -> None:
    client = _client(root)
    token = _token(client)

    def post(path: str, **data: str) -> Any:
        response = client.post(path, data={**data, "csrf": token})
        assert response.status_code == 200, response.text[:2000]
        return response

    # New experiment: the page runs `experiment new` and lands on the folder.
    response = post("/new", slug="e1", part="rectangle")
    assert response.url.path == "/e/e1"
    folder = root / "e1"
    assert (folder / "pre" / "prediction.json").is_file()
    assert "Save the criterion" in response.text

    # Uploading before the lock is the command's refusal, shown with its kind.
    raw = tmp_path / "instrument" / "scan-01.gsf"
    raw.parent.mkdir()
    _synthetic_scan(raw)
    early = client.post(
        "/e/e1/upload",
        data={"csrf": token, "as": ""},
        files={"file": ("scan-01.gsf", raw.read_bytes(), "application/octet-stream")},
    )
    assert "not_locked" in early.text and "Refused" in early.text
    assert not (folder / "during" / "raw" / "scan-01.gsf").exists()

    # The gate, then the lock. Each step changes only what its command writes.
    gate = "Fails if the tip-corrected width is more than 10% from 66 nm"
    before = _tree(root)
    post("/e/e1/criterion", text=gate)
    assert _changed(before, _tree(root)) == {"e1/pre/plan.md"}

    before = _tree(root)
    response = post("/e/e1/lock")
    assert _changed(before, _tree(root)) == set()  # a commit, not a file change
    assert "e1: lock pre/" in _git(folder, "log", "-1", "--format=%s")
    assert "Locked in commit" in response.text
    assert 'name="text" rows="4"' not in response.text  # the gate is read-only now

    # Written after the lock, the gate is refused, and the plan stays as locked.
    refused = post("/e/e1/criterion", text="a different gate")
    assert "locked" in refused.text and gate in (folder / "pre" / "plan.md").read_text()

    # The instrument record: only the fields sent change.
    before = _tree(root)
    post(
        "/e/e1/record",
        **{
            "f:tip.measured_radius_before_nm": "10",
            "f:tip.measured_radius_after_nm": "10",
            "f:instrument": "",
        },
    )
    assert _changed(before, _tree(root)) == {"e1/during/instrument.json"}
    record = json.loads((folder / "during" / "instrument.json").read_text())
    assert record["tip"]["measured_radius_before_nm"] == 10

    bad = post("/e/e1/record", **{"f:tip.measured_radius_after_nm": "0"})
    assert "invalid_value" in bad.text
    assert json.loads((folder / "during" / "instrument.json").read_text()) == record

    post("/e/e1/log", text="Scan 1, tip measured before and after")

    # The scan, uploaded through `experiment upload`.
    before = _tree(root)
    response = client.post(
        "/e/e1/upload",
        data={"csrf": token, "as": ""},
        files={"file": ("C:\\bench\\scan-01.gsf", raw.read_bytes(), "application/octet-stream")},
    )
    assert response.status_code == 200
    assert _changed(before, _tree(root)) == {"e1/during/raw/scan-01.gsf", "e1/during/uploads.json"}
    digest = hashlib.sha256(raw.read_bytes()).hexdigest()
    assert (folder / "during" / "raw" / "scan-01.gsf").read_bytes() == raw.read_bytes()
    assert digest[:12] in response.text

    # A traversal in the name is the command's refusal, and nothing escapes.
    escape = client.post(
        "/e/e1/upload",
        data={"csrf": token, "as": "../../escaped.gsf"},
        files={"file": ("x.gsf", b"bytes", "application/octet-stream")},
    )
    assert "outside_raw" in escape.text
    assert not (folder / "escaped.gsf").exists() and not (root / "escaped.gsf").exists()

    post("/e/e1/commit", phase="during", message="session 1")
    assert _git(folder, "log", "-1", "--format=%s").strip() == "session 1"

    # Only this part's analyses run; the page offers them and refuses others.
    assert (
        client.post("/e/e1/analyse", data={"csrf": token, "command": "experiment new"}).status_code
        == 400
    )

    before = _tree(root)
    response = post("/e/e1/analyse", command="experiment report")
    written = _changed(before, _tree(root))
    assert written == {
        "e1/post/measurements.json",
        "e1/post/comparison.json",
        "e1/post/report.md",
    }
    # The result, beside the gate written before it.
    analyse = response.text.split('id="analyse"', 1)[1].split('id="provenance"', 1)[0]
    assert gate in analyse
    assert "length: measured" in analyse and "width: designed vs measured" in analyse
    assert "tolerance" in analyse and "standard error" in analyse
    assert "Nothing here evaluates the criterion" in analyse
    comparison = json.loads((folder / "post" / "comparison.json").read_text())
    assert comparison["comparisons"]["width"]["observations"]

    # Reading a page writes nothing.
    before = _tree(root)
    client.get("/e/e1")
    client.get("/")
    assert _changed(before, _tree(root)) == set()


def test_the_page_writes_only_through_commands(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With the command runner replaced by one that refuses everything, no POST
    changes the folder: the page has no way of writing of its own."""
    client = _client(root)
    token = _token(client)
    client.post("/new", data={"slug": "e1", "part": "rectangle", "csrf": token})
    before = _tree(root)
    calls: list[tuple[str, ...]] = []
    real = web.run_json

    def refusing(*args: str) -> tuple[int, dict[str, Any]]:
        calls.append(args)
        if args[:2] in (("experiment", "status"), ("experiment", "record")) and len(args) == 3:
            return real(*args)  # reads, which the forms need to render
        return 1, {"error": {"kind": "stubbed", "message": "no command ran"}}

    monkeypatch.setattr(web, "run_json", refusing)
    client.post("/e/e1/criterion", data={"csrf": token, "text": "gate"})
    client.post("/e/e1/lock", data={"csrf": token})
    client.post("/e/e1/record", data={"csrf": token, "f:temperature_c": "21"})
    client.post("/e/e1/log", data={"csrf": token, "text": "entry"})
    client.post(
        "/e/e1/upload",
        data={"csrf": token},
        files={"file": ("x.gsf", b"bytes", "application/octet-stream")},
    )
    client.post("/e/e1/commit", data={"csrf": token, "phase": "during"})
    assert _changed(before, _tree(root)) == set()
    ran = {a[:2] for a in calls}
    assert {
        ("experiment", "criterion"),
        ("experiment", "lock"),
        ("experiment", "record"),
        ("experiment", "log"),
        ("experiment", "upload"),
        ("experiment", "commit"),
    } <= ran


def test_rendered_text_is_escaped(root: Path) -> None:
    client = _client(root)
    token = _token(client)
    client.post("/new", data={"slug": "e1", "part": "rectangle", "csrf": token})
    client.post("/e/e1/criterion", data={"csrf": token, "text": "<script>alert(1)</script>"})
    page = client.get("/e/e1").text
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page


def test_home_lists_folders_with_their_next_step(root: Path) -> None:
    client = _client(root)
    token = _token(client)
    client.post("/new", data={"slug": "e1", "part": "bundle", "csrf": token})
    page = client.get("/").text
    assert 'href="/e/e1"' in page and "bundle" in page and "Write the pass/fail criterion" in page
    assert "New experiment" in page


def test_a_new_experiment_that_exists_is_refused_on_the_form(root: Path) -> None:
    client = _client(root)
    token = _token(client)
    client.post("/new", data={"slug": "e1", "part": "rectangle", "csrf": token})
    again = client.post("/new", data={"slug": "e1", "part": "rectangle", "csrf": token})
    assert again.status_code == 400 and "already_exists" in again.text


def _locked_e1(root: Path, client: TestClient, token: str, tmp_path: Path) -> tuple[Path, Path]:
    """A rectangle experiment with its gate locked and a measured tip recorded."""
    for path, data in (
        ("/new", {"slug": "e1", "part": "rectangle"}),
        ("/e/e1/criterion", {"text": "Fails if the width is more than 10% from 66 nm"}),
        ("/e/e1/lock", {}),
        (
            "/e/e1/record",
            {"f:tip.measured_radius_before_nm": "10", "f:tip.measured_radius_after_nm": "10"},
        ),
    ):
        assert client.post(path, data={**data, "csrf": token}).status_code == 200
    raw = tmp_path / "instrument" / "scan-01.gsf"
    raw.parent.mkdir(exist_ok=True)
    _synthetic_scan(raw)
    return root / "e1", raw


def _upload(client: TestClient, token: str, raw: Path) -> Any:
    return client.post(
        "/e/e1/upload",
        data={"csrf": token, "as": ""},
        files={"file": ("scan-01.gsf", raw.read_bytes(), "application/octet-stream")},
    )


def test_automatic_analysis_is_off_by_default(root: Path, tmp_path: Path) -> None:
    client = _client(root)
    token = _token(client)
    folder, raw = _locked_e1(root, client, token, tmp_path)
    response = _upload(client, token, raw)
    assert "Automatic analysis: off" in response.text
    assert not (folder / "post" / "report.md").exists()


def test_switched_on_the_analysis_runs_after_an_upload(root: Path, tmp_path: Path) -> None:
    import os

    client = _client(root)
    token = _token(client)
    folder, raw = _locked_e1(root, client, token, tmp_path)

    before = _tree(root)
    on = client.post("/e/e1/auto", data={"csrf": token, "auto": "on"})
    assert on.status_code == 200 and "Automatic analysis: on" in on.text
    assert _changed(before, _tree(root)) == set()  # a preference, not the record
    settings = json.loads((Path(os.environ["DOBLADILLO_CONFIG_DIR"]) / "web.json").read_text())
    assert settings["experiments"][str(folder.resolve())]["auto_analyse"] is True

    response = _upload(client, token, raw)
    assert response.status_code == 200
    assert "Automatic analysis" in response.text and "experiment report" in response.text
    assert (folder / "post" / "report.md").is_file()

    off = client.post("/e/e1/auto", data={"csrf": token, "auto": "off"})
    assert "Automatic analysis: off" in off.text


def test_the_switch_needs_the_csrf_token(root: Path) -> None:
    client = _client(root)
    token = _token(client)
    client.post("/new", data={"slug": "e1", "part": "rectangle", "csrf": token})
    assert client.post("/e/e1/auto", data={"auto": "on"}).status_code == 403
