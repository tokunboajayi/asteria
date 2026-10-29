"""API acceptance tests for Asteria.

Run against a live API:  API_URL=http://127.0.0.1:8000 \
    ASTERIA_SOURCE_DIR=<pinned RocketPy checkout> pytest gan-harness/acceptance

These tests deliberately do not import the engine. Anything they check
against the published sources is recomputed here, independently, from the
raw files.
"""

from __future__ import annotations

import csv
import json
import os
import re
import statistics
from pathlib import Path
from typing import Any

import httpx
import pytest

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000").rstrip("/")
# Unset means "not available" (Path("") would silently mean the current folder).
SOURCE_DIR = (
    Path(os.environ["ASTERIA_SOURCE_DIR"]) if os.environ.get("ASTERIA_SOURCE_DIR") else None
)
HAVE_SOURCE = SOURCE_DIR is not None and SOURCE_DIR.is_dir()
PINNED_COMMIT = "9bd6ad3af8f97bafa3201d4e70eba2877e66e040"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
NUMBER = re.compile(r"[-−+]?\d[\d,]*(?:\.\d+)?")
FT_TO_M = 0.3048


@pytest.fixture(scope="session")
def client() -> httpx.Client:
    with httpx.Client(base_url=API_URL, timeout=30.0) as c:
        yield c


@pytest.fixture(scope="session")
def fleet(client: httpx.Client) -> dict[str, Any]:
    r = client.get("/api/rockets/fleet")
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="session")
def details(client: httpx.Client, fleet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out = {}
    for f in fleet["flights"]:
        r = client.get(f"/api/rockets/flights/{f['id']}")
        assert r.status_code == 200, r.text
        out[f["id"]] = r.json()
    return out


# 1 ------------------------------------------------------------------------
def test_health_and_fleet_size(client: httpx.Client, fleet: dict[str, Any]) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["rocket_flights"] == len(fleet["flights"])
    assert len(fleet["flights"]) >= 8, "expected at least 8 real flights in the fleet"
    ids = [f["id"] for f in fleet["flights"]]
    assert len(ids) == len(set(ids)), "flight ids must be unique"


# 2 ------------------------------------------------------------------------
def test_provenance_is_pinned_and_hashed(
    fleet: dict[str, Any], details: dict[str, dict[str, Any]]
) -> None:
    assert fleet["provenance"]["commit"] == PINNED_COMMIT
    for fid, d in details.items():
        files = d["provenance"]["files"]
        assert files, f"{fid}: no source files recorded"
        for entry in files:
            assert SHA256.match(entry["sha256"]), f"{fid}: bad sha256 for {entry['path']}"
            if HAVE_SOURCE:
                assert SOURCE_DIR is not None
                import hashlib

                actual = hashlib.sha256((SOURCE_DIR / entry["path"]).read_bytes()).hexdigest()
                assert actual == entry["sha256"], f"{fid}: hash mismatch for {entry['path']}"


# 3 ------------------------------------------------------------------------
def _read_raw_altitude_max(
    path: Path, time_column: str, column: str, unit: str, delimiter: str, keep_until: float | None
) -> float:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh, delimiter=delimiter)
        header = next(reader)
        ti, ai = header.index(time_column), header.index(column)
        values = []
        for row in reader:
            try:
                t, a = float(row[ti]), float(row[ai])
            except (IndexError, ValueError):
                continue
            if keep_until is not None and t > keep_until:
                continue
            values.append(a)
    assert values, f"no numeric values in {path}:{column}"
    peak = max(values)
    if unit == "ft":
        return peak * FT_TO_M
    assert unit == "m", f"unexpected unit {unit}"
    return peak


