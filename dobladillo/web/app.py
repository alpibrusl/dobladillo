"""The local web UI: an experiment's lifecycle in the browser, over the CLI's contract.

A person at the bench should not need a terminal to run an experiment the
way the folder layout asks: write the gate, lock `pre/`, order, record the
instrument, upload the raw files, analyse, and read the result beside the
gate written before the data. This is that, as plain server-rendered pages.

**One contract.** Like `mcp_server`, every action runs the matching CLI
command in-process with `--json` (`dobladillo._invoke.run_json`) and renders
its payload. A refusal is shown with its `error.kind`, its message and what
to do about it. Nothing here writes a file itself: the experiment folder is
changed only by those commands, so the CLI, the MCP server, the dashboard and
the provenance chain keep reading the same record. The only things this
module reads directly are the folder's documents, to display them.

**Human acts only.** The commands behind the forms -- `experiment criterion`,
`lock`, `log`, `record`, `upload`, `commit` -- are in
`mcp_server.FORBIDDEN_COMMANDS`, and an agent must not drive this page to
reach them (`experiments/AGENTS.md`).

**Security, for a page on localhost.** Any web page open in the same browser
can send a POST to 127.0.0.1, so:

- the server binds 127.0.0.1 by default. Bound to anything else (`--host`,
  to open it from a phone on the same network) it requires a random access
  token of every request, printed in the URLs at startup and then kept in an
  HttpOnly, SameSite=Strict cookie (`AccessToken`), and says loudly that it
  is reachable from the network;
- the Host header must name 127.0.0.1, localhost or, when exposed, one of
  this machine's addresses, which stops a DNS-rebinding page from reading
  responses as if it were this origin;
- every POST carries a per-process random token that only a page served
  here can read, and a POST with a foreign Origin is refused;
- request bodies are capped (`MAX_UPLOAD_BYTES`), uploads go to a temporary
  file outside the folder and into `during/raw/` only via `experiment
  upload`;
- experiment folders are addressed by name, and a name that resolves outside
  `--root` is refused, as the MCP server's `folder` helper refuses it;
- every rendered string is escaped (Jinja autoescape), Markdown is rendered
  with raw HTML off, and the pages carry a Content-Security-Policy that
  allows no script at all: there is no JavaScript here.

**Authorship.** Single user: commits carry the local git identity, as at the
CLI. The lifecycle functions already take an `author`; a multi-user version
would authenticate the request here and pass its user through.
"""

from __future__ import annotations

import datetime as _dt
import hmac
import json
import secrets
import tempfile
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Final

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markdown_it import MarkdownIt
from markupsafe import Markup
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import FormData, UploadFile
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from dobladillo._invoke import run_json

HERE: Final = Path(__file__).resolve().parent

#: The largest request body accepted, an upload included. AFM files are tens
#: of megabytes; a high-speed movie can be a few hundred.
MAX_UPLOAD_BYTES: Final = 1 << 30

#: The only names this server answers to.
LOOPBACK_HOSTS: Final = ("127.0.0.1", "localhost")

#: Where downloads may come from, inside an experiment folder: every phase.
#: A file is served only if, once resolved, it is still inside one of these
#: (so `..` and symlinks leading out are refused) and no part of its path is
#: hidden (so nothing like `.git` is ever served).
DOWNLOADABLE: Final = ("pre", "during", "post")

SECURITY_HEADERS: Final = (
    (
        b"content-security-policy",
        b"default-src 'none'; style-src 'self'; img-src 'self'; form-action 'self'; "
        b"frame-ancestors 'none'; base-uri 'none'",
    ),
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    # same-origin, NOT no-referrer: under the Fetch standard a POST from a page
    # whose policy is no-referrer carries `Origin: null`, which the origin check
    # below refuses -- every form failed in a real browser (2026-09-29) while
    # the tests, whose client sends no Origin, passed. same-origin still sends
    # nothing, and so no token-bearing URL, to any other site.
    (b"referrer-policy", b"same-origin"),
    (b"cache-control", b"no-store"),
)

