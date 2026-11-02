"""Write the API's GET responses as files: the public demo's data (`asteria export-static`).

Every file is produced by calling the real API (FastAPI's test client), so the demo
serves byte-for-byte what a running engine would. Paths mirror the API with an
extension: /api/rockets/fleet -> api/rockets/fleet.json.

Orbits are never exported: Space-Track's user agreement does not allow
redistributing its data, so the demo's status file says so and points to a
local run. The orbit artifacts are not even loaded.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

ORBITS_NOT_IN_DEMO = (
    "Not in the public demo: Storm Ghost is built from Space-Track.org element sets, and "
    "Space-Track's user agreement does not allow redistributing its data. Run Asteria "
    "locally with your own free Space-Track login to see it."
)


def _write(out: Path, rel: str, body: bytes) -> None:
    path = out / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)


def export(out: Path) -> list[str]:
    """Export the rocket API, the readiness files and an orbits-unavailable status."""
    from fastapi.testclient import TestClient

    os.environ["ASTERIA_ORBITS_ARTIFACTS"] = str(out / ".no-orbits-in-demo")
    from asteria.api.app import app

    written: list[str] = []

    with TestClient(app) as client:

        def get(path: str, ext: str = ".json") -> bytes:
            r = client.get(path)
            if r.status_code != 200:
                raise RuntimeError(f"{path} -> HTTP {r.status_code}: {r.text[:200]}")
            body: bytes = r.content
            _write(out, path.lstrip("/") + ext, body)
            written.append(path + ext)
            return body

        health = json.loads(get("/health"))
        if not health["ok"]:
            raise RuntimeError(f"rocket artifacts did not load: {health.get('detail')}")
        get("/ready")
        fleet = json.loads(get("/api/rockets/fleet"))
        for path in (
            "/api/rockets/gapmap",
            "/api/rockets/correction",
            "/api/rockets/nextbest",
            "/api/rockets/fingerprint",
            "/api/rockets/manifest",
        ):
            get(path)
        for f in fleet["flights"]:
            fid = f["id"]
            get(f"/api/rockets/flights/{fid}")
            get(f"/api/rockets/flights/{fid}/debrief")
            if client.get(f"/api/export/oem/rocket/{fid}").status_code == 200:
                get(f"/api/export/oem/rocket/{fid}", ".oem")
        dictionary = json.loads(get("/api/openmct/dictionary.json", ""))
        for m in dictionary["measurements"]:
            get(f"/api/openmct/telemetry/{m['key']}")

    status = {"available": False, "reason": ORBITS_NOT_IN_DEMO}
    _write(out, "api/orbits/status.json", json.dumps(status).encode())
    written.append("/api/orbits/status.json")
    return written