@pytest.mark.skipif(not HAVE_SOURCE, reason="ASTERIA_SOURCE_DIR not set")
def test_real_apogee_matches_raw_published_log(details: dict[str, dict[str, Any]]) -> None:
    for fid, d in details.items():
        raw = d["real"]["raw_source"]
        if raw["keep_until_s"] is not None:
            assert raw["keep_until_reason"], f"{fid}: cutoff without a written reason"
        expected = _read_raw_altitude_max(
            SOURCE_DIR / raw["path"],
            raw["time_column"],
            raw["altitude_column"],
            raw["altitude_unit"],
            raw["delimiter"],
            raw["keep_until_s"],
        )
        assert d["summary"]["apogee"]["real_m"] == pytest.approx(expected, abs=0.01), fid


# 4 ------------------------------------------------------------------------
def test_delta_only_on_overlap_and_equals_real_minus_ghost(
    details: dict[str, dict[str, Any]],
) -> None:
    for fid, d in details.items():
        t = d["delta"]["t"]
        dz = d["delta"]["altitude"]
        ghost_z = d["delta"]["ghost_altitude"]
        real_z = d["delta"]["real_altitude"]
        shift = d["delta"]["real_time_shift_s"]
        t_real = d["real"]["t"]
        lo, hi = min(t_real) + shift, max(t_real) + shift
        assert len(t) == len(dz) == len(ghost_z) == len(real_z)
        for ti, di, gi, ri in zip(t, dz, ghost_z, real_z):
            if ti < lo or ti > hi:
                assert di is None and ri is None, f"{fid}: delta extrapolated at t={ti}"
            elif di is not None:
                assert di == pytest.approx(ri - gi, abs=1e-6), (
                    f"{fid}: delta != real-ghost at t={ti}"
                )


# 5 ------------------------------------------------------------------------
@pytest.mark.skipif(not HAVE_SOURCE, reason="ASTERIA_SOURCE_DIR not set")
def test_team_prediction_quoted_verbatim_from_notebook(details: dict[str, dict[str, Any]]) -> None:
    checked = 0
    for fid, d in details.items():
        tp = d["summary"]["team_prediction"]
        if tp is None:
            continue
        nb = json.loads((SOURCE_DIR / d["provenance"]["notebook"]).read_text(encoding="utf-8"))
        text = "\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "markdown")
        assert tp["quote"] in text, f"{fid}: team prediction quote not found in notebook"
        assert NUMBER.search(tp["quote"].replace(",", "")), f"{fid}: quote carries no number"
        # Only an explicitly pre-flight number may be called the team's prediction;
        # several notebooks list RocketPy's own post-flight result as "Simulated apogee".
        assert re.search(r"before flight|last simulated", tp["quote"], re.IGNORECASE), (
            f"{fid}: quote is not explicitly a pre-flight prediction: {tp['quote']!r}"
        )
        checked += 1
    assert checked >= 3, "expected pre-flight team predictions for at least 3 flights"


# 6 ------------------------------------------------------------------------
def test_correction_is_leave_one_flight_out(client: httpx.Client) -> None:
    r = client.get("/api/rockets/correction")
    assert r.status_code == 200
    rep = r.json()
    lo, hi = rep["clip"]
    per = {p["id"]: p for p in rep["per_flight"]}
    assert len(per) >= 8
    for fid, p in per.items():
        others = [q["k_own"] for qid, q in per.items() if qid != fid]
        expected = min(max(statistics.median(others), lo), hi)
        assert p["k_hat"] == pytest.approx(expected, abs=1e-9), (
            f"{fid}: k_hat is not the held-out median"
        )
    agg = rep["aggregate"]
    before = statistics.median(abs(p["err_before_pct"]) for p in per.values())
    after = statistics.median(abs(p["err_after_pct"]) for p in per.values())
    assert agg["median_abs_err_before_pct"] == pytest.approx(before, abs=1e-9)
    assert agg["median_abs_err_after_pct"] == pytest.approx(after, abs=1e-9)


# 7 ------------------------------------------------------------------------
def test_gap_map_marks_uncharted_cells(client: httpx.Client) -> None:
    r = client.get("/api/rockets/gapmap")
    assert r.status_code == 200
    gm = r.json()
    total = 0
    uncharted = 0
    for c in gm["cells"]:
        total += c["n_samples"]
        if c["n_flights"] < gm["min_flights"]:
            assert c["charted"] is False and c["mean"] is None, c
            uncharted += 1
        else:
            assert c["charted"] is True and c["mean"] is not None, c
    assert total == gm["total_samples"]
    assert uncharted > 0, "a real fleet should leave part of the envelope uncharted"


