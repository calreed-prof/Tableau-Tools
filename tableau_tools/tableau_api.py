"""Minimal Tableau REST API client for reading published datasources."""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from typing import Callable

from lxml import etree

_API_VERSION = "3.19"
_TIMEOUT = 30  # seconds; applied to every urlopen call so a hung server can't wedge the CLI


def _url(server: str, path: str) -> str:
    host = server.rstrip("/").removeprefix("https://").removeprefix("http://")
    return f"https://{host}/api/{_API_VERSION}/{path}"


def sign_in(server: str, site: str, pat_name: str, pat_secret: str) -> tuple[str, str]:
    """Authenticate with a PAT. Returns (auth_token, site_id)."""
    body = json.dumps({
        "credentials": {
            "personalAccessTokenName": pat_name,
            "personalAccessTokenSecret": pat_secret,
            "site": {"contentUrl": site},
        }
    }).encode()
    req = urllib.request.Request(
        _url(server, "auth/signin"),
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Sign-in failed ({exc.code}): {exc.read().decode(errors='replace')}") from exc
    creds = data["credentials"]
    return creds["token"], creds["site"]["id"]


def sign_out(server: str, token: str) -> None:
    req = urllib.request.Request(
        _url(server, "auth/signout"),
        data=b"",
        method="POST",
        headers={"X-Tableau-Auth": token},
    )
    try:
        urllib.request.urlopen(req, timeout=_TIMEOUT)
    except Exception:
        pass  # best-effort


def find_datasource_id(server: str, token: str, site_id: str, name: str) -> str | None:
    """Search for a published datasource by name; return its ID or None."""
    quoted = urllib.parse.quote(name)
    req = urllib.request.Request(
        _url(server, f"sites/{site_id}/datasources?filter=name:eq:{quoted}"),
        headers={"X-Tableau-Auth": token, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Datasource lookup failed ({exc.code}): {exc.read().decode(errors='replace')}") from exc
    items = data.get("datasources", {}).get("datasource", [])
    return items[0]["id"] if items else None


def download_datasource_xml(
    server: str,
    token: str,
    site_id: str,
    ds_id: str,
    progress_cb: Callable[[int, int | None], None] | None = None,
) -> etree._Element:
    """Download a published datasource and return its parsed XML root.

    progress_cb, if given, is called as progress_cb(downloaded_bytes, total_or_None)
    after each chunk. Total may be None when the server omits Content-Length.
    """
    req = urllib.request.Request(
        _url(server, f"sites/{site_id}/datasources/{ds_id}/content"),
        headers={"X-Tableau-Auth": token},
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            total_header = resp.headers.get("Content-Length")
            total = int(total_header) if total_header and total_header.isdigit() else None
            chunks: list[bytes] = []
            downloaded = 0
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
                downloaded += len(chunk)
                if progress_cb is not None:
                    progress_cb(downloaded, total)
            raw = b"".join(chunks)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Download failed ({exc.code}): {exc.read().decode(errors='replace')}") from exc

    if raw[:2] == b"PK":  # ZIP / .tdsx
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            tds_name = next((n for n in zf.namelist() if n.endswith(".tds")), None)
            if tds_name is None:
                raise RuntimeError("Downloaded .tdsx contains no .tds file.")
            tds_bytes = zf.read(tds_name)
    else:
        tds_bytes = raw

    parser = etree.XMLParser(strip_cdata=False, resolve_entities=False, remove_blank_text=False)
    return etree.fromstring(tds_bytes, parser)