#: What to do about a refusal, by its kind. The message says what is wrong;
#: this says where on the page to fix it. Absent kinds get the message alone.
HINTS: Final[dict[str, str]] = {
    "no_criterion": "Write the pass/fail criterion in section 1, then lock the plan.",
    "empty_criterion": "Write the pass/fail criterion in section 1: what result would make "
    "this a failure?",
    "locked": "The criterion is locked in the plan. Record any change of mind in the session "
    "log (section 4); it stays visible as what it is.",
    "not_locked": "Write the pass/fail criterion (section 1) and lock the plan (section 3) first.",
    "not_in_git": "Keep the experiments folder inside a git repository (git init), then lock.",
    "already_locked": "Nothing to do: the plan is locked and unchanged.",
    "pre_incomplete": "The plan (pre/) lacks a file `experiment new` writes; see section 2.",
    "pre_changed": "The plan (pre/) changed after it was locked. Lock again to record the "
    "change as its own act, or undo it.",
    "already_exists": "Raw files are never replaced. Upload it under another name.",
    "outside_raw": "Give a plain relative name, like scan-01.spm or staircase/S1-01.spm.",
    "unknown_field": "Nothing was written. Use the fields listed in section 4.",
    "invalid_value": "Nothing was written. Correct the value; the field lists what it accepts.",
    "nothing_to_commit": "Nothing changed since the last commit.",
    "git_failed": "git said why above. A missing user.name/user.email is set with git config.",
    "no_tip_radius": "Measure the tip and record tip.measured_radius_before_nm and "
    "tip.measured_radius_after_nm in section 4. Never the nominal value.",
    "no_scans": "Upload the instrument's raw files in section 4, named as the protocol says.",
    "no_reference_height": "Record reference.flat_height_nm (from E1) in section 4.",
    "no_imaging_order": "Record imaging_order (X,Y or Y,X) in section 4.",
    "csrf": "Reload the page and submit the form again.",
    "outside_root": "Open experiments from the list on the home page.",
    "already_exists_folder": "Pick another name.",
}