# 8 ------------------------------------------------------------------------
def test_debrief_numbers_all_come_from_cited_facts(
    client: httpx.Client, fleet: dict[str, Any]
) -> None:
    for f in fleet["flights"]:
        r = client.get(f"/api/rockets/flights/{f['id']}/debrief")
        assert r.status_code == 200
        db = r.json()
        facts = {fa["id"]: fa for fa in db["facts"]}
        assert db["sentences"], f"{f['id']}: empty debrief"
        assert db["validation"]["passed"] is True
        for s in db["sentences"]:
            assert s["fact_ids"], f"{f['id']}: sentence without citation: {s['text']}"
            allowed = set()
            for fid in s["fact_ids"]:
                assert fid in facts, f"{f['id']}: cites missing fact {fid}"
                allowed.update(NUMBER.findall(facts[fid]["display"]))
                allowed.update(NUMBER.findall(facts[fid]["label"]))
            for num in NUMBER.findall(s["text"]):
                assert num in allowed, f"{f['id']}: number {num!r} not in cited facts: {s['text']}"


# 13 -----------------------------------------------------------------------
# Storm Ghost. Skipped until orbit artifacts exist (they need a Space-Track login).
SPACETRACK_FILE = (
    Path(os.environ["ASTERIA_SPACETRACK_FILE"])
    if os.environ.get("ASTERIA_SPACETRACK_FILE")
    else None
)


def _interp(xs: list[float], ys: list[float], x: float) -> float:
    for i in range(1, len(xs)):
        if xs[i] >= x:
            f = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
            return ys[i - 1] + f * (ys[i] - ys[i - 1])
    return ys[-1]


def test_event_timing_is_self_consistent_and_never_shows_transonic_altitude(
    details: dict[str, dict[str, Any]],
) -> None:
    for fid, d in details.items():
        shift = d["delta"]["real_time_shift_s"]
        g = d["ghost"]
        for e in d["timing"]["events"]:
            where = f"{fid}/{e['key']}"
            if e["status"] == "detected":
                assert e["real_t"] is not None, where
                assert e["delta_t_s"] == pytest.approx(e["real_t"] - e["ghost_t"], abs=2e-3), where
                mach = _interp(g["t"], g["mach"], e["real_t"])
                if 0.8 <= mach <= 1.2:
                    shown = e["real_altitude_m"]
                    assert shown is None, f"{where}: altitude shown at Mach {mach:.2f}"
            else:
                assert e["real_t"] is None and e["note"], f"{where}: not detected without a reason"
        apogee = next(e for e in d["timing"]["events"] if e["key"] == "apogee")
        assert apogee["real_t"] - shift == pytest.approx(
            d["summary"]["apogee"]["real_time_s"], abs=0.01
        ), fid


def test_fingerprint_only_from_verified_accelerometers(
    client: httpx.Client, details: dict[str, dict[str, Any]]
) -> None:
    fp = client.get("/api/rockets/fingerprint").json()
    rows = {r["id"]: r for r in fp["rows"]}
    assert set(rows) == set(details)
    assert "rejected" in fp["not_attempted"]
    for fid, d in details.items():
        f = rows[fid]["fingerprint"]
        has_accel = "accel_logged" in d["real"]["channels"]
        verified = (d["timing"]["accelerometer"] or "").startswith("Gravity")
        if f["status"] == "measured":
            assert has_accel and verified, fid
            assert f["burn_ratio"] == pytest.approx(
                f["burn_gain_real_mps"] / f["burn_gain_ghost_mps"], rel=2e-3
            ), fid
            assert f["coast_drag_ratio"] == pytest.approx(
                f["coast_decel_real_mps2"] / f["coast_decel_ghost_mps2"], rel=2e-3
            ), fid
        else:
            assert f["reason"], fid
        assert d["fingerprint"] == f, f"{fid}: flight and fleet fingerprints differ"


