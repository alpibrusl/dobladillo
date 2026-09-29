"""The local web UI (`dobladillo web`). Needs the optional `web` extra.

See `dobladillo.web.app` for what it does, what it will not do, and why.
"""

from dobladillo.web.app import create_app, serve

__all__ = ["create_app", "serve"]
