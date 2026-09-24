"""Restore official A graph bytes from small GitHub-readable text payloads.

Only Python's standard library is needed. This does not run a solver or compute
file fingerprints. Existing real files are never overwritten with different data.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import json
from pathlib import Path


POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1\n"


def local_file(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Path is outside its input/output directory: {relative}")
    return path


def save_original(path: Path, raw: bytes, replace_pointers: bool) -> str:
    if path.exists():
        previous = path.read_bytes()
        if previous == raw:
            return "already_present"
        if not (replace_pointers and previous.startswith(POINTER_PREFIX)):
            raise ValueError(f"Refusing to replace existing different content: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".restoring")
    with temporary.open("xb") as stream:
        stream.write(raw)
    temporary.replace(path)
    return "restored"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload-dir", type=Path,
                        default=Path(__file__).resolve().parent / "a_input_payloads")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cases", nargs="+", help="Case numbers or names, e.g. 16 24 case_051")
    parser.add_argument("--replace-lfs-pointers", action="store_true")
    args = parser.parse_args()
    payload = args.payload_dir.resolve()
    manifest = json.loads((payload / "MANIFEST.json").read_text(encoding="utf-8"))
    if manifest["encoding"] != "gzip+base64" or manifest["schema_version"] != 1:
        raise ValueError("Unsupported payload format")
    cases = manifest["cases"]
    names = list(cases)
    if args.cases:
        names = []
        for item in args.cases:
            number = item.removeprefix("case_").removesuffix(".json")
            name = f"case_{int(number):03d}"
            if name not in cases:
                raise ValueError(f"Case is not in the official input manifest: {item}")
            if name not in names:
                names.append(name)
    statuses = {"restored": 0, "already_present": 0}
    for name in names:
        entry = cases[name]
        encoded = b"".join(local_file(payload, part).read_bytes()
                           for part in entry["parts"])
        encoded = b"".join(encoded.split())
        if len(encoded) != entry["base64_characters"]:
            raise ValueError(f"Missing or truncated payload: {name}")
        raw = gzip.decompress(base64.b64decode(encoded, validate=True))
        if len(raw) != entry["original_bytes"]:
            raise ValueError(f"Incomplete restored file: {name}")
        graph = json.loads(raw)
        if not isinstance(graph, dict) or not {"tensors", "ops", "edges"} <= graph.keys():
            raise ValueError(f"Not an official graph JSON object: {name}")
        status = save_original(local_file(args.output_dir, entry["filename"]),
                               raw, args.replace_lfs_pointers)
        statuses[status] += 1
    config_name = manifest["configuration"]["filename"]
    config = local_file(payload, config_name).read_bytes()
    if len(config) != manifest["configuration"]["original_bytes"]:
        raise ValueError("Incomplete original config.txt")
    save_original(local_file(args.output_dir, config_name), config,
                  args.replace_lfs_pointers)
    print(json.dumps({"official_graphs": len(names), **statuses,
                      "config": config_name, "output_dir": str(args.output_dir.resolve())}))


if __name__ == "__main__":
    main()
