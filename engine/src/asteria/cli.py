"""Command line: `asteria fetch | build | verify | serve`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from asteria.config import paths
from asteria.provenance import sha256_file


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


def _verify() -> int:
    """Re-hash every artifact against its manifest."""
    from asteria.sources import rocketpy_repo

    rocketpy_repo.verify(paths().rocketpy_checkout)
    root = paths().rockets_artifacts
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    bad = [rel for rel, digest in manifest["files"].items() if sha256_file(root / rel) != digest]
    for rel in bad:
        print(f"MISMATCH {rel}", file=sys.stderr)
    print(f"{len(manifest['files']) - len(bad)}/{len(manifest['files'])} artifacts verified")
    return 1 if bad else 0


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
    sub.add_parser("verify", help="re-check source commit and artifact hashes")
    s = sub.add_parser("serve", help="run the API")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    if args.command == "fetch":
        _fetch()
    elif args.command == "build":
        _build(args)
    elif args.command == "verify":
        return _verify()
    elif args.command == "serve":
        _serve(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
