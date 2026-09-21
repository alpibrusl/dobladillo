"""A dashboard generated from the toolchain, so it cannot go stale."""

from dobladillo.dashboard.render import render
from dobladillo.dashboard.state import State, gather

__all__ = ["State", "gather", "render"]