class Refusal(Exception):
    """A request this server will not serve, shown as a page with its kind."""

    def __init__(self, kind: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.kind = kind
        self.status = status


@dataclass
class Site:
    """Per-process state. Nothing here is the record; the folders are."""

    root: Path
    csrf: str
    max_upload: int
    #: True when listening beyond loopback, behind an access token.
    exposed: bool = False
    flashes: OrderedDict[str, dict[str, Any]] = field(default_factory=OrderedDict)
    protocols: dict[str, tuple[int, dict[str, Any]]] = field(default_factory=dict)
    guard: threading.Lock = field(default_factory=threading.Lock)

    def remember(self, outcome: dict[str, Any]) -> str:
        """Keep an action's outcome for the page the browser is redirected to."""
        key = secrets.token_urlsafe(8)
        with self.guard:
            self.flashes[key] = outcome
            while len(self.flashes) > 64:
                self.flashes.popitem(last=False)
        return key

    def folder(self, name: str) -> Path:
        """An experiment folder by name, never outside the root."""
        candidate = (self.root / name).resolve()
        if candidate.parent != self.root or name in ("", ".", ".."):
            raise Refusal("outside_root", f"{name!r} is not a folder under {self.root}", 404)
        if not (candidate / "pre").is_dir():
            raise Refusal("missing_folder", f"no experiment {name!r} under {self.root}", 404)
        return candidate


# ------------------------------------------------------------- rendering

_MARKDOWN = MarkdownIt("js-default")  # CommonMark + tables; raw HTML off


def _markdown(text: str) -> Markup:
    return Markup(_MARKDOWN.render(text))  # noqa: S704 - markdown-it escapes, html is off


def _environment() -> Environment:
    env = Environment(
        loader=FileSystemLoader(HERE / "templates"),
        autoescape=select_autoescape(["html"], default_for_string=True, default=True),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["markdown"] = _markdown
    env.filters["pretty"] = lambda v: json.dumps(v, indent=2, ensure_ascii=False)
    env.filters["short"] = lambda v: str(v)[:12] if v else "none"
    env.filters["size"] = _size
    return env


def _size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024  # type: ignore[assignment]
    return f"{n} B"  # pragma: no cover


_ENV = _environment()


def _page(request: Request, template: str, status: int = 200, **context: Any) -> HTMLResponse:
    site: Site = request.app.state.site
    html = _ENV.get_template(template).render(
        csrf=site.csrf,
        root=str(site.root),
        exposed=site.exposed,
        request_path=request.url.path,
        **context,
    )
    return HTMLResponse(html, status_code=status)


def _as_input(value: Any) -> str:
    """A recorded value as the text a form field shows, and sends back unchanged."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return ",".join(value)
    return json.dumps(value)


#: Keys of an analysis payload that are record, not result: shown elsewhere.
_NOT_RESULTS: Final = frozenset({"record", "provenance", "design", "directory", "files", "scans"})


def _flatten(
    value: Any, prefix: str = "", out: list[tuple[str, str]] | None = None
) -> list[tuple[str, str]]:
    """A payload's numbers as labelled rows, intervals beside the values they bound."""
    rows = [] if out is None else out
    if len(rows) >= 80:
        return rows
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _NOT_RESULTS:
                continue
            _flatten(item, f"{prefix}.{key}" if prefix else str(key), rows)
    elif isinstance(value, list):
        if all(not isinstance(v, dict | list) for v in value):
            if value:
                rows.append((prefix, ", ".join(_scalar(v) for v in value[:16])))
        elif len(value) <= 12:
            for i, item in enumerate(value):
                _flatten(item, f"{prefix}[{i}]", rows)
        else:
            rows.append((prefix, f"{len(value)} entries (see the full payload)"))
    else:
        rows.append((prefix, _scalar(value)))
    return rows


def _scalar(value: Any) -> str:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def _comparison_rows(payload: dict[str, Any]) -> list[tuple[str, str]]:
    """`experiment report`'s comparisons: each value with its error, each pair's gap."""
    rows: list[tuple[str, str]] = []
    for quantity, comparison in (payload.get("comparisons") or {}).items():
        for o in comparison.get("observations", []):
            text = f"{o['value_nm']} nm"
            if o.get("standard_error_nm"):
                text += f" ± {o['standard_error_nm']} nm (standard error)"
            if o.get("n"):
                text += f", n = {o['n']}"
            rows.append((f"{quantity}: {o['origin']}", text))
        for p in comparison.get("pairs", []):
            # The comparison's own verdict, in its own words: whether the two
            # numbers agree within the tolerance `compare` derives. Not the gate.
            verdict = "agrees" if p.get("agrees") else "DISAGREES"
            rows.append(
                (
                    f"{quantity}: {p['from']} vs {p['to']}",
                    f"difference {p['difference_nm']:+} nm ({100 * p['relative']:+.1f}%), "
                    f"{p['sigma']} sigma of the combined error {p['combined_error_nm']} nm; "
                    f"tolerance {p['tolerance_nm']} nm: {verdict}"
                    + (f" ({p['explained_by']})" if p.get("explained_by") else ""),
                )
            )
        rows += [(f"{quantity}: refused", r) for r in comparison.get("refused", [])]
    return rows


def _result_rows(command: str, payload: dict[str, Any]) -> list[tuple[str, str]]:
    if command == "experiment report" or "comparisons" in payload:
        rows = _comparison_rows(payload)
        if rows:
            return rows
    return _flatten(payload)


def _measurement_rows(measurements: dict[str, Any]) -> list[tuple[str, str]]:
    keys = (
        ("particles", "particles clear of the frame edge"),
        ("measured_particles", "particles measured"),
        ("measured_over", "measured over"),
        ("tip_radius_nm", "tip radius, nm (from the record)"),
        ("tip_blunting_fraction", "tip blunting over the session"),
        ("tip_widening_nm", "tip widening removed, nm"),
        ("median_height_nm", "median height, nm"),
    )
    return [(label, _scalar(measurements[k])) for k, label in keys if k in measurements]


def _outcome(command: list[str], code: int, payload: dict[str, Any]) -> dict[str, Any]:
    """What an action did, in the shape every page shows it."""
    found = payload.get("error")
    refused = isinstance(found, dict) and code != 0
    error: dict[str, Any] = found if isinstance(found, dict) else {}
    shown = " ".join(command)
    return {
        "command": f"dobladillo {shown}",
        "code": code,
        "refused": refused,
        "kind": error.get("kind") if refused else None,
        "message": error.get("message") if refused else None,
        "hint": HINTS.get(str(error.get("kind"))) if refused else None,
        "rows": [] if refused else _result_rows(" ".join(command[:2]), payload),
        "payload": payload,
        "at": _dt.datetime.now().strftime("%H:%M:%S"),
    }


# ------------------------------------------------------------- requests


def _same(offered: str, secret: str) -> bool:
    """Constant-time comparison that cannot raise on non-ASCII input."""
    return hmac.compare_digest(offered.encode(), secret.encode())


async def _form(request: Request) -> FormData:
    """The POSTed form, once its size, origin and CSRF token check out."""
    site: Site = request.app.state.site
    length = request.headers.get("content-length")
    if length is None or not length.isdigit():
        raise Refusal("length_required", "a POST must say how long it is", 411)
    if int(length) > site.max_upload:
        raise Refusal(
            "too_large",
            f"{int(length):,} bytes is over this server's limit of {site.max_upload:,}",
            413,
        )
    origin = request.headers.get("origin")
    if origin is not None and origin != f"{request.url.scheme}://{request.url.netloc}":
        raise Refusal("cross_origin", f"a form from {origin} cannot act here", 403)
    form = await request.form(max_files=1, max_fields=200)
    token = form.get("csrf")
    if not isinstance(token, str) or not _same(token, site.csrf):
        await form.close()
        raise Refusal(
            "csrf",
            "this form did not come from a page this server rendered (missing or stale "
            "token); nothing was done",
            403,
        )
    return form


def _text(form: FormData, key: str) -> str:
    value = form.get(key)
    return value if isinstance(value, str) else ""


async def _act(request: Request, name: str, command: list[str], anchor: str) -> RedirectResponse:
    site: Site = request.app.state.site
    code, payload = await run_in_threadpool(run_json, *command)
    shown = [c if c != str(site.folder(name)) else name for c in command]
    key = site.remember(_outcome(shown, code, payload))
    return RedirectResponse(f"/e/{name}?done={key}#{anchor}", status_code=303)


def _prediction_rows(folder: Path) -> list[tuple[str, str]]:
    try:
        prediction = json.loads((folder / "pre" / "prediction.json").read_text())
    except (OSError, ValueError):
        return []
    if not isinstance(prediction, dict):
        return []
    rows = [("part", _scalar(prediction.get("part")))]
    for key, value in (prediction.get("predicted_nm") or {}).items():
        rows.append((f"predicted {key}", f"{value} nm"))
    window = prediction.get("folding_window") or {}
    tm = window.get("staple_tm_c") if isinstance(window, dict) else None
    if isinstance(tm, dict) and "median" in tm:
        rows.append(
            ("staple Tm", f"median {tm['median']} C, 10-90% {tm.get('p10')}-{tm.get('p90')} C")
        )
    design = (prediction.get("provenance") or {}).get("design_sha256")
    rows.append(("design", str(design)[:12] if design else "no design hash recorded"))
    rows.append(("generated by", _scalar(prediction.get("generated_by"))))
    return rows


def _protocol_rows(sheet: dict[str, Any]) -> list[tuple[str, str]]:
    try:
        anneal, buffer_ = sheet["anneal"], sheet["buffer"]
        return [
            (
                "buffer",
                f"{buffer_['tris_mm']} mM Tris, {buffer_['edta_mm']} mM EDTA, pH {buffer_['ph']}",
            ),
            ("Mg2+ screen", ", ".join(f"{m:g}" for m in sheet["magnesium_screen_mm"]) + " mM"),
            ("reactions", str(len(sheet["reactions"]))),
            ("hold", f"{anneal['hold']['temperature_c']} C for {anneal['hold']['minutes']:g} min"),
            (
                "ramp",
                f"{anneal['ramp']['from_c']} to {anneal['ramp']['to_c']} C at "
                f"{anneal['ramp']['rate']:g} {anneal['ramp']['rate_unit']}",
            ),
            ("total", f"{anneal['total_hours']} h"),
            ("purification", " / ".join(sheet["purification"])),
        ]
    except (KeyError, TypeError, ValueError):
        return _flatten(sheet)


def _downloadable(folder: Path, relative: str) -> Path | None:
    """The file `relative` names inside `folder`, if it may be served; else None."""
    if any(part.startswith(".") for part in Path(relative).parts):
        return None
    candidate = (folder / relative).resolve()
    bases = [(folder / b).resolve() for b in DOWNLOADABLE]
    if not any(base in candidate.parents for base in bases) or not candidate.is_file():
        return None
    return candidate


def _phase_files(folder: Path) -> dict[str, list[dict[str, Any]]]:
    """Every servable file of each phase, for the Files section."""
    out: dict[str, list[dict[str, Any]]] = {}
    for phase in DOWNLOADABLE:
        base = folder / phase
        if not base.is_dir():
            continue
        rows = []
        for p in sorted(base.rglob("*")):
            relative = str(p.relative_to(folder))
            if p.is_file() and _downloadable(folder, relative) is not None:
                rows.append({"path": relative, "bytes": p.stat().st_size})
        out[phase] = rows
    return out


def _files_under(folder: Path, relative: str) -> list[dict[str, Any]]:
    base = folder / relative
    if not base.is_dir():
        return []
    return [
        {
            "path": str(p.relative_to(folder)),
            "name": str(p.relative_to(base)),
            "bytes": p.stat().st_size,
        }
        for p in sorted(base.rglob("*"))
        if p.is_file() and p.name != "README.md"
    ]


def _results_on_disk(folder: Path, analyses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """What each analysis last wrote into post/, as rows."""
    out = []
    for analysis in analyses:
        files = []
        for relative in analysis["writes"]:
            path = folder / relative
            if not path.is_file() or path.suffix != ".json":
                continue
            try:
                data = json.loads(path.read_text())
            except ValueError:
                continue
            if relative.endswith("measurements.json"):
                rows = _measurement_rows(data)
            else:
                rows = _result_rows(analysis["command"], data)
            files.append({"path": relative, "rows": rows, "payload": data})
        out.append({**analysis, "results": files})
    return out


# ------------------------------------------------------------- pages


def home(request: Request) -> HTMLResponse:
    site: Site = request.app.state.site
    folders = []
    for path in sorted(p for p in site.root.iterdir() if (p / "pre").is_dir()):
        code, payload = run_json("experiment", "status", str(path))
        folders.append({"name": path.name, "code": code, "status": payload})
    return _page(request, "home.html", folders=folders)


def new_form(request: Request) -> HTMLResponse:
    from dobladillo.cli import EXPERIMENT_PARTS

    today = _dt.date.today().isoformat()
    return _page(request, "new.html", parts=EXPERIMENT_PARTS, slug=f"{today}-", part="rectangle")


async def new_submit(request: Request) -> Response:
    from dobladillo.cli import EXPERIMENT_PARTS

    site: Site = request.app.state.site
    form = await _form(request)
    slug, part = _text(form, "slug").strip(), _text(form, "part")
    problem = None
    if not slug or slug.startswith(".") or "/" in slug or "\\" in slug:
        problem = "the name must be one folder name, e.g. 2026-09-29-rectangle-afm"
    elif (site.root / slug).resolve().parent != site.root:
        problem = f"{slug!r} would not be under {site.root}"
    elif part not in EXPERIMENT_PARTS:
        problem = f"unknown part {part!r}"
    if problem:
        outcome = _outcome(
            ["experiment", "new", slug],
            2,
            {"error": {"kind": "invalid_parameters", "message": problem}},
        )
        return _page(
            request,
            "new.html",
            400,
            parts=EXPERIMENT_PARTS,
            slug=slug,
            part=part,
            outcome=outcome,
        )
    command = ["experiment", "new", slug, "--part", part, "--root", str(site.root)]
    code, payload = await run_in_threadpool(run_json, *command)
    outcome = _outcome(["experiment", "new", slug, "--part", part], code, payload)
    if outcome["refused"]:
        return _page(
            request,
            "new.html",
            400,
            parts=EXPERIMENT_PARTS,
            slug=slug,
            part=part,
            outcome=outcome,
        )
    key = site.remember(outcome)
    return RedirectResponse(f"/e/{slug}?done={key}", status_code=303)


def experiment(request: Request) -> HTMLResponse:
    site: Site = request.app.state.site
    name = request.path_params["name"]
    folder = site.folder(name)
    code, status = run_json("experiment", "status", str(folder))
    if "error" in status and code != 0:
        raise Refusal(status["error"]["kind"], status["error"]["message"])
    _, record = run_json("experiment", "record", str(folder))
    part = status.get("part")
    sheet: tuple[int, dict[str, Any]] | None = None
    if part:
        with site.guard:
            sheet = site.protocols.get(part)
        if sheet is None:
            sheet = run_json("lab", "protocol", part)
            with site.guard:
                site.protocols[part] = sheet
    plan = folder / "pre" / "plan.md"
    protocol = folder / "pre" / "protocol.md"
    flash = site.flashes.get(request.query_params.get("done", ""))
    fields = [{**f, "input": _as_input(f.get("value"))} for f in record.get("fields", [])]
    return _page(
        request,
        "experiment.html",
        name=name,
        s=status,
        steps={s["step"]: s for s in status["steps"]},
        flash=flash,
        plan=plan.read_text() if plan.is_file() else "",
        protocol=protocol.read_text() if protocol.is_file() else "",
        prediction=_prediction_rows(folder),
        order=_files_under(folder, "pre/order"),
        files=_phase_files(folder),
        sheet=None
        if sheet is None
        else {
            "refused": "error" in sheet[1] and sheet[0] != 0,
            "payload": sheet[1],
            "rows": _protocol_rows(sheet[1]),
        },
        record=record,
        fields=fields,
        analyses=_results_on_disk(folder, status.get("analyses", [])),
        max_upload=site.max_upload,
    )


async def criterion(request: Request) -> Response:
    name = request.path_params["name"]
    folder = request.app.state.site.folder(name)
    form = await _form(request)
    return await _act(
        request, name, ["experiment", "criterion", str(folder), _text(form, "text")], "plan"
    )


async def lock(request: Request) -> Response:
    name = request.path_params["name"]
    folder = request.app.state.site.folder(name)
    await _form(request)
    return await _act(request, name, ["experiment", "lock", str(folder)], "lock")


async def log(request: Request) -> Response:
    name = request.path_params["name"]
    folder = request.app.state.site.folder(name)
    form = await _form(request)
    return await _act(
        request, name, ["experiment", "log", str(folder), _text(form, "text")], "during"
    )


async def record(request: Request) -> Response:
    site: Site = request.app.state.site
    name = request.path_params["name"]
    folder = site.folder(name)
    form = await _form(request)
    _, current = await run_in_threadpool(run_json, "experiment", "record", str(folder))
    before = {f["field"]: _as_input(f.get("value")) for f in current.get("fields", [])}
    command = ["experiment", "record", str(folder)]
    for key, value in form.multi_items():
        if not key.startswith("f:") or not isinstance(value, str):
            continue
        field_name = key[2:]
        # Only what the person changed: an untouched field is not re-asserted.
        if before.get(field_name) != value:
            command += ["--set", f"{field_name}={value}"]
    if len(command) == 3:
        outcome = _outcome(["experiment", "record", name], 0, {"changed": {}})
        outcome["rows"] = [("nothing changed", "no field differs from the record")]
        key = site.remember(outcome)
        return RedirectResponse(f"/e/{name}?done={key}#instrument", status_code=303)
    return await _act(request, name, command, "instrument")


def _upload_name(filename: str) -> str:
    """The browser's file name without any directory it sent along."""
    return PureWindowsPath(PurePosixPath(filename).name).name


async def upload(request: Request) -> Response:
    site: Site = request.app.state.site
    name = request.path_params["name"]
    folder = site.folder(name)
    form = await _form(request)
    item = form.get("file")
    if not isinstance(item, UploadFile) or not item.filename:
        await form.close()
        raise Refusal("missing_file", "choose a file to upload")
    target = _text(form, "as").strip() or _upload_name(item.filename)
    try:
        with tempfile.TemporaryDirectory(prefix="dobladillo-upload-") as tmp:
            staged = Path(tmp) / "upload"
            with staged.open("wb") as out:
                while chunk := await item.read(1 << 20):
                    out.write(chunk)
            command = ["experiment", "upload", str(folder), str(staged), "--as", target]
            code, payload = await run_in_threadpool(run_json, *command)
    finally:
        await form.close()
    shown = ["experiment", "upload", name, item.filename, "--as", target]
    key = site.remember(_outcome(shown, code, payload))
    return RedirectResponse(f"/e/{name}?done={key}#raw", status_code=303)


async def commit(request: Request) -> Response:
    name = request.path_params["name"]
    folder = request.app.state.site.folder(name)
    form = await _form(request)
    phase = _text(form, "phase")
    command = ["experiment", "commit", str(folder), "--phase", phase]
    message = _text(form, "message").strip()
    if message:
        command += ["-m", message]
    return await _act(request, name, command, "analyse" if phase == "post" else "during")


async def analyse(request: Request) -> Response:
    name = request.path_params["name"]
    folder = request.app.state.site.folder(name)
    form = await _form(request)
    wanted = _text(form, "command")
    _, status = await run_in_threadpool(run_json, "experiment", "status", str(folder))
    allowed = [a["command"] for a in status.get("analyses", [])]
    if wanted not in allowed:
        raise Refusal(
            "not_an_analysis",
            f"{wanted!r} is not an analysis for this folder's part; these are: "
            + (", ".join(allowed) or "none"),
        )
    return await _act(request, name, [*wanted.split(), str(folder)], "analyse")


def download(request: Request) -> FileResponse:
    site: Site = request.app.state.site
    folder = site.folder(request.path_params["name"])
    relative = request.path_params["path"]
    candidate = _downloadable(folder, relative)
    if candidate is None:
        raise Refusal(
            "not_downloadable",
            f"{relative!r} is not a file in this experiment's pre/, during/ or post/",
            404,
        )
    # Always an attachment: nothing uploaded is ever rendered inside this origin.
    return FileResponse(candidate, filename=candidate.name, content_disposition_type="attachment")


async def refused(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, Refusal)
    return _page(
        request,
        "refused.html",
        exc.status,
        kind=exc.kind,
        message=str(exc),
        hint=HINTS.get(exc.kind),
    )


class SecurityHeaders:
    """Adds `SECURITY_HEADERS` to every response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                names = {k.lower() for k, _ in message.get("headers", [])}
                message["headers"] = list(message.get("headers", [])) + [
                    (k, v) for k, v in SECURITY_HEADERS if k not in names
                ]
            await send(message)

        await self.app(scope, receive, with_headers)


#: The cookie that carries the access token once it has been presented.
TOKEN_COOKIE: Final = "dobladillo_token"

_UNAUTHORISED: Final = (
    b"<!doctype html><html lang=en><meta charset=utf-8>"
    b"<meta name=viewport content='width=device-width, initial-scale=1'>"
    b"<title>Access token needed</title><h1>Access token needed</h1>"
    b"<p>This dobladillo web UI is reachable from the network, so it answers only to "
    b"the link it printed when it started, the one ending in <code>?token=</code>. "
    b"Open that link on this device.</p></html>"
)


class AccessToken:
    """Every request must carry the token: once in `?token=`, then as a cookie.

    Only when the server listens beyond loopback. The token is accepted from
    the query string, and the response sets it as an HttpOnly, SameSite=Strict
    cookie, so the pages after it need no token in their links and no other
    site can send it along. Without a valid token the answer is a 401 page
    that carries no data.
    """

    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app = app
        self.token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        offered = request.query_params.get("token")
        from_query = offered is not None and _same(offered, self.token)
        cookie = request.cookies.get(TOKEN_COOKIE)
        from_cookie = cookie is not None and _same(cookie, self.token)
        if not (from_query or from_cookie):
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        (b"content-type", b"text/html; charset=utf-8"),
                        (b"content-length", str(len(_UNAUTHORISED)).encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": _UNAUTHORISED})
            return
        if not from_query or from_cookie:
            await self.app(scope, receive, send)
            return
        cookie_header = f"{TOKEN_COOKIE}={self.token}; Path=/; HttpOnly; SameSite=Strict".encode()

        async def set_cookie(message: Message) -> None:
            if message["type"] == "http.response.start":
                message["headers"] = [*message.get("headers", []), (b"set-cookie", cookie_header)]
            await send(message)

        await self.app(scope, receive, set_cookie)


def create_app(
    root: Path,
    *,
    allowed_hosts: tuple[str, ...] = LOOPBACK_HOSTS,
    max_upload: int = MAX_UPLOAD_BYTES,
    access_token: str | None = None,
) -> Starlette:
    """The application. `root` bounds every experiment folder it will touch.

    `access_token` is required of every request when given: `serve` gives one
    whenever it listens beyond loopback.
    """
    site = Site(
        root=root.resolve(),
        csrf=secrets.token_urlsafe(32),
        max_upload=max_upload,
        exposed=access_token is not None,
    )
    folder = "/e/{name}"
    middleware = [
        Middleware(SecurityHeaders),
        Middleware(TrustedHostMiddleware, allowed_hosts=list(allowed_hosts)),
    ]
    if access_token is not None:
        middleware.append(Middleware(AccessToken, token=access_token))
    app = Starlette(
        routes=[
            Route("/", home),
            Route("/new", new_form, methods=["GET"]),
            Route("/new", new_submit, methods=["POST"]),
            Route(folder, experiment),
            Route(folder + "/criterion", criterion, methods=["POST"]),
            Route(folder + "/lock", lock, methods=["POST"]),
            Route(folder + "/log", log, methods=["POST"]),
            Route(folder + "/record", record, methods=["POST"]),
            Route(folder + "/upload", upload, methods=["POST"]),
            Route(folder + "/commit", commit, methods=["POST"]),
            Route(folder + "/analyse", analyse, methods=["POST"]),
            Route(folder + "/files/{path:path}", download),
            Mount("/static", StaticFiles(directory=HERE / "static"), name="static"),
        ],
        middleware=middleware,
        exception_handlers={Refusal: refused},
    )
    app.state.site = site
    return app


@dataclass(frozen=True)
class Serving:
    """How `serve` will listen, decided before it does: testable without a socket."""

    host: str
    port: int
    #: None on loopback; otherwise every request needs it.
    token: str | None
    allowed_hosts: tuple[str, ...]
    urls: tuple[str, ...]

    @property
    def exposed(self) -> bool:
        return self.token is not None


def plan(host: str, port: int) -> Serving:
    """Loopback needs nothing more. Any other address gets a fresh access token,
    answers to this machine's addresses, and prints a URL per address."""
    from dobladillo.web.addresses import is_loopback, local_ipv4

    if is_loopback(host):
        shown = "127.0.0.1" if host == "localhost" else host
        return Serving(host, port, None, LOOPBACK_HOSTS, (f"http://{shown}:{port}/",))
    token = secrets.token_urlsafe(24)
    addresses = local_ipv4() if host in ("0.0.0.0", "") else [host]
    names = (*LOOPBACK_HOSTS, *addresses)
    urls = tuple(f"http://{a}:{port}/?token={token}" for a in (*addresses, "127.0.0.1"))
    return Serving(host, port, token, names, urls)


def serve(root: Path, *, port: int, host: str = "127.0.0.1") -> None:
    """Serve until interrupted: on 127.0.0.1 by default; elsewhere only behind a token."""
    import sys

    import uvicorn

    how = plan(host, port)
    app = create_app(root, allowed_hosts=how.allowed_hosts, access_token=how.token)
    if how.exposed:
        print(
            f"WARNING: dobladillo web is listening on {host}:{port} and is reachable from "
            "the network.\nAnyone with the link below can read these experiments and write "
            "their record (gates, readings, raw data, commits).\nUse it on a network you "
            "trust, and stop it with Ctrl-C when you are done.\n",
            file=sys.stderr,
        )
        for url in how.urls:
            print(f"  {url}", file=sys.stderr)
    else:
        print(f"dobladillo web: {how.urls[0]}  (Ctrl-C stops it)", file=sys.stderr)
    uvicorn.run(app, host=host, port=port, log_level="warning", server_header=False)
