"""Command line: `asteria fetch | build | verify | serve`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from asteria.artifacts import ArtifactError, verified
from asteria.config import paths


def _fetch() -> Path:
    from asteria.sources import rocketpy_repo

    checkout = rocketpy_repo.ensure_checkout(paths().rocketpy_checkout)
    print(f"source ready: {checkout} @ {rocketpy_repo.head_commit(checkout)}")
    return checkout


def _build(args: argparse.Namespace) -> None:
    from asteria.rockets.build import build

    checkout = _fetch()
    out = build(checkout, paths().rockets_artifacts, jobs=args.jobs, only=args.only or None)
    print(f"artifacts written: {out}")


def _build_orbits() -> None:
    from asteria.config import env_files
    from asteria.orbits.build import build

    out = build(paths(), env_files())
    print(f"orbit artifacts written: {out}")


def _verify_dir(label: str, root: Path) -> int:
    """Re-hash one artifacts directory against its manifest; 1 if it fails, else 0."""
    try:
        files = verified(root)["files"]
    except (ArtifactError, OSError, ValueError) as exc:
        print(f"{label}: {exc}", file=sys.stderr)
        return 1
    print(f"{label}: {len(files)}/{len(files)} artifacts verified")  # type: ignore[arg-type]
    return 0


def _verify() -> int:
    """Re-check the pinned source checkout and re-hash every built artifact."""
    from asteria.sources import rocketpy_repo

    bad = 0
    try:
        rocketpy_repo.verify(paths().rocketpy_checkout)
    except rocketpy_repo.SourceIntegrityError as exc:
        print(f"source: {exc}; run `asteria fetch`", file=sys.stderr)
        bad = 1
    bad += _verify_dir("rockets", paths().rockets_artifacts)
    orbits = paths().orbits_artifacts
    if (orbits / "manifest.json").is_file():
        bad += _verify_dir("orbits", orbits)
    else:
        print("orbits: not built (needs a Space-Track login)")
    return 1 if bad else 0


def _openapi(out: Path) -> None:
    """Write the API's OpenAPI schema; the web console generates its types from it."""
    from asteria.api.app import app

    out.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"openapi schema written: {out}")


def _serve(args: argparse.Namespace) -> None:
    import uvicorn

    uvicorn.run("asteria.api.app:app", host=args.host, port=args.port, log_level="info")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="asteria")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("fetch", help="fetch the pinned RocketPy sources")
    b = sub.add_parser("build", help="build the Rockets artifacts")
    b.add_argument("--jobs", type=int, default=2)
    b.add_argument("--only", nargs="*", help="flight ids (default: the whole fleet)")
    sub.add_parser("build-orbits", help="build Storm Ghost (needs a Space-Track login)")
    sub.add_parser("verify", help="re-check source commit and artifact hashes")
    s = sub.add_parser("serve", help="run the API")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    o = sub.add_parser("openapi", help="write the API schema used to generate web types")
    o.add_argument("--out", type=Path, default=Path("openapi.json"))
    args = parser.parse_args(argv)
    if args.command == "fetch":
        _fetch()
    elif args.command == "build":
        _build(args)
    elif args.command == "build-orbits":
        _build_orbits()
    elif args.command == "verify":
        return _verify()
    elif args.command == "serve":
        _serve(args)
    elif args.command == "openapi":
        _openapi(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
