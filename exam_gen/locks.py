"""Teacher item locks (Round 34 / F5).

A teacher who fixes a clumsy stem or swaps in a better distractor should not
lose that work the next time they press Generate.  A *lock* pins one item so
regeneration reuses the teacher's version verbatim.

Locks are stored per year and keyed by the **normalised original stem**, so a
lock survives a different seed, theme or difficulty as long as the same bank
item comes up.  The file lives beside the other machine-local app state in
``<appdir>/locked_items.json`` and is therefore never committed.
"""
from __future__ import annotations

import json
import os

FILENAME = "locked_items.json"

#: ``"bm"`` / ``"en"`` labels are cosmetic; only the stored fields matter.
_FIELDS = ("stem", "options", "answer", "ans_text", "note", "box",
           "prompt", "model", "lines", "bullets")


def _appdir(appdir: str | None = None) -> str:
    if appdir:
        return appdir
    base = (os.environ.get("XDG_DATA_HOME")
            or os.path.expanduser("~/.local/share"))
    return os.path.join(base, "exam-gen")


def path(appdir: str | None = None) -> str:
    return os.path.join(_appdir(appdir), FILENAME)


def key_for(stem: str) -> str:
    """Normalised lookup key for an item stem."""
    return " ".join(str(stem or "").lower().split())


def normalise(store) -> dict:
    """Coerce whatever was on disk into ``{year: {key: {...}}}``.

    A corrupt or hand-edited file must never break generation, so anything
    unrecognisable is dropped rather than raising.
    """
    out: dict[str, dict] = {}
    if not isinstance(store, dict):
        return out
    for year, items in store.items():
        if not isinstance(items, dict):
            continue
        clean: dict[str, dict] = {}
        for k, v in items.items():
            if not isinstance(v, dict):
                continue
            keep = {f: v[f] for f in _FIELDS if f in v}
            if "stem" in keep or "prompt" in keep:
                clean[str(k)] = keep
        if clean:
            out[str(year)] = clean
    return out


def load(appdir: str | None = None) -> dict:
    """Read the lock store; a missing or corrupt file reads as empty."""
    try:
        with open(path(appdir), encoding="utf-8") as fh:
            return normalise(json.load(fh))
    except (OSError, ValueError):
        return {}


def save(store: dict, appdir: str | None = None) -> str:
    """Write the lock store, creating the directory if needed."""
    p = path(appdir)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(normalise(store), fh, ensure_ascii=False, indent=2)
    os.replace(tmp, p)
    return p


def locked_keys(store: dict, year: int) -> set[str]:
    """The stems locked for one year."""
    return set(normalise(store).get(str(int(year)), {}).keys())