def _orbits_or_skip(client: httpx.Client) -> dict[str, Any]:
    status = client.get("/api/orbits/status").json()
    if not status["available"]:
        pytest.skip("orbit artifacts not built (needs a Space-Track login)")
    r = client.get("/api/orbits/fleet")
    assert r.status_code == 200, r.text
    return r.json()


def test_orbit_gaps_recomputed_independently_from_raw_element_sets(client: httpx.Client) -> None:
    """Re-derive every published gap with SGP4 straight from the raw Space-Track file."""
    fleet = _orbits_or_skip(client)
    if SPACETRACK_FILE is None or not SPACETRACK_FILE.is_file():
        pytest.skip("ASTERIA_SPACETRACK_FILE not set")
    import hashlib
    from datetime import UTC, datetime

    import numpy as np
    from sgp4.api import WGS72, Satrec, jday

    raw = SPACETRACK_FILE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == fleet["provenance"]["spacetrack_sha256"]
    records = json.loads(raw)

    def when(text: str) -> datetime:
        t = datetime.fromisoformat(text.replace("Z", ""))
        return t.replace(tzinfo=UTC) if t.tzinfo is None else t

    def rv(l1: str, l2: str, t: datetime) -> tuple[np.ndarray, np.ndarray]:
        sat = Satrec.twoline2rv(l1, l2, WGS72)
        jd, fr = jday(t.year, t.month, t.day, t.hour, t.minute, t.second + t.microsecond / 1e6)
        err, r, v = sat.sgp4(jd, fr)
        assert err == 0
        return np.array(r), np.array(v)

    checked = 0
    for obj in fleet["objects"]:
        series = obj["storm"]
        if series is None:
            continue
        # Space-Track re-issues fits under the same epoch; the latest issue supersedes.
        latest: dict[datetime, dict[str, Any]] = {}
        for r in records:
            if int(r["NORAD_CAT_ID"]) != obj["norad_id"]:
                continue
            key = when(r["EPOCH"]).replace(microsecond=0)
            issued = (when(r["CREATION_DATE"]), int(r["GP_ID"]))
            if key not in latest or issued > (
                when(latest[key]["CREATION_DATE"]),
                int(latest[key]["GP_ID"]),
            ):
                latest[key] = r
        sets = sorted(latest.values(), key=lambda r: when(r["EPOCH"]))
        assert len(set(series["epochs"])) == len(series["epochs"]), (
            f"{obj['name']}: repeated epochs"
        )
        base = [s for s in sets if when(s["EPOCH"]) < when(fleet["storm"]["onset"])][-1]
        by_epoch = {when(s["EPOCH"]).replace(microsecond=0): s for s in sets}
        for epoch, it in zip(series["epochs"], series["in_track_km"]):
            t_key = when(epoch)
            tracked = by_epoch[t_key]
            t_exact = when(tracked["EPOCH"])
            rg, vg = rv(base["TLE_LINE1"], base["TLE_LINE2"], t_exact)
            rt, _ = rv(tracked["TLE_LINE1"], tracked["TLE_LINE2"], t_exact)
            radial = rg / np.linalg.norm(rg)
            cross = np.cross(rg, vg) / np.linalg.norm(np.cross(rg, vg))
            in_track = float((rt - rg) @ np.cross(cross, radial))
            assert it == pytest.approx(in_track, abs=1e-3), f"{obj['name']} at {epoch}"
            checked += 1
    assert checked > 0, "no orbit gaps were published"


def test_orbit_gap_map_marks_uncharted_cells(client: httpx.Client) -> None:
    _orbits_or_skip(client)
    gm = client.get("/api/orbits/gapmap").json()
    for c in gm["cells"]:
        if c["n_flights"] < gm["min_flights"]:
            assert c["charted"] is False and c["mean"] is None, c
