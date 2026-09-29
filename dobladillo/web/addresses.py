"""This machine's own IPv4 addresses, to print the URLs a phone on the LAN can open.

The one module in the package that imports `socket`, and it never sends a
packet: a UDP socket that is `connect`ed only asks the routing table which
interface would be used. The other addresses are read from the interface
list the operating system prints (`ifconfig`, or `ip` on Linux), not looked
up by name. `tests/test_licences.py` allows this file, and only this file,
the import.
"""

from __future__ import annotations

import ipaddress
import re
import socket
import subprocess

_INET = re.compile(r"\binet (?:addr:)?(\d+\.\d+\.\d+\.\d+)")


def _listed() -> list[str]:
    for command in (["ifconfig"], ["ip", "-4", "-o", "addr", "show"]):
        try:
            out = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
                stdin=subprocess.DEVNULL,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if out.returncode == 0:
            return _INET.findall(out.stdout)
    return []


def _usable(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return ip.version == 4 and not (ip.is_loopback or ip.is_link_local or ip.is_unspecified)


def local_ipv4() -> list[str]:
    """Non-loopback IPv4 addresses of this machine, primary first. May be empty."""
    found: list[str] = []
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # No packet leaves: connect() on UDP only selects a route. 10.255.255.255
        # is a private address, so no real host is even named.
        probe.connect(("10.255.255.255", 1))
        found.append(probe.getsockname()[0])
    except OSError:
        pass
    finally:
        probe.close()
    found += _listed()
    out: list[str] = []
    for address in found:
        if _usable(address) and address not in out:
            out.append(address)
    return out


def is_loopback(host: str) -> bool:
    """Whether binding `host` keeps the server on this machine."""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False
