"""Historical element sets from Space-Track.org (US Space Force, 18th/19th SDS).

Needs a free account: SPACETRACK_USER and SPACETRACK_PASSWORD, from the
environment or engine/.env.local. The password is only ever sent to
Space-Track's login endpoint; it is never logged or written anywhere.

Space-Track's user agreement forbids redistributing its data, so raw
responses stay in the local cache (.asteria/, git-ignored) and are never
committed or published.

One query fetches every object's history (Space-Track asks for under 30
requests a minute and 300 an hour; a build makes one, plus the login).
"""

from __future__ import annotations

import hashlib
import http.cookiejar
import json
import os
import urllib.parse
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from asteria.provenance import sha256_file

BASE = "https://www.space-track.org"
LOGIN = f"{BASE}/ajaxauth/login"


class CredentialsMissing(RuntimeError):
    """No Space-Track login available."""


@dataclass(frozen=True)
class Credentials:
    user: str
    password: str

    def __repr__(self) -> str:  # never print the password
        return f"Credentials(user={self.user!r}, password=***)"


@dataclass(frozen=True)
class HistoryFile:
    query_url: str
    path: Path
    sha256: str
    downloaded_at: str
    records: list[dict[str, Any]]


def _dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def credentials(env_file: Path) -> Credentials:
    """Environment first, then `env_file`; raise CredentialsMissing if neither has both."""
    file_values = _dotenv(env_file)
    user = os.environ.get("SPACETRACK_USER") or file_values.get("SPACETRACK_USER", "")
    password = os.environ.get("SPACETRACK_PASSWORD") or file_values.get("SPACETRACK_PASSWORD", "")
    if not user or not password:
        raise CredentialsMissing(
            "Space-Track login not found: set SPACETRACK_USER and SPACETRACK_PASSWORD "
            f"in the environment or in {env_file}"
        )
    return Credentials(user, password)


def history_url(norad_ids: Sequence[int], start: datetime, end: datetime) -> str:
    ids = ",".join(str(i) for i in sorted(norad_ids))
    span = f"{start:%Y-%m-%d}--{end:%Y-%m-%d}"
    return (
        f"{BASE}/basicspacedata/query/class/gp_history/NORAD_CAT_ID/{ids}"
        f"/EPOCH/{span}/orderby/NORAD_CAT_ID,EPOCH asc/format/json"
    ).replace(" ", "%20")


def _download(url: str, creds: Credentials) -> bytes:
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    body = urllib.parse.urlencode({"identity": creds.user, "password": creds.password}).encode()
    with opener.open(urllib.request.Request(LOGIN, data=body, method="POST"), timeout=60) as r:
        reply = r.read().decode("utf-8", "replace")
    if "Failed" in reply or not any(c.name == "chocolatechip" for c in jar):
        raise PermissionError(
            "Space-Track login failed: check SPACETRACK_USER / SPACETRACK_PASSWORD"
        )
    with opener.open(url, timeout=300) as r:
        return bytes(r.read())


def fetch_history(
    cache: Path, norad_ids: Sequence[int], start: datetime, end: datetime, env_file: Path
) -> HistoryFile:
    """Element-set history for `norad_ids` in [start, end], cached by query."""
    url = history_url(norad_ids, start, end)
    key = hashlib.sha256(url.encode()).hexdigest()[:16]
    path = cache / f"gp_history_{key}.json"
    meta = cache / f"gp_history_{key}.meta.json"
    if not path.is_file() or not meta.is_file():
        payload = _download(url, credentials(env_file))
        records = json.loads(payload)
        if not isinstance(records, list):
            raise ValueError(f"Space-Track returned {type(records).__name__}, expected a list")
        cache.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        stamp = datetime.now(UTC).replace(microsecond=0).isoformat()
        meta.write_text(json.dumps({"url": url, "downloaded_at": stamp}), encoding="utf-8")
    info = json.loads(meta.read_text(encoding="utf-8"))
    return HistoryFile(
        query_url=url,
        path=path,
        sha256=sha256_file(path),
        downloaded_at=info["downloaded_at"],
        records=json.loads(path.read_text(encoding="utf-8")),
    )
