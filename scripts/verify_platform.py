#!/usr/bin/env python3
"""
The `platform` gate: prevents committing invented platform literals.

## Why it exists

A platform literal such as a `$schema` URL or a connection string is easy to
invent by analogy with another one seen before, and the result looks correct
until the tool rejects it. Three typical ways this happens:

1. The `$schema` of a project file: writing a path segment that looks plausible
   when the real one is different. The desktop tool rejects it with an error
   dialog.
2. The `$schema` of a report definition: writing the wrong version number, which
   is valid-looking and wrong.
3. A connection string written by hand, when the real one emitted by the tool
   carries several more keys.

Principle 6 already forbids this: statements about the platform need official
documentation that was actually read. Writing that down is not enough if nothing
checks it. All three cases are resolved the same way -- by copying from a real
artifact that already exists, or by resolving the URL -- and both of those can be
mechanized, which is what this does.

## What it does

Over what is about to be committed, or over the whole tree with `--all`, it finds
platform literals and requires each one to satisfy ONE of two conditions:

  a) **Precedent**: the same literal already appears in a committed file of the
     repository. If the tool wrote it before, it is real.
  b) **Resolvable**: if it is a URL, it answers HTTP 200.

A literal that satisfies neither is not verified: it is an analogy.

## What it does NOT do

It does not validate semantics. A schema URL can exist and still be the wrong one
for that file type. Catching that is the vendor validator's job. This gate
catches what was invented, not what was badly chosen.

Usage
-----
  python verify_platform.py            # over the staged diff
  python verify_platform.py --all      # over the whole tracked tree
  python verify_platform.py --offline  # precedent only, without resolving URLs

Exit: 0 if everything verifies and a receipt is issued, 1 if there are
unverified literals, 2 if the inputs are wrong.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from faw import receipts  # noqa: E402

# Platform literals that get invented by analogy. Each pattern comes from an
# observed mistake, not from imagining what could go wrong.
PATTERNS = {
    "schema-url": re.compile(r'https://developer\.microsoft\.com/json-schemas/[^\s"\'<>]+'),
    "expression-source": re.compile(r"DirectLake\s*-\s*[A-Za-z0-9_]+"),
}

# Connection strings take a different path. An early version treated them like
# every other literal and got it wrong: the pattern cut at the first space of a
# display name containing spaces, and flagged as invented a string the desktop
# tool had written itself. A connection string cannot be verified by precedent,
# because it is usually unique, nor over HTTP, because it is not a network URL.
# What CAN be verified is its SHAPE, and that is exactly what distinguished the
# real one from the invented one: the hand-written one carried only two keys and
# was missing everything else the tool adds.
CONNECTION_MARK = "powerbi://"
CONNECTION_KEYS = ("data source", "initial catalog", "semanticmodelid")

EXTENSIONS = {".json", ".pbir", ".pbip", ".pbism", ".tmdl", ".py", ".md", ".yml", ".yaml"}

# Paths that neither count as precedent nor get scanned: they are the method's own
# documentation, where these literals appear as examples.
EXCLUDE = ("docs/faw/", ".faw/", "faw/contracts/TEMPLATE")


def _git(*args: str) -> str:
    r = subprocess.run(["git", *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.stdout if r.returncode == 0 else ""


def _files(whole_tree: bool) -> list[str]:
    output = _git("ls-files") if whole_tree else _git("diff", "--cached", "--name-only")
    return [f for f in output.splitlines() if f.strip()]


def _relevant(path: str) -> bool:
    if any(x in path for x in EXCLUDE):
        return False
    return Path(path).suffix.lower() in EXTENSIONS


def _literals(text: str) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for name, rx in PATTERNS.items():
        for m in rx.findall(text):
            out.setdefault(name, set()).add(m.rstrip('.,;:"\''))
    return out


def _precedent(literal: str, current_file: str) -> str | None:
    """Look for the literal in the COMMITTED version of the repository, not the tree."""
    output = _git("grep", "-l", "--fixed-strings", literal, "HEAD", "--")
    for line in output.splitlines():
        # `git grep ... HEAD` returns "HEAD:path"
        path = line.split(":", 1)[-1].strip()
        if path and path != current_file and not any(x in path for x in EXCLUDE):
            return path
    return None


def _resolves(url: str, cache: dict[str, bool]) -> bool:
    if url in cache:
        return cache[url]
    req = urllib.request.Request(url, method="GET",
                                 headers={"User-Agent": "faw-verify-platform"})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            ok = 200 <= r.status < 300
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
        ok = False
    cache[url] = ok
    return ok


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    p = argparse.ArgumentParser(description="FAW platform gate")
    p.add_argument("--all", action="store_true",
                   help="scan the whole tracked tree instead of the staged diff")
    p.add_argument("--offline", action="store_true",
                   help="do not try to resolve URLs; accept precedent in the repository only")
    a = p.parse_args()

    if not _git("rev-parse", "--git-dir").strip():
        print("ERROR: this is not a git repository", file=sys.stderr)
        return 2

    files = [f for f in _files(a.all) if _relevant(f)]
    print(f"\n=== Platform: {'whole tree' if a.all else 'staged diff'} ===")
    print(f"  relevant files: {len(files)}")

    if not files:
        print("\n  nothing to verify\n\n  PASS\n")
        receipts.issue("platform", "verify_platform.py", [],
                       "no relevant files in scope")
        return 0

    cache: dict[str, bool] = {}
    total = 0
    verified: list[tuple[str, str, str]] = []
    unverified: list[tuple[str, str, str]] = []

    for path in files:
        pth = Path(path)
        if not pth.exists():
            continue
        try:
            text = pth.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        # --- Connection strings: checked by shape, not by precedent ---
        if CONNECTION_MARK in text.lower():
            total += 1
            lower = text.lower()
            missing = [c for c in CONNECTION_KEYS if c not in lower]
            if missing:
                unverified.append((
                    path,
                    f"connection string to {CONNECTION_MARK}...",
                    f"[connection-string] missing keys the tool emits: {', '.join(missing)}",
                ))
            else:
                verified.append((path, f"connection string to {CONNECTION_MARK}...",
                                 "has the complete shape the tool emits"))

        for kind, literals in _literals(text).items():
            for lit in literals:
                total += 1
                prec = _precedent(lit, path)
                if prec:
                    verified.append((path, lit, f"precedent in {prec}"))
                    continue
                if lit.startswith("https://") and not a.offline:
                    if _resolves(lit, cache):
                        verified.append((path, lit, "resolves HTTP 200"))
                        continue
                    unverified.append((path, lit, "does not resolve and has no precedent"))
                    continue
                unverified.append((path, lit, f"[{kind}] no precedent in the repository"))

    print(f"  platform literals found: {total}")
    for path, lit, reason in verified:
        print(f"    ok   {lit[:88]}  ({reason})")

    if unverified:
        print(f"\n  [ERROR] {len(unverified)} UNVERIFIED literals:")
        for path, lit, reason in unverified:
            print(f"      {path}")
            print(f"        {lit}")
            print(f"        -> {reason}")
        print("\n  A platform literal with no precedent and no resolution is an analogy,\n"
              "  not a fact (principle 6). How to resolve it:\n"
              "    - Copy it from a real artifact the tool already wrote.\n"
              "    - Or let the tool generate it and commit THAT.\n"
              "    - Or read the official documentation and verify the exact URL.\n\n  FAIL\n")
        receipts.invalidate("platform")
        return 1

    print("\n  PASS\n")
    receipts.issue("platform", "verify_platform.py", [],
                   f"{total} platform literals, all with precedent or resolution")
    return 0


if __name__ == "__main__":
    sys.exit(main())
