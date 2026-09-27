"""Cheap, deterministic integrity checks for the committed Claude Pop assets."""

import hashlib
import json
import re
import struct
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "eidoverse/claude_pop"
errors = []


def fail(message):
    errors.append(message)


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)
    except (OSError, UnicodeError, ValueError) as exc:
        fail(f"{path.relative_to(ROOT)}: {exc}")
        return None


def asset(path, base=ROOT, suffix=None):
    if not isinstance(path, str) or not path or "\\" in path:
        fail(f"invalid asset path: {path!r}")
        return None
    parts = Path(path)
    if parts.is_absolute() or any(part in ("..", ".") for part in path.split("/")):
        fail(f"unsafe asset path: {path!r}")
        return None
    resolved = (base / parts).resolve()
    if not resolved.is_relative_to(ROOT) or not resolved.is_file():
        fail(f"missing asset: {path} (relative to {base.relative_to(ROOT)})")
        return None
    if suffix and resolved.suffix.lower() != suffix:
        fail(f"wrong asset type: {path}, expected {suffix}")
    return resolved


def check_binary(path):
    if path.suffix.lower() not in (".glb", ".vrm", ".vrma"):
        return
    with path.open("rb") as stream:
        header = stream.read(12)
    if len(header) != 12 or header[:4] != b"glTF" or struct.unpack_from("<I", header, 4)[0] != 2 or struct.unpack_from("<I", header, 8)[0] != path.stat().st_size:
        fail(f"invalid GLB header/length: {path.relative_to(ROOT)}")


def check_entry(entry, key, base=ROOT, suffix=None, hashed=False):
    if not isinstance(entry, dict):
        fail(f"invalid catalog entry: {entry!r}")
        return None
    path = asset(entry.get(key), base, suffix)
    if path is None:
        return None
    size = entry.get("bytes")
    if size is not None and (type(size) is not int or size != path.stat().st_size):
        fail(f"size mismatch: {path.relative_to(ROOT)}")
    check_binary(path)
    if hashed:
        digest = entry.get("sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            fail(f"invalid SHA-256 entry: {path.relative_to(ROOT)}")
        else:
            h = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    h.update(chunk)
            if h.hexdigest() != digest:
                fail(f"SHA-256 mismatch: {path.relative_to(ROOT)}")
    return path.relative_to(ROOT).as_posix()


def unique(paths, label):
    for path, count in Counter(paths).items():
        if count > 1:
            fail(f"duplicate {label}: {path}")


def catalog(name, key, count_field, suffix):
    data = read_json(PACK / name)
    if not isinstance(data, dict) or not isinstance(data.get(key), list):
        fail(f"invalid catalog: {name}")
        return [], set()
    rows = data[key]
    paths = [check_entry(row, "path", suffix=suffix, hashed=True) for row in rows]
    recorded = [p for p in paths if p]
    distinct = set(recorded)
    if data.get(count_field) != len(distinct):
        fail(f"{name}: {count_field} differs from distinct committed paths")
    actual = {p.relative_to(ROOT).as_posix() for p in (PACK / name.split("/")[0]).rglob(f"*{suffix}")}
    if distinct != actual:
        fail(f"{name}: unlisted assets {sorted(actual - distinct)}, missing entries {sorted(distinct - actual)}")
    return rows, distinct


def main():
    for path in sorted(PACK.rglob("*.json")):
        read_json(path)

    avatars, avatar_paths = catalog("avatars/catalog.json", "avatars", "count", ".vrm")
    unique([r.get("path") for r in avatars if isinstance(r, dict)], "avatar path")
    motions, motion_paths = catalog("motions/catalog.json", "clips", "uniqueClips", ".vrma")
    motion_data = read_json(PACK / "motions/catalog.json") or {}
    if motion_data.get("sourceEntries") != len(motions):
        fail("motions/catalog.json: sourceEntries mismatch")
    unique([(r.get("archive"), r.get("source")) for r in motions if isinstance(r, dict)], "motion source")
    aliases = {}
    for row in motions:
        if not isinstance(row, dict):
            continue
        signature = (row.get("sha256"), row.get("bytes"))
        previous = aliases.setdefault(row.get("path"), signature)
        if previous != signature:
            fail(f"conflicting aliases: {row.get('path')}")
    unique([aliases[p][0] for p in motion_paths], "committed motion SHA-256")

    style = read_json(PACK / "accessory_styles/asset_catalog.json") or {}
    inventory = read_json(PACK / "wardrobe/manifests/asset_inventory.json") or {}
    groups = [(style, "assets", PACK / "accessory_styles"), (inventory, "items", PACK / "wardrobe")]
    listed = set()
    for data, key, base in groups:
        rows = data.get(key, [])
        if not isinstance(rows, list):
            fail(f"invalid {key} inventory in {base.relative_to(ROOT)}")
            continue
        paths = [check_entry(row, "file", base, ".glb") for row in rows]
        unique([p for p in paths if p], "mesh path")
        listed.update(p for p in paths if p)
        if "assetFiles" in data and data["assetFiles"] != len(rows):
            fail("wardrobe inventory count mismatch")
    actual = {p.relative_to(ROOT).as_posix() for p in PACK.rglob("*.glb")}
    if listed != actual:
        fail(f"mesh inventory mismatch: unlisted {sorted(actual - listed)}, missing {sorted(listed - actual)}")

    # These fields are committed asset references; source ZIP paths and generated
    # work/ outputs are deliberately excluded.
    for path in sorted(PACK.rglob("*.json")):
        if path.name in ("catalog.json", "asset_catalog.json", "asset_inventory.json", "asset_manifest.json"):
            continue
        data = read_json(path)
        if data is None:
            continue
        def visit(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    if key in ("file", "clip", "asset", "garment") and isinstance(value, str) and Path(value).suffix.lower() in (".json", ".vrma", ".vrm", ".glb", ".png"):
                        base = PACK / "wardrobe" if path.is_relative_to(PACK / "wardrobe/manifests") else path.parent.parent if path.parent.name == "groups" and key == "clip" else path.parent
                        asset(value, base)
                    elif key == "baseVRM" and isinstance(value, str):
                        asset(value)
                    else:
                        visit(value)
            elif isinstance(node, list):
                for value in node:
                    visit(value)
        visit(data)

    if errors:
        for message in sorted(set(errors)):
            print("ERROR:", message, file=sys.stderr)
        return 1
    print(f"Claude Pop assets OK: {len(avatar_paths)} VRMs, {len(motion_paths)} VRMAs, {len(listed)} GLBs; JSON and SHA-256 verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
